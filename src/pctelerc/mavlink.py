from __future__ import annotations

from dataclasses import dataclass, replace
import logging
import threading
import time
from typing import Optional

from .config import AppSettings
from .core import ControlFrame, LinkState, heartbeat_link_state, normalized_to_pwm, PWM_NEUTRAL
from .field_safety import SafetyDecision, can_arm, can_continue_control, can_enable_control
from .network_errors import describe_mavlink_start_error

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MavlinkSnapshot:
    running: bool = False
    state: LinkState = LinkState.DISCONNECTED
    last_heartbeat: float | None = None
    heartbeat_age: float | None = None
    vehicle_system: int | None = None
    vehicle_component: int | None = None
    vehicle_type: str = ""
    mode: str = ""
    armed: bool = False
    control_enabled: bool = False
    failsafe_latched: bool = False
    steer_pwm: int = PWM_NEUTRAL
    throttle_pwm: int = PWM_NEUTRAL
    rx_messages: int = 0
    tx_messages: int = 0
    ignored_heartbeats: int = 0
    error: str = ""
    command_status: str = ""
    command_pending: bool = False


class MavlinkService:
    """One UDP socket and one accepted vehicle peer per operator session."""

    SEND_HZ = 20.0
    RELEASE_RETRIES = 3

    def __init__(self):
        self._lock = threading.Lock()
        self._lifecycle_lock = threading.RLock()
        self._send_lock = threading.RLock()
        self._settings = AppSettings()
        self._snapshot = MavlinkSnapshot()
        self._control_frame: Optional[ControlFrame] = None
        self._axis_count: int | None = None
        self._control_enabled = False
        self._failsafe_latched = False
        self._owns_override = False
        self._last_control_tick = None
        self._pending_arm = None
        self._command_deadline = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._link = None
        self._control_mav = None
        self._bound_host: str | None = None
        self._bound_port: int | None = None
        self._bridge_discovery_sent = False

    def configure(self, settings: AppSettings):
        with self._send_lock:
            return self._serialized_configure(settings)

    def _serialized_configure(self, settings: AppSettings):
        validated = AppSettings(**vars(settings)).validate()
        with self._lock:
            changed = validated != self._settings
        if changed:
            self.disable_control()
            with self._lock:
                network_changed = any(getattr(validated, key) != getattr(self._settings, key)
                                      for key in ("bind_host", "listen_port", "target_host", "target_port", "link_mode", "serial_port"))
                if self._link is not None and network_changed:
                    raise ValueError("Disconnect before changing MAVLink network settings.")
        with self._lock:
            self._settings = validated
            if changed:
                self._control_frame = None
                self._axis_count = None
            link = self._link
        if link is not None:
            self._configure_link_target(link, validated)

    def listener_restart_required(self) -> bool:
        with self._lifecycle_lock:
            thread_alive = bool(self._thread and self._thread.is_alive())
        with self._lock:
            settings = AppSettings(**vars(self._settings)).validate()
            bound_host = self._bound_host
            bound_port = self._bound_port
        if not thread_alive:
            return True
        return bound_host != settings.bind_host or bound_port != settings.listen_port

    def start(self) -> bool:
        with self._lifecycle_lock:
            if self._thread and self._thread.is_alive():
                logger.info("Ignoring duplicate MAVLink start request")
                return False
            self._stop.clear()
            thread = threading.Thread(
                target=self._run,
                daemon=True,
                name="pctelerc-mavlink",
            )
            self._thread = thread
            thread.start()
            return True

    def stop(self) -> bool:
        with self._lifecycle_lock:
            with self._send_lock:
                self._stop.set()
                self.disable_control()
            thread = self._thread
            if thread:
                thread.join(timeout=2.0)
                if thread.is_alive():
                    logger.error("MAVLink worker did not stop within timeout")
                    return False
            self._thread = None
            return True

    def snapshot(self) -> MavlinkSnapshot:
        with self._lock:
            return self._snapshot

    def set_control_frame(self, frame: ControlFrame | None, axis_count: int | None = None):
        with self._lock:
            self._control_frame = frame
            self._axis_count = axis_count

    def enable_control(self):
        with self._send_lock:
            return self._serialized_enable_control()

    def _serialized_enable_control(self):
        with self._lock:
            snap = self._snapshot
            frame = self._control_frame
            axis_count = self._axis_count
            settings = AppSettings(**vars(self._settings)).validate()
        decision = can_enable_control(
            settings=settings,
            link_state=(heartbeat_link_state(snap.last_heartbeat, stale_after=settings.heartbeat_timeout)
                        if snap.running and not self._stop.is_set() else LinkState.DISCONNECTED),
            frame=frame,
            axis_count=axis_count,
        )
        if not decision.allowed:
            return False, decision.message
        with self._lock:
            self._failsafe_latched = False
            self._control_enabled = True
            self._owns_override = True
            self._last_control_tick = time.monotonic()
            self._snapshot = replace(
                self._snapshot,
                control_enabled=True,
                failsafe_latched=False,
                error="",
            )
        logger.info(
            "PC control enabled for MAVLink sys=%s comp=%s",
            snap.vehicle_system,
            snap.vehicle_component,
        )
        return True, "PC control enabled."

    def disable_control(self):
        with self._send_lock:
            return self._serialized_disable_control()

    def _serialized_disable_control(self):
        with self._lock:
            was_enabled = self._control_enabled
            self._control_enabled = False
            release_needed = self._owns_override
            self._snapshot = replace(
                self._snapshot,
                control_enabled=False,
                steer_pwm=PWM_NEUTRAL,
                throttle_pwm=PWM_NEUTRAL,
            )
        if was_enabled or release_needed:
            if was_enabled:
                logger.info("PC control disabled; issuing neutral/release")
            return self._send_neutral_then_release()
        return True

    def arm(self):
        with self._send_lock:
            return self._serialized_arm()

    def _serialized_arm(self):
        with self._lock:
            snap = self._snapshot
            frame = self._control_frame
            axis_count = self._axis_count
            settings = AppSettings(**vars(self._settings)).validate()
            conn = self._link
            control_mav = self._control_mav
        decision = can_arm(
            settings=settings,
            link_state=(heartbeat_link_state(snap.last_heartbeat, stale_after=settings.heartbeat_timeout)
                        if snap.running and not self._stop.is_set() else LinkState.DISCONNECTED),
            frame=frame,
            axis_count=axis_count,
        )
        if not decision.allowed:
            return False, decision.message
        if conn is None or control_mav is None:
            return False, "Vehicle link is not connected."
        return self._send_arm_command(True)

    def disarm(self):
        with self._send_lock:
            return self._serialized_disarm()

    def _serialized_disarm(self):
        self.disable_control()
        return self._send_arm_command(False)

    def _send_arm_command(self, arm: bool):
        with self._lock:
            snap = self._snapshot
            conn = self._link
            control_mav = self._control_mav
            sysid = snap.vehicle_system
            compid = snap.vehicle_component
        if (not snap.running or self._stop.is_set()
                or heartbeat_link_state(snap.last_heartbeat, stale_after=self._settings.heartbeat_timeout) != LinkState.CONNECTED
                or conn is None or control_mav is None or sysid is None):
            return False, "Vehicle link is not connected."
        try:
            from pymavlink.dialects.v10 import ardupilotmega as mavlink1
            with self._send_lock:
                control_mav.command_long_send(
                    sysid,
                    compid or 1,
                    mavlink1.MAV_CMD_COMPONENT_ARM_DISARM,
                    0,
                    1.0 if arm else 0.0,
                    0, 0, 0, 0, 0, 0,
                )
            with self._lock:
                self._pending_arm = arm
                self._command_deadline = time.monotonic() + 5.0
                self._snapshot = replace(
                    self._snapshot,
                    tx_messages=self._snapshot.tx_messages + 1,
                    command_status="Arm request sent; awaiting vehicle confirmation." if arm else "Disarm request sent; awaiting vehicle confirmation.",
                    command_pending=True,
                )
            return (
                True,
                "Arm request sent; wait for heartbeat to confirm ARMED."
                if arm
                else "Disarm request sent; wait for heartbeat to confirm disarmed.",
            )
        except Exception as exc:
            with self._lock:
                self._snapshot = replace(
                    self._snapshot,
                    error=f"Arm/disarm send failed: {exc}",
                )
            return False, f"Could not send {'arm' if arm else 'disarm'} command: {exc}"

    def _configure_link_target(self, link, settings: AppSettings):
        with self._send_lock:
            link.configure_target(settings.target_host.strip(), settings.target_port)

    def _has_send_destination(self, link) -> bool:
        return link.destination is not None

    def _run(self):
        link = None
        try:
            with self._lock:
                settings = AppSettings(**vars(self._settings)).validate()

            from .transport import VehicleUDP
            if settings.link_mode == "elrs_serial":
                from .transport import VehicleSerial
                if not settings.serial_port:
                    raise ValueError("Select the ELRS module COM port before connecting.")
                link = VehicleSerial(settings.serial_port)
            else:
                link = VehicleUDP(settings.bind_host, settings.listen_port)
            self._configure_link_target(link, settings)

            # Keep receive auto-detection intact (MAVLink 1/2), but deliberately
            # encode all bridge-facing control traffic as MAVLink 1. The ESP32
            # command filter and Android TeleRC compatibility contract use
            # sysid 255 / compid 190 MAVLink 1 control frames.
            from pymavlink.dialects.v10 import ardupilotmega as mavlink1
            control_mav = mavlink1.MAVLink(
                link,
                srcSystem=255,
                srcComponent=190,
            )

            with self._lock:
                self._control_enabled = False
                self._owns_override = False
                self._last_control_tick = None
                self._control_frame = None
                self._axis_count = None
                self._link = link
                self._control_mav = control_mav
                self._bound_host = settings.bind_host
                self._bound_port = settings.listen_port
                self._bridge_discovery_sent = False
                self._snapshot = MavlinkSnapshot(
                    running=True,
                    state=LinkState.CONNECTING,
                )

            logger.info(
                "MAVLink link %s opened (%s)",
                settings.link_mode,
                settings.serial_port if settings.link_mode == "elrs_serial" else f"{settings.bind_host}:{settings.listen_port}",
            )

            next_hb = 0.0
            next_control = 0.0
            while not self._stop.is_set():
                now = time.monotonic()
                # Bound receive work to one decoded message per loop, including
                # malformed data, so noisy traffic cannot starve the watchdog.
                msg = link.recv_msg()
                if msg is not None and msg.get_type() != "BAD_DATA":
                    self._handle_message(msg, now)

                if now >= next_hb:
                    self._send_bridge_discovery()
                    self._send_gcs_heartbeat()
                    next_hb = now + 1.0

                self._refresh_link_state(now)

                if now >= next_control:
                    self._control_tick(now)
                    next_control = now + 1.0 / (5.0 if settings.link_mode == "elrs_serial" else self.SEND_HZ)

                time.sleep(0.005)

        except Exception as exc:
            with self._lock:
                settings = AppSettings(**vars(self._settings)).validate()
                self._failsafe_latched = self._failsafe_latched or self._control_enabled
                self._control_enabled = False
                self._snapshot = replace(
                    self._snapshot,
                    failsafe_latched=self._failsafe_latched,
                    running=False,
                    state=LinkState.DISCONNECTED,
                    control_enabled=False,
                    error=describe_mavlink_start_error(exc, settings.listen_port),
                )
            logger.exception("MAVLink worker stopped")

        finally:
            self._send_neutral_then_release()
            self._send_bridge_disconnect()
            with self._lock:
                link = self._link or link
                self._link = None
                self._control_mav = None
                self._bound_host = None
                self._bound_port = None
            try:
                if link is not None:
                    link.close()
            except Exception:
                pass
            with self._lock:
                self._control_enabled = False
                self._snapshot = replace(
                    self._snapshot,
                    running=False,
                    state=LinkState.DISCONNECTED,
                    last_heartbeat=None,
                    heartbeat_age=None,
                    vehicle_system=None,
                    vehicle_component=None,
                    armed=False,
                    control_enabled=False,
                    steer_pwm=PWM_NEUTRAL,
                    throttle_pwm=PWM_NEUTRAL,
                )
                self._control_frame = None
                self._axis_count = None
                self._pending_arm = None
                self._command_deadline = None
                self._snapshot = replace(self._snapshot, command_pending=False)

    def _handle_message(self, msg, now: float):
        typ = msg.get_type()
        with self._lock:
            snap = replace(
                self._snapshot,
                rx_messages=self._snapshot.rx_messages + 1,
            )

            if (typ == "COMMAND_ACK" and getattr(msg, "command", None) == 400
                    and self._pending_arm is not None
                    and msg.get_srcSystem() == snap.vehicle_system
                    and msg.get_srcComponent() == snap.vehicle_component):
                result = getattr(msg, "result", None)
                if result not in (0, 5):
                    action = "Arm" if self._pending_arm else "Disarm"
                    snap = replace(snap, command_status=f"{action} rejected by vehicle (MAV_RESULT {result}).", command_pending=False)
                    self._pending_arm = None
                    self._command_deadline = None
                else:
                    snap = replace(snap, command_status="Command acknowledged; awaiting heartbeat confirmation.")

            if typ == "HEARTBEAT" and getattr(msg, "type", None) != 6:
                valid_vehicle = (getattr(msg, "autopilot", 3) != 8
                                 and msg.get_srcSystem() not in (0, 255))
                if not valid_vehicle:
                    self._snapshot = replace(snap, ignored_heartbeats=snap.ignored_heartbeats + 1)
                    return

            if (typ == "HEARTBEAT" and getattr(msg, "type", None) != 6
                    and getattr(msg, "autopilot", 3) != 8
                    and msg.get_srcSystem() not in (0, 255)):
                src_sys = msg.get_srcSystem()
                src_comp = msg.get_srcComponent()

                if snap.vehicle_system is not None and (
                    src_sys != snap.vehicle_system
                    or src_comp != snap.vehicle_component
                ):
                    self._snapshot = replace(
                        snap,
                        ignored_heartbeats=snap.ignored_heartbeats + 1,
                    )
                    return

                try:
                    from pymavlink import mavutil
                    mode = mavutil.mode_string_v10(msg)
                    armed = bool(
                        msg.base_mode
                        & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
                    )
                except Exception:
                    mode = ""
                    armed = False

                first_lock = snap.vehicle_system is None
                snap = replace(
                    snap,
                    last_heartbeat=now,
                    state=LinkState.CONNECTED,
                    vehicle_system=src_sys,
                    vehicle_component=src_comp,
                    vehicle_type=str(getattr(msg, "type", "")),
                    mode=mode,
                    armed=armed,
                    error="",
                )
                if self._pending_arm is not None and armed == self._pending_arm:
                    snap = replace(snap, command_status="Vehicle confirmed ARMED." if armed else "Vehicle confirmed disarmed.", command_pending=False)
                    self._pending_arm = None
                    self._command_deadline = None
                if first_lock:
                    if self._link is not None:
                        self._link.lock_vehicle_peer()
                    logger.info(
                        "Locked MAVLink vehicle identity sys=%s comp=%s",
                        src_sys,
                        src_comp,
                    )

            self._snapshot = snap

    def _refresh_link_state(self, now: float):
        release = False
        with self._lock:
            settings = self._settings
            snap = self._snapshot
            if self._command_deadline is not None and now >= self._command_deadline:
                snap = replace(snap, command_status="Arm/disarm was not confirmed within 5 seconds. Check vehicle state.", command_pending=False)
                self._pending_arm = None
                self._command_deadline = None
            state = heartbeat_link_state(
                snap.last_heartbeat,
                now=now,
                stale_after=settings.heartbeat_timeout,
            )
            age = (
                None
                if snap.last_heartbeat is None
                else max(0.0, now - snap.last_heartbeat)
            )
            if state == LinkState.STALE and self._control_enabled:
                logger.error(
                    "Heartbeat stale while PC control active; latching fail-safe"
                )
                self._control_enabled = False
                self._failsafe_latched = True
                release = True

            self._snapshot = replace(
                snap,
                state=state,
                heartbeat_age=age,
                control_enabled=self._control_enabled,
                failsafe_latched=self._failsafe_latched,
            )

        if release:
            self._send_neutral_then_release()

    def _control_tick(self, now: float):
        with self._send_lock:
            return self._serialized_control_tick(now)

    def _serialized_control_tick(self, now: float):
        with self._lock:
            settings = AppSettings(**vars(self._settings)).validate()
            frame = self._control_frame
            axis_count = self._axis_count
            enabled = self._control_enabled
            snap = self._snapshot
            # Read time after the frame: the producer may have sampled after
            # the worker loop started, which must not look like a future frame.
            now = time.monotonic()
            previous_tick = self._last_control_tick
            if enabled:
                self._last_control_tick = now

        if not enabled:
            return

        decision = can_continue_control(
            settings=settings,
            link_state=(heartbeat_link_state(snap.last_heartbeat, stale_after=settings.heartbeat_timeout)
                        if snap.running and not self._stop.is_set() else LinkState.DISCONNECTED),
            frame=frame,
            axis_count=axis_count,
            now=now,
        )
        if previous_tick is not None and now - previous_tick > max(settings.controller_timeout, .4 if settings.link_mode == "elrs_serial" else 0):
            decision = SafetyDecision(False, "worker_delayed", "Control worker missed its watchdog deadline.")
        if not decision.allowed:
            with self._lock:
                self._control_enabled = False
                self._failsafe_latched = True
                self._snapshot = replace(
                    self._snapshot,
                    control_enabled=False,
                    failsafe_latched=True,
                    steer_pwm=PWM_NEUTRAL,
                    throttle_pwm=PWM_NEUTRAL,
                    error=f"Control disabled by fail-safe: {decision.message}",
                )
            logger.error("PC control fail-safe: %s", decision.message)
            self._send_neutral_then_release()
            return

        steer = normalized_to_pwm(frame.steering, 1.0)
        throttle = normalized_to_pwm(
            frame.throttle,
            settings.throttle_limit,
        )
        if self._send_override(steer, throttle):
            with self._lock:
                self._snapshot = replace(
                    self._snapshot,
                    steer_pwm=steer,
                    throttle_pwm=throttle,
                    tx_messages=self._snapshot.tx_messages + 1,
                )
        else:
            logger.error(
                "RC override transmission failed; latching fail-safe"
            )
            with self._lock:
                self._control_enabled = False
                self._failsafe_latched = True
                self._snapshot = replace(
                    self._snapshot,
                    control_enabled=False,
                    failsafe_latched=True,
                    steer_pwm=PWM_NEUTRAL,
                    throttle_pwm=PWM_NEUTRAL,
                    error="Control disabled: RC override transmission failed.",
                )
            self._send_neutral_then_release()

    def _send_bridge_discovery(self):
        # The TeleRC bridge uses this packet to register/refresh the PC peer.
        # GCS heartbeat alone is not a recognized pairing/keepalive packet.
        with self._send_lock:
            with self._lock:
                link = self._link
                settings = self._settings
            if link is None or self._stop.is_set() or settings.link_mode != "telerc_udp":
                return
            destination = link.destination or ("192.168.4.1", settings.target_port)
            try:
                packet = b"TELERC_DISCOVER_V1"
                if link.port.sendto(packet, destination) == len(packet):
                    self._bridge_discovery_sent = True
            except OSError as exc:
                logger.debug("Bridge discovery send failed: %s", exc)

    def _send_bridge_disconnect(self):
        # After neutral/sparse release, relinquish this session's bridge lease.
        # Do not send handover packets when we never attempted registration.
        with self._send_lock:
            with self._lock:
                link = self._link
                settings = self._settings
            if link is None or not self._bridge_discovery_sent:
                return
            destination = link.destination or ("192.168.4.1", settings.target_port)
            for _ in range(self.RELEASE_RETRIES):
                try:
                    link.port.sendto(b"TELERC_DISCONNECT_V1", destination)
                except OSError as exc:
                    logger.debug("Bridge disconnect send failed: %s", exc)
                time.sleep(.02)
            self._bridge_discovery_sent = False

    def _send_gcs_heartbeat(self):
        with self._lock:
            conn = self._link
            control_mav = self._control_mav
        if conn is None or control_mav is None or not self._has_send_destination(conn):
            return
        try:
            from pymavlink.dialects.v10 import ardupilotmega as mavlink1
            with self._send_lock:
                control_mav.heartbeat_send(
                    mavlink1.MAV_TYPE_GCS,
                    mavlink1.MAV_AUTOPILOT_INVALID,
                    0,
                    0,
                    mavlink1.MAV_STATE_ACTIVE,
                )
            with self._lock:
                self._snapshot = replace(
                    self._snapshot,
                    tx_messages=self._snapshot.tx_messages + 1,
                )
        except Exception as exc:
            logger.warning("GCS heartbeat send failed: %s", exc)
            with self._lock:
                self._snapshot = replace(
                    self._snapshot,
                    error=f"GCS heartbeat send failed: {exc}",
                )

    def _send_override(self, steer_pwm: int, throttle_pwm: int) -> bool:
        with self._lock:
            conn = self._link
            control_mav = self._control_mav
            snap = self._snapshot
            settings = self._settings
            sysid = snap.vehicle_system
            compid = snap.vehicle_component

        if conn is None or control_mav is None or sysid is None:
            return False

        channels = [65535] * 8
        channels[settings.steering_channel - 1] = int(steer_pwm)
        channels[settings.throttle_channel - 1] = int(throttle_pwm)

        try:
            with self._send_lock:
                control_mav.rc_channels_override_send(
                    sysid,
                    compid or 1,
                    *channels,
                )
            return True
        except Exception:
            return False

    def _send_neutral_then_release(self):
        with self._send_lock:
            return self._serialized_send_neutral_then_release()

    def _serialized_send_neutral_then_release(self):
        with self._lock:
            conn = self._link
            control_mav = self._control_mav
            owned = self._owns_override
        if not owned:
            return True
        if conn is None or control_mav is None:
            return False

        delivered = False
        for _ in range(self.RELEASE_RETRIES):
            try:
                neutral_sent = self._send_override(PWM_NEUTRAL, PWM_NEUTRAL)
                time.sleep(0.02)

                with self._lock:
                    snap = self._snapshot
                    settings = self._settings
                    sysid = snap.vehicle_system
                    compid = snap.vehicle_component

                if sysid is None:
                    return False

                channels = [65535] * 8
                channels[settings.steering_channel - 1] = 0
                channels[settings.throttle_channel - 1] = 0

                with self._send_lock:
                    control_mav.rc_channels_override_send(
                        sysid,
                        compid or 1,
                        *channels,
                    )
                delivered = delivered or neutral_sent
                with self._lock:
                    self._snapshot = replace(self._snapshot, tx_messages=self._snapshot.tx_messages + 1 + int(neutral_sent))
                time.sleep(0.02)

            except Exception as exc:
                logger.warning(
                    "Neutral/release attempt failed: %s",
                    exc,
                )

        with self._lock:
            if delivered:
                self._owns_override = False
            else:
                self._snapshot = replace(self._snapshot, error="Neutral/release could not be sent; verify vehicle failsafe and transmitter handover.")
        return delivered

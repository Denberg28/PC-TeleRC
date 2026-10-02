from __future__ import annotations

from dataclasses import dataclass, replace
import logging
import threading
import time
from typing import Optional

from .config import AppSettings
from .core import ControlFrame, LinkState, heartbeat_link_state, normalized_to_pwm, PWM_NEUTRAL
from .field_safety import can_arm, can_continue_control, can_enable_control
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


class MavlinkService:
    """Single-socket MAVLink transport for the PC TeleRC session.

    Exactly one UDP socket is bound for both receive and transmit. When a fixed
    ESP32 target is configured the bound input socket is switched to fixed-target
    transmit mode; otherwise pymavlink replies to the last UDP peer. This avoids
    maintaining a second UDP socket and removes avoidable listener lifecycle races.
    """

    SEND_HZ = 20.0
    RELEASE_RETRIES = 3

    def __init__(self):
        self._lock = threading.Lock()
        self._lifecycle_lock = threading.RLock()
        self._send_lock = threading.Lock()
        self._settings = AppSettings()
        self._snapshot = MavlinkSnapshot()
        self._control_frame: Optional[ControlFrame] = None
        self._axis_count: int | None = None
        self._control_enabled = False
        self._failsafe_latched = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._link = None
        self._control_mav = None
        self._bound_host: str | None = None
        self._bound_port: int | None = None

    def configure(self, settings: AppSettings):
        validated = AppSettings(**vars(settings)).validate()
        with self._lock:
            self._settings = validated
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
        self.disable_control()
        with self._lifecycle_lock:
            self._stop.set()
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
        with self._lock:
            snap = self._snapshot
            frame = self._control_frame
            axis_count = self._axis_count
            settings = AppSettings(**vars(self._settings)).validate()
        decision = can_enable_control(
            settings=settings,
            link_state=snap.state,
            frame=frame,
            axis_count=axis_count,
        )
        if not decision.allowed:
            return False, decision.message
        with self._lock:
            self._failsafe_latched = False
            self._control_enabled = True
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
        with self._lock:
            was_enabled = self._control_enabled
            self._control_enabled = False
            link_available = self._link is not None
            self._snapshot = replace(
                self._snapshot,
                control_enabled=False,
                steer_pwm=PWM_NEUTRAL,
                throttle_pwm=PWM_NEUTRAL,
            )
        if was_enabled or link_available:
            if was_enabled:
                logger.info("PC control disabled; issuing neutral/release")
            self._send_neutral_then_release()

    def arm(self):
        with self._lock:
            snap = self._snapshot
            frame = self._control_frame
            axis_count = self._axis_count
            settings = AppSettings(**vars(self._settings)).validate()
            conn = self._link
            control_mav = self._control_mav
        decision = can_arm(
            settings=settings,
            link_state=snap.state,
            frame=frame,
            axis_count=axis_count,
        )
        if not decision.allowed:
            return False, decision.message
        if conn is None or control_mav is None:
            return False, "Vehicle link is not connected."
        return self._send_arm_command(True)

    def disarm(self):
        return self._send_arm_command(False)

    def _send_arm_command(self, arm: bool):
        with self._lock:
            snap = self._snapshot
            conn = self._link
            control_mav = self._control_mav
            sysid = snap.vehicle_system
            compid = snap.vehicle_component
        if snap.state != LinkState.CONNECTED or conn is None or control_mav is None or sysid is None:
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
                self._snapshot = replace(
                    self._snapshot,
                    tx_messages=self._snapshot.tx_messages + 1,
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
        """Configure outbound writes on the already-bound receive socket."""
        try:
            target_host = settings.target_host.strip()
            with self._send_lock:
                if target_host:
                    link.destination_addr = (target_host, settings.target_port)
                    link.udp_server = False
                else:
                    link.udp_server = True
        except Exception as exc:
            logger.warning("Could not update MAVLink UDP target: %s", exc)

    def _has_send_destination(self, link) -> bool:
        with self._lock:
            target_host = self._settings.target_host.strip()
        if target_host:
            return True
        return getattr(link, "last_address", None) is not None

    def _run(self):
        try:
            from pymavlink import mavutil
            with self._lock:
                settings = AppSettings(**vars(self._settings)).validate()

            link = mavutil.mavlink_connection(
                f"udpin:{settings.bind_host}:{settings.listen_port}",
                source_system=255,
                source_component=190,
                autoreconnect=True,
            )
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
                self._link = link
                self._control_mav = control_mav
                self._bound_host = settings.bind_host
                self._bound_port = settings.listen_port
                self._snapshot = MavlinkSnapshot(
                    running=True,
                    state=LinkState.CONNECTING,
                )

            logger.info(
                "MAVLink UDP listener bound to %s:%s using one shared socket",
                settings.bind_host,
                settings.listen_port,
            )

            next_hb = 0.0
            next_control = 0.0
            while not self._stop.is_set():
                now = time.monotonic()
                msg = link.recv_match(blocking=False)
                if msg is not None:
                    self._handle_message(msg, now)

                if now >= next_hb:
                    self._send_gcs_heartbeat()
                    next_hb = now + 1.0

                self._refresh_link_state(now)

                if now >= next_control:
                    self._control_tick(now)
                    next_control = now + 1.0 / self.SEND_HZ

                time.sleep(0.005)

        except Exception as exc:
            with self._lock:
                settings = AppSettings(**vars(self._settings)).validate()
                self._control_enabled = False
                self._snapshot = replace(
                    self._snapshot,
                    running=False,
                    state=LinkState.DISCONNECTED,
                    control_enabled=False,
                    error=describe_mavlink_start_error(exc, settings.listen_port),
                )
            logger.exception("MAVLink worker stopped")

        finally:
            self._send_neutral_then_release()
            with self._lock:
                link = self._link
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
                    control_enabled=False,
                )

    def _handle_message(self, msg, now: float):
        typ = msg.get_type()
        with self._lock:
            snap = replace(
                self._snapshot,
                rx_messages=self._snapshot.rx_messages + 1,
            )

            if typ == "HEARTBEAT" and getattr(msg, "type", None) != 6:
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
                    logger.warning(
                        "Ignored foreign MAVLink heartbeat sys=%s comp=%s; locked sys=%s comp=%s",
                        src_sys,
                        src_comp,
                        snap.vehicle_system,
                        snap.vehicle_component,
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
                if first_lock:
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
        with self._lock:
            settings = AppSettings(**vars(self._settings)).validate()
            frame = self._control_frame
            axis_count = self._axis_count
            enabled = self._control_enabled
            snap = self._snapshot

        if not enabled:
            return

        decision = can_continue_control(
            settings=settings,
            link_state=snap.state,
            frame=frame,
            axis_count=axis_count,
            now=now,
        )
        if not decision.allowed:
            with self._lock:
                self._control_enabled = False
                self._failsafe_latched = True
                self._snapshot = replace(
                    self._snapshot,
                    control_enabled=False,
                    failsafe_latched=True,
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
                    error="Control disabled: RC override transmission failed.",
                )
            self._send_neutral_then_release()

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
                    mavutil.mavlink.MAV_STATE_ACTIVE,
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
        with self._lock:
            conn = self._link
            control_mav = self._control_mav
        if conn is None or control_mav is None:
            return

        for _ in range(self.RELEASE_RETRIES):
            try:
                self._send_override(PWM_NEUTRAL, PWM_NEUTRAL)
                time.sleep(0.02)

                with self._lock:
                    snap = self._snapshot
                    settings = self._settings
                    sysid = snap.vehicle_system
                    compid = snap.vehicle_component

                if sysid is None:
                    return

                channels = [65535] * 8
                channels[settings.steering_channel - 1] = 0
                channels[settings.throttle_channel - 1] = 0

                with self._send_lock:
                    control_mav.rc_channels_override_send(
                        sysid,
                        compid or 1,
                        *channels,
                    )
                time.sleep(0.02)

            except Exception as exc:
                logger.warning(
                    "Neutral/release attempt failed: %s",
                    exc,
                )

from __future__ import annotations

from dataclasses import dataclass, replace
import logging
import threading
import time
from typing import Optional

from .config import AppSettings
from .core import ControlFrame, LinkState, apply_sensitivity, heartbeat_link_state, normalized_to_pwm, PWM_NEUTRAL
from .field_safety import can_arm, can_continue_control, can_enable_control
from .network_errors import describe_mavlink_start_error
from .serial_errors import RadioConnectionError, describe_serial_error

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MavlinkSnapshot:
    running: bool = False
    state: LinkState = LinkState.DISCONNECTED
    last_heartbeat: float | None = None
    heartbeat_age: float | None = None
    opened_at: float | None = None
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
    radio_status: str = ""
    latitude: float | None = None
    longitude: float | None = None
    heading: float | None = None
    speed: float | None = None
    voltage: float | None = None
    battery_remaining: int | None = None
    battery_timestamp: float | None = None
    gps_fix: int = 0
    gps_timestamp: float | None = None
    satellites: int | None = None
    position_timestamp: float | None = None


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
        self._send_lock = threading.RLock()
        self._settings = AppSettings()
        self._snapshot = MavlinkSnapshot()
        self._control_frame: Optional[ControlFrame] = None
        self._axis_count: int | None = None
        self._control_source = None
        self._control_enabled = False
        self._failsafe_latched = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._link = None
        self._control_mav = None
        self._bound_host: str | None = None
        self._bound_port: int | None = None
        self._bound_mode = "telerc_udp"
        self._bound_serial = ""
        self._bridge_registered = False
        self._lora_direct_deadline = None
        self._lora_backend = "DIRECT"
        self._lora_stop_baseline = None
        self._owns_elrs_override = False
        self._last_elrs_tick = None
        self._next_elrs_send = 0.0
        self._enabled_controller_session = None

    def configure(self, settings: AppSettings):
        with self._send_lock:
            return self._configure(settings)

    def _configure(self, settings: AppSettings):
        validated = AppSettings(**vars(settings)).validate()
        with self._lock:
            old = self._settings
            link = self._link
        if validated != old and (old.link_mode in ("elrs_serial", "elrs_backpack") or validated.link_mode in ("elrs_serial", "elrs_backpack")):
            self.disable_control()
            routing = ("link_mode", "elrs_port", "lora_port", "bind_host", "listen_port", "target_host", "target_port", "backpack_host", "backpack_listen_port", "backpack_target_port")
            if link is not None and any(getattr(old, key) != getattr(validated, key) for key in routing):
                raise ValueError("Disconnect before changing the radio connection.")
            with self._lock:
                self._control_frame = None
                self._axis_count = None
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
        if self._bound_mode != settings.link_mode:
            return True
        if settings.link_mode == "elrs_backpack":
            return False  # Routing edits are rejected while this session is open.
        if settings.link_mode != "telerc_udp":
            return self._bound_serial != self._serial_port(settings)
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

    def set_control_source(self, source):
        """Bind a thread-safe snapshot supplier, never a GUI/SDL polling call."""
        with self._lock:
            self._control_source = source

    def _refresh_control_source(self):
        with self._lock:
            source = self._control_source
        if source is None:
            return
        try:
            sample = source()
            frame = sample.frame if sample.connected else None
            axes = len(sample.axes) if sample.connected else None
        except Exception:
            logger.exception("Controller snapshot unavailable")
            frame, axes = None, None
        # Retain acquisition time: a stopped controller must still expire.
        self.set_control_frame(frame, axes)

    def enable_control(self):
        with self._send_lock:
            return self._enable_control()

    def _elrs_link_state(self, snap, settings):
        if settings.link_mode != "elrs_serial":
            return snap.state
        if snap.running and not self._stop.is_set() and self._link is not None:
            try:
                self._link.check_health()
            except OSError:
                return LinkState.DISCONNECTED
        return (heartbeat_link_state(snap.last_heartbeat, now=time.monotonic(), stale_after=settings.heartbeat_timeout)
                if snap.running and not self._stop.is_set() and self._link is not None
                else LinkState.DISCONNECTED)

    def _enable_control(self):
        if self._settings.link_mode == "elrs_backpack":
            return False, "Handset control — Backpack provides telemetry and FPV only."
        self._refresh_control_source()
        with self._lock:
            snap = self._snapshot
            frame = self._control_frame
            axis_count = self._axis_count
            settings = AppSettings(**vars(self._settings)).validate()
        decision = can_enable_control(
            settings=settings,
            link_state=self._elrs_link_state(snap, settings),
            frame=frame,
            axis_count=axis_count,
            now=time.monotonic(),
        )
        if not decision.allowed:
            return False, decision.message
        if settings.link_mode == "lora_usb" and self._lora_backend == "ARDUROVER":
            status = getattr(self._link, "remote_status", None)
            if snap.mode != "MANUAL" or status is None or not status.fresh(time.monotonic()):
                return False, "Select MANUAL and wait for fresh LoRa rover status."
            self._lora_stop_baseline = (status.boot, status.stops)
        if settings.link_mode == "lora_usb" and self._lora_backend == "DIRECT" and snap.mode not in ("DIRECT", "FAILSAFE"):
            return False, "Select DIRECT on the motor controller and wait for its heartbeat."
        with self._lock:
            self._lora_direct_deadline = time.monotonic() + 2.5 if settings.link_mode == "lora_usb" and (snap.mode == "FAILSAFE" or self._lora_backend == "ARDUROVER") else None
            self._failsafe_latched = False
            self._control_enabled = True
            self._enabled_controller_session = frame.session
            if settings.link_mode == "elrs_serial":
                self._owns_elrs_override = True
                self._last_elrs_tick = time.monotonic()
                self._next_elrs_send = 0.0
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
            return self._disable_control()

    def _disable_control(self):
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
        if self._settings.link_mode == "elrs_serial":
            return self._send_neutral_then_release() if self._owns_elrs_override else True
        if was_enabled or link_available:
            if was_enabled:
                logger.info("PC control disabled; issuing neutral/release")
            self._send_neutral_then_release()

    def arm(self):
        with self._send_lock:
            return self._arm()

    def _arm(self):
        if self._settings.link_mode == "elrs_backpack":
            return False, "Use the ELRS handset to arm; Backpack is telemetry-only."
        self._refresh_control_source()
        with self._lock:
            snap = self._snapshot
            frame = self._control_frame
            axis_count = self._axis_count
            settings = AppSettings(**vars(self._settings)).validate()
            conn = self._link
            control_mav = self._control_mav
        decision = can_arm(
            settings=settings,
            link_state=self._elrs_link_state(snap, settings),
            frame=frame,
            axis_count=axis_count,
            now=time.monotonic(),
        )
        if not decision.allowed:
            return False, decision.message
        if conn is None or control_mav is None:
            return False, "Vehicle link is not connected."
        if settings.link_mode == "lora_usb":
            required = "MANUAL" if self._lora_backend == "ARDUROVER" else "DIRECT"
            if not snap.control_enabled or snap.mode != required:
                return False, f"Enable LoRa PC Control in {required} mode before arming."
            if self._lora_backend == "ARDUROVER":
                status = getattr(conn, "remote_status", None)
                if (status is None or not status.fresh(time.monotonic()) or not status.ready
                        or status.owned != 3 or self._lora_stop_baseline != (status.boot, status.stops)):
                    return False, "Wait for rover neutral acquisition before arming."
        return self._send_arm_command(True)

    def disarm(self):
        with self._send_lock:
            if self._settings.link_mode in ("elrs_serial", "lora_usb"):
                self.disable_control()
            return self._send_arm_command(False)

    def _send_arm_command(self, arm: bool):
        if self._settings.link_mode == "elrs_backpack":
            return False, "Use the ELRS handset to arm/disarm; Backpack is telemetry-only."
        with self._lock:
            snap = self._snapshot
            conn = self._link
            control_mav = self._control_mav
            sysid = snap.vehicle_system
            compid = snap.vehicle_component
        if self._elrs_link_state(snap, self._settings) != LinkState.CONNECTED or conn is None or control_mav is None or sysid is None:
            return False, "Vehicle link is not connected."
        try:
            from pymavlink.dialects.v10 import ardupilotmega as mavlink1
            with self._send_lock:
                if arm and self._settings.link_mode == "lora_usb":
                    if not self._send_override(PWM_NEUTRAL, PWM_NEUTRAL):
                        self.disable_control()
                        return False, "Neutral send failed; LoRa ARM cancelled."
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

    @staticmethod
    def _serial_port(settings):
        return settings.lora_port if settings.link_mode == "lora_usb" else settings.elrs_port

    def _configure_link_target(self, link, settings: AppSettings):
        """Configure outbound writes on the already-bound receive socket."""
        if hasattr(link, "destination"):
            return  # USB routing is fixed when the port opens.
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
        if hasattr(link, "destination"):
            return link.destination is not None
        with self._lock:
            target_host = self._settings.target_host.strip()
        if target_host:
            return True
        return getattr(link, "last_address", None) is not None

    def _run(self):
        link = None
        try:
            from pymavlink import mavutil
            with self._lock:
                settings = AppSettings(**vars(self._settings)).validate()

            if settings.link_mode == "elrs_backpack":
                from .backpack import BackpackTelemetry
                link = BackpackTelemetry(settings.backpack_host, settings.backpack_listen_port,
                                         settings.backpack_target_port, settings.bind_host)
            elif settings.link_mode == "telerc_udp":
                link = mavutil.mavlink_connection(
                    f"udpin:{settings.bind_host}:{settings.listen_port}",
                    source_system=255, source_component=190, autoreconnect=True,
                )
            else:
                from .transport import VehicleLoRa, VehicleSerial
                port = self._serial_port(settings)
                if not port:
                    raise RadioConnectionError("Select the radio COM port before connecting.")
                if settings.link_mode == "lora_usb":
                    link = VehicleLoRa(port)
                    board = link.require_active_base(self._stop)
                    self._lora_backend = board.backend
                    self._lora_stop_baseline = None
                    if board.chip != 1262:
                        raise RadioConnectionError("Select a LilyGO T3S3 SX1262 BASE for this profile.")
                else:
                    link = VehicleSerial(port)
                if self._stop.is_set():
                    return
            if settings.link_mode != "lora_usb":
                self._lora_backend = "DIRECT"
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
                self._bound_mode = settings.link_mode
                self._bound_serial = self._serial_port(settings)
                self._control_enabled = False
                self._owns_elrs_override = False
                self._last_elrs_tick = None
                self._next_elrs_send = 0.0
                if settings.link_mode == "elrs_serial":
                    self._control_frame = None
                    self._axis_count = None
                self._bridge_registered = False
                self._snapshot = MavlinkSnapshot(
                    running=True,
                    state=LinkState.CONNECTING,
                    opened_at=time.monotonic(),
                )

            logger.info("MAVLink %s opened", settings.link_mode)

            next_hb = 0.0
            next_control = 0.0
            while not self._stop.is_set():
                now = time.monotonic()
                # A continuous malformed USB stream must not starve watchdogs.
                # Expire the old heartbeat before accepting a recovery packet.
                # Otherwise a worker stall/outage ending with a heartbeat could
                # hide the gap and leave previously enabled control active.
                self._refresh_link_state(now)
                msg = link.recv_msg() if settings.link_mode in ("elrs_serial", "elrs_backpack") else link.recv_match(blocking=False)
                now = time.monotonic()
                self._refresh_link_state(now)
                if msg is not None and msg.get_type() != "BAD_DATA":
                    self._handle_message(msg, now)

                if now >= next_hb:
                    if settings.link_mode == "elrs_backpack":
                        self._send_backpack_registration(now)
                    else:
                        self._send_lora_discovery()
                        self._send_gcs_heartbeat()
                    next_hb = now + 1.0

                self._refresh_link_state(now)

                if now >= next_control:
                    self._control_tick(now)
                    # ELRS safety runs at 20 Hz; drive writes remain at 5 Hz.
                    next_control = now + 1.0 / (10.0 if settings.link_mode == "lora_usb" else self.SEND_HZ)

                time.sleep(0.005)

        except Exception as exc:
            with self._lock:
                settings = AppSettings(**vars(self._settings)).validate()
                if settings.link_mode == "elrs_serial" and self._control_enabled:
                    self._failsafe_latched = True
                self._control_enabled = False
                self._snapshot = replace(
                    self._snapshot,
                    running=False,
                    state=LinkState.DISCONNECTED,
                    control_enabled=False,
                    failsafe_latched=self._failsafe_latched,
                    error=(describe_serial_error(exc, self._serial_port(settings), "open" if link is None else "communicate")
                           if settings.link_mode in ("elrs_serial", "lora_usb") and not isinstance(exc, RadioConnectionError)
                           else describe_mavlink_start_error(exc, settings.listen_port)),
                )
            if settings.link_mode == "telerc_udp":
                logger.exception("MAVLink worker stopped")
            else:
                logger.error("%s", self.snapshot().error)

        finally:
            self._send_neutral_then_release()
            self._send_lora_disconnect()
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
                    last_heartbeat=None, heartbeat_age=None,
                    vehicle_system=None, vehicle_component=None, armed=False,
                    control_enabled=False,
                    steer_pwm=PWM_NEUTRAL, throttle_pwm=PWM_NEUTRAL,
                )
                self._control_frame = None
                self._axis_count = None

    def _handle_message(self, msg, now: float):
        typ = msg.get_type()
        with self._lock:
            snap = replace(
                self._snapshot,
                rx_messages=self._snapshot.rx_messages + 1,
            )

            # Display telemetry is accepted only from the locked autopilot.
            # It never creates or renews a heartbeat and never changes control.
            if typ in ("GPS_RAW_INT", "GLOBAL_POSITION_INT", "SYS_STATUS"):
                if (snap.vehicle_system, snap.vehicle_component) != (msg.get_srcSystem(), msg.get_srcComponent()):
                    self._snapshot = snap
                    return
                if typ == "GPS_RAW_INT":
                    fix = int(getattr(msg, "fix_type", 0))
                    sats = int(getattr(msg, "satellites_visible", 255))
                    snap = replace(snap, gps_fix=fix, gps_timestamp=now, satellites=None if sats == 255 else sats)
                    lat, lon = msg.lat / 1e7, msg.lon / 1e7
                    if fix >= 3 and -90 <= lat <= 90 and -180 <= lon <= 180:
                        speed = getattr(msg, "vel", 65535)
                        heading = getattr(msg, "cog", 65535)
                        snap = replace(snap, latitude=lat, longitude=lon, position_timestamp=now,
                                       speed=None if speed == 65535 else speed / 100,
                                       heading=None if heading == 65535 else heading / 100)
                elif (typ == "GLOBAL_POSITION_INT" and snap.gps_fix >= 3
                      and snap.gps_timestamp is not None and 0 <= now - snap.gps_timestamp <= 5):
                    lat, lon = msg.lat / 1e7, msg.lon / 1e7
                    if -90 <= lat <= 90 and -180 <= lon <= 180:
                        import math
                        heading = getattr(msg, "hdg", 65535)
                        snap = replace(snap, latitude=lat, longitude=lon, position_timestamp=now,
                                       speed=math.hypot(msg.vx, msg.vy) / 100,
                                       heading=None if heading == 65535 else heading / 100)
                elif typ == "SYS_STATUS":
                    voltage = getattr(msg, "voltage_battery", 65535)
                    remaining = getattr(msg, "battery_remaining", -1)
                    snap = replace(snap, voltage=None if voltage == 65535 else voltage / 1000,
                                   battery_remaining=remaining if 0 <= remaining <= 100 else None,
                                   battery_timestamp=now)
                self._snapshot = snap
                return

            if typ == "HEARTBEAT" and self._settings.link_mode in ("elrs_serial", "elrs_backpack"):
                # Only the ArduRover autopilot can claim this rover session.
                if (getattr(msg, "type", None) != 10 or getattr(msg, "autopilot", None) != 3
                        or msg.get_srcSystem() in (0, 255) or msg.get_srcComponent() != 1):
                    self._snapshot = replace(snap, ignored_heartbeats=snap.ignored_heartbeats + 1)
                    return

            if (typ == "HEARTBEAT" and self._settings.link_mode == "lora_usb"
                    and ((msg.get_srcSystem(), msg.get_srcComponent()) != (1, 1)
                         or getattr(msg, "type", None) != 10
                         or getattr(msg, "autopilot", None) != (3 if self._lora_backend == "ARDUROVER" else 0))):
                self._snapshot = replace(snap, ignored_heartbeats=snap.ignored_heartbeats + 1)
                return
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

                if self._settings.link_mode == "lora_usb" and self._lora_backend == "DIRECT":
                    # Only the TeleRC motor heartbeat defines these custom modes.
                    mode = {0: "FAILSAFE", 1: "DIRECT", 2: "AUTOPILOT"}.get(getattr(msg, "custom_mode", None), "UNKNOWN") if getattr(msg, "autopilot", None) == 0 and getattr(msg, "type", None) == 10 else "UNKNOWN"
                    if mode == "DIRECT":
                        self._lora_direct_deadline = None
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
                    error=snap.error if self._failsafe_latched else "",
                )
                if first_lock:
                    logger.info(
                        "Locked MAVLink vehicle identity sys=%s comp=%s",
                        src_sys,
                        src_comp,
                    )

            self._snapshot = snap

    def _refresh_link_state(self, now: float):
        with self._send_lock:
            return self._serialized_refresh_link_state(now)

    def _serialized_refresh_link_state(self, now: float):
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
                snap = replace(snap,
                    steer_pwm=PWM_NEUTRAL, throttle_pwm=PWM_NEUTRAL,
                    error=f"Control stopped: rover heartbeat missing for {age:.2f}s "
                          f"(limit {settings.heartbeat_timeout:.2f}s). "
                          "After recovery, re-enable PC Control manually; reconnect only if the link stays down.")

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
        if self._settings.link_mode == "elrs_backpack":
            return
        self._refresh_control_source()
        with self._lock:
            settings = AppSettings(**vars(self._settings)).validate()
            frame = self._control_frame
            axis_count = self._axis_count
            enabled = self._control_enabled
            snap = self._snapshot
            if settings.link_mode == "elrs_serial":
                now = time.monotonic()
            previous_tick = self._last_elrs_tick
            if enabled and settings.link_mode == "elrs_serial":
                self._last_elrs_tick = now

        if not enabled:
            return

        decision = can_continue_control(
            settings=settings,
            link_state=self._elrs_link_state(snap, settings),
            frame=frame,
            axis_count=axis_count,
            now=now,
        )
        if (frame is not None and self._enabled_controller_session is not None
                and frame.session != self._enabled_controller_session):
            from .field_safety import SafetyDecision
            decision = SafetyDecision(False, "controller_reconnected",
                                      "Controller reconnected or changed; re-enable manually at neutral.")
        elif not decision.allowed and decision.code == "controller_stale":
            from .field_safety import SafetyDecision
            age = "missing" if frame is None else f"{max(0.0, now - frame.timestamp):.3f}s old"
            decision = SafetyDecision(False, decision.code,
                                      f"Controller input missing or stale: {age} (limit {settings.controller_timeout:.3f}s).")
        if (settings.link_mode == "elrs_serial" and previous_tick is not None
                and now - previous_tick > settings.controller_timeout):
            from .field_safety import SafetyDecision
            decision = SafetyDecision(False, "worker_delayed", "Control worker missed its watchdog deadline.")
        initializing_lora = (
            settings.link_mode == "lora_usb" and snap.mode == "FAILSAFE"
            and self._lora_direct_deadline is not None and now < self._lora_direct_deadline
            and frame is not None and frame.neutral and abs(frame.steering) <= .05
        )
        if settings.link_mode == "lora_usb" and self._lora_backend == "ARDUROVER":
            from .field_safety import SafetyDecision
            status = getattr(self._link, "remote_status", None)
            acquiring = self._lora_direct_deadline is not None
            valid = status is not None and status.fresh(now)
            if valid:
                with self._lock:
                    self._snapshot = replace(self._snapshot, radio_status=status.describe())
            if not valid:
                decision = SafetyDecision(False, "lora_status_stale", "LoRa rover status missing for 500 ms.")
            elif self._lora_stop_baseline != (status.boot, status.stops):
                decision = SafetyDecision(False, "lora_rover_stopped", status.describe() + "; re-enable manually at neutral.")
            elif snap.mode != "MANUAL":
                decision = SafetyDecision(False, "lora_fc_mode", "ArduRover left MANUAL mode.")
            elif acquiring and status.ready and status.owned == 3:
                self._lora_direct_deadline = None
                acquiring = False
            elif acquiring and now >= self._lora_direct_deadline:
                decision = SafetyDecision(False, "lora_acquire_timeout", "LoRa rover did not accept neutral within 2.5 seconds.")
            elif not acquiring and (not status.ready or status.owned != 3):
                decision = SafetyDecision(False, "lora_ownership_lost", "LoRa rover released control; re-enable manually at neutral.")
            initializing_lora = acquiring
        if settings.link_mode == "lora_usb" and self._lora_backend == "DIRECT" and snap.mode != "DIRECT" and not initializing_lora:
            from .field_safety import SafetyDecision
            decision = SafetyDecision(False, "lora_mode", "LoRa motor controller left DIRECT mode.")
        if not decision.allowed:
            with self._lock:
                self._control_enabled = False
                self._failsafe_latched = True
                self._snapshot = replace(
                    self._snapshot,
                    control_enabled=False,
                    failsafe_latched=True,
                    steer_pwm=PWM_NEUTRAL, throttle_pwm=PWM_NEUTRAL,
                    error=f"Control disabled by fail-safe: {decision.message}",
                )
            logger.error("PC control fail-safe: %s", decision.message)
            self._send_neutral_then_release()
            return

        if settings.link_mode == "elrs_serial":
            if now < self._next_elrs_send:
                return
            # Send only the newest input, never catch up a missed command burst.
            self._next_elrs_send = now + .2

        steer = PWM_NEUTRAL if initializing_lora else normalized_to_pwm(frame.steering, 1.0)
        throttle = PWM_NEUTRAL if initializing_lora else normalized_to_pwm(
            apply_sensitivity(frame.throttle, settings.throttle_sensitivity),
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
                    steer_pwm=PWM_NEUTRAL, throttle_pwm=PWM_NEUTRAL,
                    error="Control disabled: RC override transmission failed.",
                )
            self._send_neutral_then_release()
            if settings.link_mode == "elrs_serial":
                raise OSError("ELRS RC override USB write failed; reconnect manually.")

    def _send_lora_discovery(self):
        with self._send_lock:
            if self._bound_mode == "lora_usb" and self._link and not self._stop.is_set():
                self._link.write(b"TELERC_DISCOVER_V1")
                self._bridge_registered = True

    def _send_lora_disconnect(self):
        with self._send_lock:
            if self._bound_mode == "lora_usb" and self._link and self._bridge_registered:
                try:
                    self._link.write(b"TELERC_DISCONNECT_V1")
                    # Allow the native USB frame to drain before port close.
                    time.sleep(.02)
                except OSError:
                    logger.warning("LoRa disconnect could not be delivered.")
                self._bridge_registered = False

    def _send_gcs_heartbeat(self):
        if self._settings.link_mode == "elrs_backpack":
            return
        with self._lock:
            conn = self._link
            control_mav = self._control_mav
        if conn is None or control_mav is None or not self._has_send_destination(conn):
            return
        try:
            from pymavlink.dialects.v10 import ardupilotmega as mavlink1
            with self._send_lock:
                if self._stop.is_set():
                    return
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
            if self._settings.link_mode == "elrs_serial":
                raise OSError(f"ELRS heartbeat send failed: {exc}") from exc
            with self._lock:
                self._snapshot = replace(
                    self._snapshot,
                    error=f"GCS heartbeat send failed: {exc}",
                )

    def _send_override(self, steer_pwm: int, throttle_pwm: int) -> bool:
        if self._settings.link_mode == "elrs_backpack":
            return False
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
        if self._settings.link_mode == "elrs_backpack":
            return True
        with self._lock:
            conn = self._link
            control_mav = self._control_mav
            elrs = self._settings.link_mode == "elrs_serial"
            owned = self._owns_elrs_override
        if elrs and not owned:
            return True
        if conn is None or control_mav is None:
            return False
        if elrs:
            try:
                conn.discard_pending_output()
            except Exception as exc:
                logger.warning("ELRS queue could not be cleared: %s", exc)
                with self._lock:
                    self._snapshot = replace(self._snapshot, error=(self._snapshot.error +
                        f" ELRS USB queue could not be cleared: {exc}. Verify rover failsafe.").strip())
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
                time.sleep(0.02)

            except Exception as exc:
                logger.warning(
                    "Neutral/release attempt failed: %s",
                    exc,
                )
        if elrs:
            with self._lock:
                if delivered:
                    self._owns_elrs_override = False
                else:
                    reason = "Neutral/release USB writes failed; verify rover failsafe and handover."
                    self._snapshot = replace(self._snapshot, error=(self._snapshot.error + " " + reason).strip())
        return delivered

    def _send_backpack_registration(self, now):
        """Runs at 1 Hz regardless of heartbeat freshness; never grants control."""
        with self._send_lock:
            if self._stop.is_set() or self._bound_mode != "elrs_backpack" or self._control_mav is None:
                return
            try:
                self._control_mav.ping_send(int(now * 1_000_000), 0, 0, 0)
                with self._lock:
                    self._snapshot = replace(self._snapshot, tx_messages=self._snapshot.tx_messages + 1)
            except OSError:
                # A temporary Wi-Fi route loss must not freeze registration
                # recovery. The socket retains its fixed peer and next 1 Hz try.
                with self._lock:
                    self._snapshot = replace(self._snapshot, error="Backpack registration waiting — check Wi-Fi and peer address.")




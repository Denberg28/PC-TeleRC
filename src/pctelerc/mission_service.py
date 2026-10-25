"""One mission worker, one rover, no automatic reconnect or start replay."""

from dataclasses import replace
import queue
import threading
import time

from PySide6.QtCore import QObject, Signal
from .core import LinkState
from .mavlink import MavlinkSnapshot
from .mission_protocol.client import Client, compare, fingerprint
from .mission_transport import MissionUSB
from .firmware_profiles import route_interrupted


ARM_ACK_TIMEOUT = 12


class Cancelled(RuntimeError):
    pass


class Events(QObject):
    message = Signal(str)
    snapshot = Signal(object)
    ready = Signal(bool)
    verified = Signal(str)
    busy = Signal(bool)
    phase = Signal(str)
    capabilities = Signal(object)
    stored_mission = Signal(object)


class MissionService:
    """The UI owns a 2-second lease; a stalled/closed UI cannot sustain a mission link."""

    def __init__(self, transport_factory=MissionUSB, *, fleet_actions=False, operation_gate=None):
        self.events = Events()
        self.transport_factory = transport_factory
        self.thread = None
        self.jobs = queue.Queue(maxsize=1)
        self.stop_event = threading.Event()
        self.hold_event = threading.Event()
        self.disarm_event = threading.Event()
        self.ui_at = time.monotonic()
        self.quiet_until = 0.0
        self.verified_digest = ""
        self.snapshot = MavlinkSnapshot()
        self.gps_at = 0.0
        self.stationary = []
        self.boot_ms = None
        self._gate = threading.RLock()
        self.capabilities = dict(relays=0, mask=0, firmware="")
        self.gps_boot = None
        self.phase = "Offline"
        self._confirmed = False
        self.fleet_actions = fleet_actions
        self.operation_gate = operation_gate
        self._owns_operation = False

    def _phase(self, value):
        self.phase = value
        self.events.phase.emit(value)

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def pulse(self):
        self.ui_at = time.monotonic()

    def connect(self, port, rover):
        if self.running or time.monotonic() < self.quiet_until:
            raise RuntimeError(
                "Close the old mission session and wait 5 seconds before connecting"
            )
        if not port.strip() or not 1 <= rover <= 20:
            raise ValueError("Select the BASE COM port and rover ID 1–20")
        self.stop_event.clear()
        self.hold_event.clear()
        self.disarm_event.clear()
        self._confirmed = False
        self.capabilities = dict(relays=0, mask=0, firmware="")
        self.pulse()
        self.jobs = queue.Queue(maxsize=1)
        self.thread = threading.Thread(
            target=self._run, args=(port, rover), daemon=True, name="TeleRC-mission"
        )
        self._phase("Connecting")
        self.thread.start()

    def close(self):
        with self._gate:
            self.stop_event.set()
            self._confirmed = False
        if self.thread:
            self.thread.join(timeout=1)
        return not self.running

    def submit(self, action, items, continue_on_loss=False, auxiliary=False):
        if not self.running or self.stop_event.is_set():
            raise RuntimeError("Connect the addressed mission BASE first")
        if action not in (("upload", "start", "arm", "disarm", "inspect") if self.fleet_actions else ("upload", "start", "inspect")):
            raise ValueError("Unknown mission action")
        # Deep immutable job snapshot independent of subsequent GUI edits.
        import copy

        with self._gate:
            self._check()
            if not self._confirmed:
                raise RuntimeError("Wait for a fresh addressed rover heartbeat before mission actions")
            if self.operation_gate is not None:
                if not self.operation_gate.acquire(blocking=False):
                    raise RuntimeError("Another rover operation is in progress; fleet monitoring continues")
                self._owns_operation = True
            try:
                self.jobs.put_nowait(
                    (action, copy.deepcopy(items), bool(continue_on_loss), bool(auxiliary))
                )
            except Exception:
                self._release_operation()
                raise

    def _release_operation(self):
        with self._gate:
            if self._owns_operation:
                self._owns_operation = False
                self.operation_gate.release()

    def hold(self):
        with self._gate:
            self.hold_event.set()

    def request_disarm(self):
        with self._gate:
            self._check(allow_hold=True)
            if not self.fleet_actions or not self._confirmed:
                raise RuntimeError('Connect a fleet-capable rover before DISARM')
            self.disarm_event.set()
            self.hold_event.set()

    def _base_status(self, text):
        self.events.message.emit("BASE: " + text)
        if self.fleet_actions and text.startswith(('Fleet capacity;', 'Incompatible rover;', 'Host lease expired;', 'BUSY;', 'Command queue full', 'RF fault;', 'RF OFF;')):
            self.verified_digest = ""
            self.events.verified.emit("")
            raise RuntimeError(text)
        if route_interrupted(text):
            self.verified_digest = ""
            self.events.verified.emit("")
            # Initial discovery is expected. Once an addressed FC has confirmed
            # this session, never carry verification or queued work across loss.
            if self._confirmed:
                self._confirmed = False
                while not self.jobs.empty():
                    self.jobs.get_nowait()
                raise RuntimeError("LoRa route interrupted; state UNKNOWN. Reconnect and re-upload; no automatic resume")
            self._phase("Finding rover · " + text[:70])

    def _check(self, *, allow_hold=False):
        if self.stop_event.is_set() or time.monotonic() - self.ui_at > 2:
            raise Cancelled(
                "Mission connection closed or UI stalled; state UNKNOWN. FC loss policy applies."
            )
        last = self.snapshot.last_heartbeat
        if last is not None and time.monotonic() - last > 5:
            raise RuntimeError("Telemetry lost; state unknown. Reconnect manually.")
        if self.hold_event.is_set() and not allow_hold:
            raise Cancelled("Operator requested HOLD; current operation cancelled")

    def _observe(self, m, rover):
        now = time.monotonic()
        s = self.snapshot
        if m.get_srcSystem() != rover or m.get_srcComponent() != 1:
            return
        kind = m.get_type()
        if kind == "HEARTBEAT" and m.type == 10 and m.autopilot == 3:
            s = replace(
                s,
                running=True,
                state=LinkState.CONNECTED,
                last_heartbeat=now,
                heartbeat_age=0,
                vehicle_system=rover,
                vehicle_component=1,
                armed=bool(m.base_mode & 128),
                mode={0: "MANUAL", 4: "HOLD", 10: "AUTO"}.get(
                    m.custom_mode, str(m.custom_mode)
                ),
            )
            if (
                self.phase in ("AUTO · running", "AUTO · monitor only")
                and (m.custom_mode != 10 or not s.armed)
            ):
                self._phase(
                    "RC/FC takeover · monitor only"
                    if s.armed
                    else "Disarmed · monitor only"
                )
        elif kind == "GPS_RAW_INT":
            if self.fleet_actions and (not m.time_usec or (self.gps_boot is not None and m.time_usec<=self.gps_boot)):
                return
            if m.time_usec and self.gps_boot == m.time_usec:
                return
            self.gps_boot = m.time_usec
            self.gps_at = now
            s = replace(
                s,
                gps_fix=m.fix_type,
                satellites=m.satellites_visible,
                gps_timestamp=now,
            )
        elif kind == "GLOBAL_POSITION_INT":
            if self.boot_ms is not None and m.time_boot_ms == self.boot_ms:
                return
            if (
                self.boot_ms is not None
                and (m.time_boot_ms - self.boot_ms) & 0xFFFFFFFF > 0x80000000
            ):
                self.verified_digest = ""
                self.events.verified.emit("")
                raise RuntimeError("FC reboot detected; close and re-upload disarmed")
            self.boot_ms = m.time_boot_ms
            if (
                not -850000000 <= m.lat <= 850000000
                or not -1800000000 <= m.lon <= 1800000000
            ):
                raise RuntimeError("FC position is outside valid map coordinates")
            speed = (m.vx * m.vx + m.vy * m.vy) ** 0.5 / 100
            s = replace(
                s,
                latitude=m.lat / 1e7,
                longitude=m.lon / 1e7,
                position_timestamp=now,
                speed=speed,
                heading=None if m.hdg == 65535 else m.hdg / 100,
            )
            self.stationary = (
                ([self.stationary[0], now] if self.stationary else [now])
                if speed <= 0.1
                else []
            )
        elif kind in ("MISSION_CURRENT", "MISSION_ITEM_REACHED"):
            self.events.message.emit(f"{kind}: row {m.seq}")
        elif kind == "STATUSTEXT":
            self.events.message.emit(str(m.text)[:120])
        self.snapshot = s
        if kind in ("HEARTBEAT", "GPS_RAW_INT", "GLOBAL_POSITION_INT"):
            self.events.snapshot.emit(s)

    def _auxiliary(self, c, items, allowed):
        outputs = {}
        for row in items[1:]:
            if row["command"] == 183:
                channel, pwm = row["params"][:2]
                channel = int(channel)
                if channel in range(5, 9):
                    raise RuntimeError("M5–M8 are reserved for motors")
                outputs.setdefault(channel, []).append(pwm)
        if outputs and not allowed:
            raise RuntimeError(
                "Auxiliary mission outputs require explicit cutoff/mapping acceptance"
            )
        for channel, values in outputs.items():
            if self.capabilities["firmware"] and not self.capabilities["mask"] & (
                1 << (channel - 1)
            ):
                raise RuntimeError(
                    f"Output {channel} is not permitted by this firmware profile"
                )
            if c.parameter(f"SERVO{channel}_FUNCTION") != 0:
                raise RuntimeError(
                    f"SERVO{channel}_FUNCTION must be 0; motor/RC outputs forbidden"
                )
            low, high = (
                c.parameter(f"SERVO{channel}_MIN"),
                c.parameter(f"SERVO{channel}_MAX"),
            )
            if not all(low <= pwm <= high for pwm in values):
                raise RuntimeError(f"Output {channel} PWM outside verified FC limits")
            # WPL imports have no ON/OFF metadata: require explicit same safe end.
            if values[0] != values[-1]:
                raise RuntimeError(
                    f"Output {channel} must begin and end at the same reviewed OFF PWM"
                )

    def _navigation_ready(self, c):
        # Fresh real GPS and two stationary position reports, never map/cache data.
        end = time.monotonic() + 8 + 2 * self.capabilities["relays"]
        self.stationary = []
        self.gps_at = 0
        while time.monotonic() < end:
            c.recv(["GPS_RAW_INT", "GLOBAL_POSITION_INT", "HEARTBEAT"], 0.3)
            s = self.snapshot
            now = time.monotonic()
            if (
                s.gps_fix >= 3
                and now - self.gps_at <= 5
                and s.position_timestamp is not None
                and now - s.position_timestamp <= 5
                and len(self.stationary) == 2
                and self.stationary[-1] - self.stationary[0] >= 0.25
            ):
                return
        raise RuntimeError(
            "START blocked: need fresh 3D GPS and two stationary position reports"
        )

    def _arm_action(self, c, arm, digest, policy, *, held=False):
        """Explicit fleet-only normal arming, no force value and no retries."""
        if arm:
            if self.verified_digest != digest or c.start_attempted:
                raise RuntimeError("Upload and verify this rover's exact mission before ARM")
            c.hold()
            c.heartbeat(disarmed=True)
            if c.parameter('ARMING_CHECK') != 1 or c.parameter('ARMING_REQUIRE') <= 0:
                raise RuntimeError("ARM blocked: enable FC arming requirements and full pre-arm checks deliberately")
            c.loss_policy(policy, min_timeout=3+2*self.capabilities['relays'])
        else:
            self.verified_digest = ""
            self.events.verified.emit("")
            if not held:
                c.hold()
        self._navigation_ready(c)
        m = c.heartbeat()
        if m.custom_mode not in (0,4) or (arm and m.custom_mode!=4):
            raise RuntimeError("ARM requires confirmed stationary HOLD; FC mode changed")
        if bool(m.base_mode & 128) == arm:
            if arm:
                raise RuntimeError("Rover already armed elsewhere; ARM is not repeated")
            self._phase('Disarmed · HOLD' if m.custom_mode==4 else 'Disarmed · monitor only')
            return
        c.check()
        c.link.mav.command_long_send(c.rover,1,400,0,1 if arm else 0,0,0,0,0,0,0)
        accepted = False
        end = time.monotonic()+ARM_ACK_TIMEOUT
        while time.monotonic() < end:
            m = c.recv(['COMMAND_ACK','HEARTBEAT'],.3)
            if m is None:
                continue
            if m.get_type() == 'COMMAND_ACK' and m.command == 400:
                if getattr(m,'target_system',255) not in (0,255) or getattr(m,'target_component',190) not in (0,190):
                    continue
                if m.result not in (0,5):
                    raise RuntimeError(f"FC refused {'ARM' if arm else 'DISARM'} ({m.result}); no retry")
                accepted |= m.result == 0
            if accepted and m.get_type() == 'HEARTBEAT' and bool(m.base_mode & 128) == arm:
                if arm and m.custom_mode not in (0,4):
                    raise RuntimeError('FC mode changed during ARM; inspect live state; no START is queued')
                self._phase('Armed · not started' if arm else 'Disarmed · HOLD' if m.custom_mode==4 else 'Disarmed · monitor only')
                return
        raise RuntimeError('ARM/DISARM state UNKNOWN; inspect live FC state; command is not retried')

    def _run(self, port, rover):
        link = None
        failure = None
        self.verified_digest = ""
        self.events.verified.emit("")
        self.snapshot = MavlinkSnapshot(
            running=True, state=LinkState.CONNECTING, vehicle_system=rover
        )
        self.gps_at = 0
        self.boot_ms = None
        self.gps_boot = None
        self.stationary = []
        try:
            link = self.transport_factory(port, rover)
            link.gate = self._gate
            c = Client("", rover, link=link)
            c.check = self._check
            c.log = lambda *a: self.events.message.emit(" ".join(map(str, a)))
            link.check = self._check
            link.status = self._base_status
            if hasattr(link, "handshake"):
                self.capabilities = link.handshake()
                self.events.capabilities.emit(dict(self.capabilities, profile=getattr(link, 'profile', None)))
            if self.fleet_actions and not getattr(link, 'fleet_authority', False):
                raise RuntimeError('Fleet-capable BASE/ROVER firmware is required for addressed ARM/DISARM')
            original_recv = link.recv_match

            def receive(*args, **kwargs):
                m = original_recv(*args, **kwargs)
                if m is not None:
                    self._observe(m, rover)
                return m

            link.recv_match = receive
            c.heartbeat()
            self._confirmed = True
            self._phase(
                "AUTO · monitor only" if self.snapshot.mode == "AUTO" else "Ready"
            )
            self.events.ready.emit(True)
            self.events.message.emit(
                f"ROVER {rover} · mission connected · no automatic ARM/START"
            )
            while not self.stop_event.is_set():
                self._check(allow_hold=True)
                if self.hold_event.is_set():
                    # HOLD cancels pending START/upload. It never retries START.
                    while not self.jobs.empty():
                        self.jobs.get_nowait()
                    c.check = lambda: self._check(allow_hold=True)
                    link.check = c.check
                    self.verified_digest = ""
                    self.events.verified.emit("")
                    self.events.busy.emit(True)
                    self._phase("Requesting HOLD")
                    try:
                        c.hold()
                        self._phase("HOLD confirmed")
                        if self.disarm_event.is_set():
                            self._phase('HOLD confirmed · checking disarm')
                            self._arm_action(c,False,'',False,held=True)
                    except Exception as exc:
                        self._phase("HOLD unconfirmed")
                        self.events.message.emit(
                            f"HOLD UNCONFIRMED: {exc}; use independent RC/physical stop"
                        )
                        raise
                    finally:
                        self.hold_event.clear()
                        self.disarm_event.clear()
                        c.check = self._check
                        link.check = self._check
                        self.events.busy.emit(False)
                try:
                    action, items, policy, aux = self.jobs.get_nowait()
                except queue.Empty:
                    try:
                        c.recv(
                            ["HEARTBEAT", "MISSION_CURRENT", "MISSION_ITEM_REACHED"],
                            0.15,
                        )
                    except Cancelled:
                        if self.hold_event.is_set() and not self.stop_event.is_set():
                            continue
                        raise
                    if time.monotonic() - c.hb_at > 5:
                        raise RuntimeError(
                            "TELEMETRY LOST; mission/stop state UNKNOWN; reconnect manually"
                        )
                    continue
                self.events.busy.emit(True)
                digest = fingerprint(items, rover) if action != "inspect" else ""
                fatal = False
                try:
                    if action == "inspect":
                        self._phase("Reading FC mission")
                        stored = c.download(allow_empty=True)
                        self._check()
                        self.events.stored_mission.emit(stored)
                        self._phase("FC mission retrieved · not start-authorized")
                        self.events.message.emit(f"Read {len(stored)} FC mission rows; draft unchanged")
                    elif action in ('arm','disarm'):
                        self._phase('Checking ARM' if action == 'arm' else 'HOLD → checking disarm')
                        self._arm_action(c,action == 'arm',digest,policy)
                    elif action == "upload":
                        self.verified_digest = ""
                        self.events.verified.emit("")
                        self._phase("Uploading")
                        c.heartbeat(disarmed=True)
                        c.loss_policy(
                            policy, min_timeout=3 + 2 * self.capabilities["relays"]
                        )
                        self._auxiliary(c, items, aux)
                        c.upload(items)
                        compare(items, c.download())
                        c.start_attempted = False
                        self.verified_digest = digest
                        self.events.verified.emit(digest)
                        self._phase("Verified · not started")
                        self.events.message.emit(
                            "Upload and full readback VERIFIED; mission NOT STARTED"
                        )
                    else:
                        if self.verified_digest != digest or c.start_attempted:
                            raise RuntimeError(
                                "Upload and verify this exact plan in this session before START"
                            )
                        self._phase("Checking START")
                        compare(items, c.download())
                        c.loss_policy(
                            policy, min_timeout=3 + 2 * self.capabilities["relays"]
                        )
                        self._auxiliary(c, items, aux)
                        self._navigation_ready(c)
                        # Local UI/hold checks and actual transmission share a gate.
                        # HOLD cannot be followed by a queued START after this check.
                        self.verified_digest = ""
                        self.events.verified.emit("")
                        c.start_once()
                        self._phase("AUTO · running")
                except Cancelled as exc:
                    self.verified_digest = ""
                    self.events.verified.emit("")
                    self.events.message.emit(str(exc))
                except Exception as exc:
                    fatal = True
                    self.verified_digest = ""
                    self.events.verified.emit("")
                    self.events.message.emit(f"ABORT / UNKNOWN: {exc}")
                    # Failed/unknown transactions must not keep a synthetic healthy
                    # GCS presence alive. Stop heartbeats; verified FC loss policy applies.
                    raise
                finally:
                    self.events.busy.emit(False)
                    if not fatal:
                        self._release_operation()
        except Exception as exc:
            failure = str(exc)
            self.events.message.emit(failure)
        finally:
            self.stop_event.set()
            self._confirmed = False
            if link is not None:
                try:
                    link.close()
                except Exception:
                    pass
            self._release_operation()
            self.quiet_until = time.monotonic() + 5
            self.verified_digest = ""
            self.events.verified.emit("")
            self.events.ready.emit(False)
            self.events.busy.emit(False)
            self.snapshot = replace(self.snapshot, running=False, state=LinkState.STALE)
            self.events.snapshot.emit(self.snapshot)
            self._phase("Offline · " + (failure[:90] if failure else "state unknown"))
            self.events.message.emit(
                "Mission link closed; motion/auxiliary state UNKNOWN. FC loss policy applies; no auto-resume."
            )

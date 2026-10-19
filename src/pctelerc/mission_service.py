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


class Cancelled(RuntimeError):
    pass


class Events(QObject):
    message = Signal(str)
    snapshot = Signal(object)
    ready = Signal(bool)
    verified = Signal(str)
    busy = Signal(bool)


class MissionService:
    """The UI owns a 2-second lease; a stalled/closed UI cannot sustain a mission link."""
    def __init__(self, transport_factory=MissionUSB):
        self.events = Events()
        self.transport_factory = transport_factory
        self.thread = None
        self.jobs = queue.Queue(maxsize=1)
        self.stop_event = threading.Event()
        self.hold_event = threading.Event()
        self.ui_at = time.monotonic()
        self.quiet_until = 0.
        self.verified_digest = ''
        self.snapshot = MavlinkSnapshot()
        self.gps_at = 0.
        self.stationary = []
        self.boot_ms = None
        self._gate = threading.RLock()

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def pulse(self):
        self.ui_at = time.monotonic()

    def connect(self, port, rover):
        if self.running or time.monotonic() < self.quiet_until:
            raise RuntimeError('Close the old mission session and wait 5 seconds before connecting')
        if not port.strip() or not 1 <= rover <= 20:
            raise ValueError('Select the BASE COM port and rover ID 1–20')
        self.stop_event.clear(); self.hold_event.clear(); self.pulse()
        self.jobs = queue.Queue(maxsize=1)
        self.thread = threading.Thread(target=self._run, args=(port, rover), daemon=True, name='TeleRC-mission')
        self.thread.start()

    def close(self):
        with self._gate:
            self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=1)
        return not self.running

    def submit(self, action, items, continue_on_loss=False, auxiliary=False):
        if not self.running or self.stop_event.is_set():
            raise RuntimeError('Connect the addressed mission BASE first')
        if action not in ('upload', 'start'):
            raise ValueError('Unknown mission action')
        # Deep immutable job snapshot independent of subsequent GUI edits.
        import copy
        self.jobs.put_nowait((action, copy.deepcopy(items), bool(continue_on_loss), bool(auxiliary)))

    def hold(self):
        with self._gate:
            self.hold_event.set()

    def _check(self, *, allow_hold=False):
        if self.stop_event.is_set() or time.monotonic()-self.ui_at > 2:
            raise Cancelled('Mission connection closed or UI stalled; state UNKNOWN. FC loss policy applies.')
        if self.hold_event.is_set() and not allow_hold:
            raise Cancelled('Operator requested HOLD; current operation cancelled')

    def _observe(self, m, rover):
        now = time.monotonic()
        s = self.snapshot
        if m.get_srcSystem() != rover or m.get_srcComponent() != 1:
            return
        kind = m.get_type()
        if kind == 'HEARTBEAT' and m.type == 10 and m.autopilot == 3:
            s = replace(s, running=True, state=LinkState.CONNECTED, last_heartbeat=now,
                        heartbeat_age=0, vehicle_system=rover, vehicle_component=1,
                        armed=bool(m.base_mode & 128), mode={0:'MANUAL',4:'HOLD',10:'AUTO'}.get(m.custom_mode,str(m.custom_mode)))
        elif kind == 'GPS_RAW_INT':
            self.gps_at = now
            s = replace(s, gps_fix=m.fix_type, satellites=m.satellites_visible, gps_timestamp=now)
        elif kind == 'GLOBAL_POSITION_INT':
            if self.boot_ms is not None and m.time_boot_ms < self.boot_ms:
                self.verified_digest = ''; self.events.verified.emit('')
                raise RuntimeError('FC reboot detected; close and re-upload disarmed')
            self.boot_ms = m.time_boot_ms
            speed = (m.vx*m.vx+m.vy*m.vy)**.5/100
            s = replace(s, latitude=m.lat/1e7, longitude=m.lon/1e7,
                        position_timestamp=now, speed=speed, heading=None if m.hdg==65535 else m.hdg/100)
            self.stationary = ([self.stationary[0], now] if self.stationary else [now]) if speed <= .1 else []
        elif kind in ('MISSION_CURRENT','MISSION_ITEM_REACHED'):
            self.events.message.emit(f'{kind}: row {m.seq}')
        elif kind == 'STATUSTEXT':
            self.events.message.emit(str(m.text)[:120])
        self.snapshot = s
        if kind in ('HEARTBEAT','GPS_RAW_INT','GLOBAL_POSITION_INT'):
            self.events.snapshot.emit(s)

    def _auxiliary(self, c, items, allowed):
        outputs = {}
        for row in items[1:]:
            if row['command'] == 183:
                channel, pwm = row['params'][:2]
                channel = int(channel)
                if channel in range(5,9):
                    raise RuntimeError('M5–M8 are reserved for motors')
                outputs.setdefault(channel, []).append(pwm)
        if outputs and not allowed:
            raise RuntimeError('Auxiliary mission outputs require explicit cutoff/mapping acceptance')
        for channel, values in outputs.items():
            if c.parameter(f'SERVO{channel}_FUNCTION') != 0:
                raise RuntimeError(f'SERVO{channel}_FUNCTION must be 0; motor/RC outputs forbidden')
            low, high = c.parameter(f'SERVO{channel}_MIN'), c.parameter(f'SERVO{channel}_MAX')
            if not all(low <= pwm <= high for pwm in values):
                raise RuntimeError(f'Output {channel} PWM outside verified FC limits')
            # WPL imports have no ON/OFF metadata: require explicit same safe end.
            if values[0] != values[-1]:
                raise RuntimeError(f'Output {channel} must begin and end at the same reviewed OFF PWM')

    def _navigation_ready(self, c):
        # Fresh real GPS and two stationary position reports, never map/cache data.
        end = time.monotonic()+8
        self.stationary = []
        self.gps_at = 0
        while time.monotonic() < end:
            c.recv(['GPS_RAW_INT','GLOBAL_POSITION_INT','HEARTBEAT'], .3)
            s = self.snapshot; now = time.monotonic()
            if (s.gps_fix >= 3 and now-self.gps_at <= 3 and s.position_timestamp is not None
                and now-s.position_timestamp <= 3 and len(self.stationary)==2
                and self.stationary[-1]-self.stationary[0] >= .25):
                return
        raise RuntimeError('START blocked: need fresh 3D GPS and two stationary position reports')

    def _run(self, port, rover):
        link = None
        self.verified_digest = ''; self.events.verified.emit('')
        self.snapshot = MavlinkSnapshot(running=True, state=LinkState.CONNECTING, vehicle_system=rover)
        self.gps_at = 0; self.boot_ms = None; self.stationary = []
        try:
            link = self.transport_factory(port, rover)
            link.gate = self._gate
            c = Client('', rover, link=link)
            c.check = self._check
            c.log = lambda *a: self.events.message.emit(' '.join(map(str,a)))
            link.check = self._check
            link.status = lambda text: self.events.message.emit('BASE: '+text)
            original_recv = link.recv_match
            def receive(*args, **kwargs):
                m = original_recv(*args, **kwargs)
                if m is not None:
                    self._observe(m, rover)
                return m
            link.recv_match = receive
            c.heartbeat()
            self.events.ready.emit(True)
            self.events.message.emit(f'ROVER {rover} · mission connected · no automatic ARM/START')
            while not self.stop_event.is_set():
                self._check(allow_hold=True)
                if self.hold_event.is_set():
                    # HOLD cancels pending START/upload. It never retries START.
                    while not self.jobs.empty():
                        self.jobs.get_nowait()
                    c.check = lambda: self._check(allow_hold=True)
                    link.check = c.check
                    self.verified_digest = ''; self.events.verified.emit('')
                    self.events.busy.emit(True)
                    try:
                        c.hold()
                    except Exception as exc:
                        self.events.message.emit(f'HOLD UNCONFIRMED: {exc}; use independent RC/physical stop')
                    finally:
                        self.hold_event.clear(); c.check = self._check; link.check = self._check
                        self.events.busy.emit(False)
                try:
                    action, items, policy, aux = self.jobs.get_nowait()
                except queue.Empty:
                    try:
                        c.recv(['HEARTBEAT','MISSION_CURRENT','MISSION_ITEM_REACHED'], .15)
                    except Cancelled:
                        if self.hold_event.is_set() and not self.stop_event.is_set():
                            continue
                        raise
                    if time.monotonic()-c.hb_at > 5:
                        raise RuntimeError('TELEMETRY LOST; mission/stop state UNKNOWN; reconnect manually')
                    continue
                self.events.busy.emit(True)
                digest = fingerprint(items, rover)
                try:
                    if action == 'upload':
                        self.verified_digest = ''; self.events.verified.emit('')
                        c.heartbeat(disarmed=True); c.loss_policy(policy); self._auxiliary(c,items,aux)
                        c.upload(items); compare(items,c.download())
                        c.start_attempted = False
                        self.verified_digest = digest; self.events.verified.emit(digest)
                        self.events.message.emit('Upload and full readback VERIFIED; mission NOT STARTED')
                    else:
                        if self.verified_digest != digest or c.start_attempted:
                            raise RuntimeError('Upload and verify this exact plan in this session before START')
                        compare(items,c.download()); c.loss_policy(policy); self._auxiliary(c,items,aux)
                        self._navigation_ready(c)
                        # Local UI/hold checks and actual transmission share a gate.
                        # HOLD cannot be followed by a queued START after this check.
                        c.start_once()
                except Cancelled as exc:
                    self.verified_digest = ''; self.events.verified.emit('')
                    self.events.message.emit(str(exc))
                except Exception as exc:
                    self.verified_digest = ''; self.events.verified.emit('')
                    self.events.message.emit(f'ABORT / UNKNOWN: {exc}')
                    # Failed/unknown transactions must not keep a synthetic healthy
                    # GCS presence alive. Stop heartbeats; verified FC loss policy applies.
                    raise
                finally:
                    self.events.busy.emit(False)
        except Exception as exc:
            self.events.message.emit(str(exc))
        finally:
            self.stop_event.set()
            if link is not None:
                try: link.close()
                except Exception: pass
            self.quiet_until = time.monotonic()+5
            self.verified_digest = ''; self.events.verified.emit('')
            self.events.ready.emit(False); self.events.busy.emit(False)
            self.snapshot = replace(self.snapshot, running=False, state=LinkState.STALE)
            self.events.snapshot.emit(self.snapshot)
            self.events.message.emit('Mission link closed; motion/auxiliary state UNKNOWN. FC loss policy applies; no auto-resume.')

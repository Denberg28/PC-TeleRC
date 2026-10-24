"""One native CDC owner, addressed virtual mission links, no reconnect or replay."""
from collections import deque
import threading
import time
from pymavlink.dialects.v20 import common
from .mission_protocol.usb_gateway import Decoder, encode
from .mission_transport import MissionUSB
from .firmware_profiles import FirmwareProfile


def fleet_capabilities(data):
    try:
        fields = data.decode('ascii').split(';')
        if fields.pop(0) != 'TF3':
            raise ValueError
        values = {}
        for field in fields:
            k, v = field.split('=')
            if k in values:
                raise ValueError
            values[k] = v
        if set(values) != {'fw', 'relays', 'mask', 'rovers', 'arm', 'budget'}:
            raise ValueError
        if values['fw'] != '0.5.0' or any(not values[k].isascii() or not values[k].isdigit() for k in values if k != 'fw'):
            raise ValueError
        if (int(values['relays']),int(values['rovers']),int(values['arm']),int(values['budget'])) != (2,20,1,2000):
            raise ValueError
        mask = int(values['mask'])
        if not 0 <= mask <= 65535 or mask & 0xf0:
            raise ValueError
        return dict(relays=2, mask=mask, firmware='0.5.0')
    except (UnicodeError, ValueError, KeyError):
        raise RuntimeError('Fleet BASE 0.5.0 required; upload the matching fleet BASE/ROVER sketches') from None


class FleetHub:
    def __init__(self, port, serial_factory=None):
        if serial_factory is None:
            import serial
            serial_factory = serial.Serial
        self.port = serial_factory(port=None,baudrate=115200,timeout=0,write_timeout=.1)
        self.port.dtr, self.port.rts, self.port.port = True, False, port
        self.lock = threading.RLock()
        self.send_lock = threading.Lock()
        self.operation = threading.Lock()
        self.channels = {}
        self.error = None
        self.stopped = threading.Event()
        self.capabilities = None
        self.decoder = Decoder()
        try:
            self.port.open()
            self.port.reset_input_buffer()
            self.port.reset_output_buffer()
            # Identify the BASE before any subscription, heartbeat or radio work.
            end, retry = time.monotonic()+3, 0
            while time.monotonic() < end:
                if time.monotonic() >= retry:
                    self._write(encode(1,3,b'FLEET'))
                    retry = time.monotonic()+.5
                for _, kind, data in self.decoder.feed(self.port.read(512)):
                    if kind == 3:
                        self.capabilities = fleet_capabilities(data)
                if self.capabilities is not None:
                    break
                time.sleep(.005)
            if self.capabilities is None:
                raise RuntimeError('No fleet BASE reply; select its native USB COM port')
        except Exception:
            self.port.close()
            raise
        self.thread = threading.Thread(target=self._read,daemon=True,name='TeleRC-fleet-USB')
        self.thread.start()

    def _write(self, data):
        if not self.send_lock.acquire(timeout=.1):
            raise OSError('Fleet USB write busy; command not queued')
        try:
            if self.error or self.stopped.is_set() or not self.port.is_open:
                raise OSError(self.error or 'Fleet BASE disconnected; reconnect manually')
            deadline = time.monotonic()+.05
            while self.port.out_waiting:
                if self.stopped.is_set() or time.monotonic() >= deadline:
                    raise OSError('Fleet USB output backlog; command not queued')
                self.stopped.wait(.002)
            if self.port.write(data) != len(data):
                raise OSError('Partial fleet USB write; command state UNKNOWN')
        finally:
            self.send_lock.release()
        return len(data)

    def _read(self):
        try:
            while not self.stopped.is_set():
                if not self.port.is_open or self.port.in_waiting > 8192:
                    raise OSError('Fleet BASE disconnected or receive backlog')
                for rover, kind, data in self.decoder.feed(self.port.read(512)):
                    if kind == 3 and fleet_capabilities(data) != self.capabilities:
                        raise OSError('Fleet BASE capabilities changed; reconnect manually')
                    with self.lock:
                        channel = self.channels.get(rover)
                        if channel is not None:
                            channel.feed(kind, data)
                self.stopped.wait(.002)
        except Exception as exc:
            self.error = str(exc)
            self.stopped.set()

    def channel(self, rover):
        if type(rover) is not int or not 1 <= rover <= 20:
            raise ValueError('Rover ID must be 1–20')
        with self.lock:
            if self.error or self.stopped.is_set():
                raise OSError(self.error or 'Fleet BASE closed')
            if rover in self.channels:
                raise RuntimeError(f'Rover {rover} already connected')
            channel = FleetPort(self,rover)
            self.channels[rover] = channel
        try:
            self._write(encode(rover,4,b'OPEN'))
            if not channel.opened.wait(2):
                raise RuntimeError('Rover subscription unconfirmed; reconnect deliberately')
            if channel.open_reply != b'OPENED':
                raise RuntimeError(channel.open_reply.decode('ascii',errors='replace'))
            return FleetMissionUSB(channel, self.capabilities)
        except Exception:
            channel.close()
            raise

    def close(self):
        # Abort all channels and discard local USB work; never send ARM/START/HOLD
        # implicitly. The explicitly configured FC loss policy remains in charge.
        self.stopped.set()
        if hasattr(self,'thread'):
            self.thread.join(timeout=1)
        try:
            self.port.reset_output_buffer()
        finally:
            self.port.close()


class FleetPort:
    def __init__(self,hub,rover):
        self.hub, self.rover = hub, rover
        self.buffer = bytearray()
        self.opened = threading.Event()
        self.open_reply = b''
        self.closed = False
        self.error = None

    def feed(self,kind,data):
        if kind == 4:
            self.open_reply = data
            self.opened.set()
        elif kind in (1,2):
            packet = encode(self.rover,kind,data)
            if len(self.buffer)+len(packet) > 8192:
                self.error = 'Rover telemetry backlog; reconnect manually'
            else:
                self.buffer.extend(packet)

    @property
    def in_waiting(self):
        if self.closed or self.error or self.hub.error or self.hub.stopped.is_set():
            raise OSError(self.error or self.hub.error or 'Fleet channel closed')
        with self.hub.lock:
            return len(self.buffer)

    @property
    def out_waiting(self):
        return 0  # Writes are serialized directly, never retained in a command queue.

    def write(self,data):
        if self.closed:
            raise OSError('Rover channel closed')
        frames = Decoder().feed(data)
        if len(frames) != 1 or frames[0][0] != self.rover or frames[0][1] != 1:
            raise ValueError('Cross-rover or invalid fleet channel write')
        return self.hub._write(data)

    def read(self,n):
        self.in_waiting
        with self.hub.lock:
            data = bytes(self.buffer[:n])
            del self.buffer[:n]
            return data

    def reset_output_buffer(self):
        pass  # Another rover's USB work must never be purged by this channel.

    def close(self):
        with self.hub.lock:
            if self.closed:
                return
            self.closed = True
            self.hub.channels.pop(self.rover,None)
            self.buffer.clear()
        if not self.hub.stopped.is_set():
            self.hub._write(encode(self.rover,4,b'CLOSE'))


class FleetMissionUSB(MissionUSB):
    fleet_authority = True

    def __init__(self,port,caps):
        self.rover, self.port = port.rover, port
        self.gate = threading.RLock()
        self.check = lambda: None
        self.status = lambda _: None
        self.decoder = Decoder()
        self.capabilities = dict(caps)
        self.profile = FirmwareProfile('0.5.0','Fleet LoRa',2,True)
        self.messages = deque(maxlen=64)
        self.mav = common.MAVLink(self,srcSystem=255,srcComponent=190)
        self.mav.robust_parsing = True

    def handshake(self):
        self.check()
        return dict(self.capabilities)

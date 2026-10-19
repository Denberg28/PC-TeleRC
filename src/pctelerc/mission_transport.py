"""Exclusive, bounded native CDC transport for TeleRC LoRa Mission v0.1.0."""
from collections import deque
import time
import threading
from pymavlink.dialects.v20 import common
from .mission_protocol.usb_gateway import Decoder, encode, split_mav


class MissionUSB:
    def __init__(self, port, rover):
        import serial
        if not 1 <= rover <= 20:
            raise ValueError('Rover ID must be 1–20')
        self.gate = threading.RLock()
        self.rover = rover
        self.check = lambda: None
        self.status = lambda text: None
        self.decoder = Decoder()
        self.messages = deque(maxlen=64)
        self.mav = common.MAVLink(self, srcSystem=255, srcComponent=190)
        self.mav.robust_parsing = True
        self.port = serial.Serial(port=None, baudrate=115200, timeout=0, write_timeout=.1)
        self.port.dtr = True; self.port.rts = False; self.port.port = port
        try:
            self.port.open()
            self.port.reset_input_buffer(); self.port.reset_output_buffer()
        except Exception:
            self.port.close(); raise

    def write(self, data):
        # Native Windows CDC may briefly retain a successful previous write.
        # Wait outside the send gate so HOLD/close can invalidate this send.
        deadline = time.monotonic()+.1
        while self.port.out_waiting:
            self.check()
            if time.monotonic() >= deadline:
                raise OSError('Mission USB output backlog; reconnect manually')
            time.sleep(.002)
        with self.gate:
            return self._write(data)

    def _write(self, data):
        self.check()
        if self.port.out_waiting:
            raise OSError('Mission USB output backlog; reconnect manually')
        frames = split_mav(bytes(data))
        for frame in frames:
            self.check()
            packet = encode(self.rover, 1, frame)
            if self.port.write(packet) != len(packet):
                raise OSError('Partial mission USB write; state UNKNOWN')
        return len(data)

    def recv_match(self, blocking=False):
        self.check()
        if self.port.in_waiting > 8192:
            raise OSError('Mission USB receive backlog; reconnect manually')
        for rover, kind, data in self.decoder.feed(self.port.read(512)):
            if rover != self.rover:
                continue
            if kind == 2:
                self.status(data.decode('ascii', errors='replace')[:100])
            elif kind == 1:
                for msg in self.mav.parse_buffer(data) or []:
                    if msg.get_type() != 'BAD_DATA':
                        if len(self.messages) >= 64:
                            raise OSError('Mission telemetry queue overflow')
                        self.messages.append(msg)
        return self.messages.popleft() if self.messages else None

    def close(self):
        try:
            self.port.reset_output_buffer()
        finally:
            self.port.close()
        self.messages.clear()

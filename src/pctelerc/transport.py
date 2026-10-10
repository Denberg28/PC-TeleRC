"""USB radio transports. Stable a10 Wi-Fi remains in MavlinkService."""
from pymavlink import mavutil


class VehicleSerial(mavutil.mavfile):
    """Bounded USB MAVLink transport for ELRS; no implicit reopen or port scan."""

    def __init__(self, port_name: str, baud: int = 460800):
        import serial
        # Configure control signals before opening to avoid ESP reset on Windows.
        self.port = serial.Serial(port=None, baudrate=baud, timeout=0, write_timeout=.1)
        self.port.dtr = False
        self.port.rts = False
        self.port.port = port_name
        try:
            self.port.open()
            super().__init__(None, port_name, source_system=255, source_component=190, input=True)
        except Exception:
            self.port.close()
            raise

    @property
    def destination(self):
        return self.port.port if self.port.is_open else None

    def configure_target(self, host, port):
        pass  # Serial routing is established only when opening the selected port.

    def lock_vehicle_peer(self):
        pass  # One physical serial endpoint; the service locks MAVLink identity.

    def recv(self, n=None):
        if not self.port.is_open:
            raise OSError("Radio USB disconnected; reconnect manually.")
        return self.port.read(min(self.port.in_waiting, 4096))

    def write(self, buf):
        # Never add drive commands behind a backed-up local serial queue.
        if self.port.out_waiting > 128:
            raise OSError("ELRS serial output is backed up; control disabled.")
        sent = self.port.write(buf)
        if sent != len(buf):
            raise OSError("Incomplete ELRS serial send.")
        return sent

    def recv_msg(self):
        self.pre_message()
        message = self.mav.parse_char(b"")
        if message is None:
            data = self.recv()
            if data and self.first_byte:
                self.auto_mavlink_version(data)
            message = self.mav.parse_char(data)
        if message is not None:
            self.post_message(message)
        return message

    def close(self):
        # A closed link must not replay queued commands when USB is reconnected.
        try:
            if self.port.is_open:
                self.port.reset_output_buffer()
        finally:
            self.port.close()


class VehicleLoRa(VehicleSerial):
    """Native T3-S3 CDC at 115200, carrying CRC-framed TeleRC datagrams."""

    def __init__(self, port_name: str):
        import serial
        from collections import deque
        from .lora import Parser
        self.parser = Parser()
        self.packets = deque()
        # Native CDC needs DTR asserted for firmware Serial.availableForWrite().
        # RTS is kept low; select the board's native USB port, not a reset-wired adapter.
        self.port = serial.Serial(port=None, baudrate=115200, timeout=0, write_timeout=.02)
        self.port.dtr = True
        self.port.rts = False
        self.port.port = port_name
        try:
            self.port.open()
            self.port.reset_input_buffer()
            mavutil.mavfile.__init__(self, None, port_name, source_system=255, source_component=190, input=True)
        except Exception:
            self.port.close()
            raise

    def read_packet(self):
        import time
        if not self.port.is_open:
            raise OSError("LoRa USB disconnected; reconnect manually.")
        data = self.port.read(min(self.port.in_waiting, 512))
        for packet in self.parser.feed(data, time.monotonic()):
            if len(self.packets) >= 32:
                raise OSError('LoRa USB receive backlog; reconnect required.')
            self.packets.append(packet)
        return self.packets.popleft() if self.packets else b''

    def recv(self, n=None):
        packet = self.read_packet()
        # Never mix local setup/status text with the MAVLink parser. Each USB
        # datagram contains one complete firmware telemetry frame.
        if not packet:
            return b''
        v1 = packet[0] == 0xfe and len(packet) >= 8 and len(packet) == packet[1] + 8
        v2 = packet[0] == 0xfd and len(packet) >= 12 and len(packet) == packet[1] + 12 + (13 if packet[2] & 1 else 0)
        return packet if v1 or v2 else b''

    def write(self, buf):
        from .lora import encode
        import time
        deadline = time.monotonic() + .01
        while self.port.out_waiting:
            if time.monotonic() >= deadline:
                raise OSError('LoRa USB output is backed up; control disabled.')
            time.sleep(.001)
        frame = encode(bytes(buf))
        sent = self.port.write(frame)
        if sent != len(frame):
            raise OSError('Incomplete LoRa USB send; reconnect required.')
        return len(buf)

    def require_active_base(self, stop_event, timeout=2.0):
        import time
        from .lora import Board
        self.write(b'TELERC_LORA_GET_V1')
        deadline = time.monotonic() + timeout
        while not stop_event.is_set() and time.monotonic() < deadline:
            board = Board.parse(self.read_packet())
            if board:
                if board.role != 'BASE':
                    raise ValueError('This is the ROVER board. Connect the LoRa BASE to the PC for driving.')
                if not board.active:
                    raise ValueError('LoRa BASE radio is inactive. Provision and restart it in LoRa Setup.')
                return board
            stop_event.wait(.005)
        raise ValueError('No TeleRC LoRa board reply. Check native USB, firmware and COM port.')

"""One bound UDP socket, one vehicle peer, and observable send failures."""
from __future__ import annotations

import errno
import socket

from pymavlink import mavutil


class VehicleUDP(mavutil.mavudp):
    def __init__(self, bind_host: str, bind_port: int):
        # Exclusive ownership on Windows prevents a second UDP listener from
        # silently taking packets from this socket. Do not enable SO_REUSEADDR.
        self.port = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                self.port.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            self.port.bind((bind_host, bind_port))
            if hasattr(socket, "SIO_UDP_CONNRESET"):
                self.port.ioctl(socket.SIO_UDP_CONNRESET, False)
            mavutil.set_close_on_exec(self.port.fileno())
            self.port.setblocking(False)
            self.udp_server = True
            self.broadcast = False
            self.last_address = None
            self.timeout = 0
            self.clients = set()
            self.clients_last_alive = {}
            self.resolved_destination_addr = None
            mavutil.mavfile.__init__(self, self.port.fileno(), f"{bind_host}:{bind_port}",
                                    source_system=255, source_component=190, input=True)
        except Exception:
            self.port.close()
            raise
        self.fixed_destination: tuple[str, int] | None = None
        self.vehicle_peer: tuple[str, int] | None = None
        self.received_peer: tuple[str, int] | None = None

    def configure_target(self, host: str, port: int):
        self.fixed_destination = (host, port) if host else None

    def lock_vehicle_peer(self):
        if self.received_peer is not None:
            self.vehicle_peer = self.received_peer

    def recv(self, n=None):
        try:
            data, address = self.port.recvfrom(mavutil.UDP_MAX_PACKET_LEN)
        except OSError as exc:
            if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK, errno.ECONNREFUSED):
                return b""
            raise
        # Filter before parsing: unrelated peers cannot refresh the heartbeat or
        # inherit the outbound command stream. Fixed targets identify the bridge
        # by IP and port; dynamic routing locks the first accepted autopilot peer.
        if self.fixed_destination and address != self.fixed_destination:
            return b""
        if self.vehicle_peer and address != self.vehicle_peer:
            return b""
        if self.received_peer is not None and address != self.received_peer:
            # Do not combine partial MAVLink frames from different UDP senders.
            self.mav = self.mav.__class__(self, srcSystem=255, srcComponent=190)
            self.mav.robust_parsing = True
        self.received_peer = address
        return data

    @property
    def destination(self):
        return self.fixed_destination or self.vehicle_peer

    def write(self, buf):
        destination = self.destination
        if destination is None:
            raise OSError("No accepted vehicle UDP peer is available.")
        # pymavlink's default mavudp.write swallows socket errors and broadcasts
        # to every learned client. Surface errors and unicast to the vehicle only.
        sent = self.port.sendto(buf, destination)
        if sent != len(buf):
            raise OSError("Incomplete MAVLink UDP send.")
        return sent

    def recv_msg(self):
        self.pre_message()
        # Drain the current datagram before reading another sender, preserving
        # the source address of every decoded message in a multi-frame packet.
        message = self.mav.parse_char(b"")
        if message is None:
            data = self.recv()
            if data and self.first_byte:
                self.auto_mavlink_version(data)
            message = self.mav.parse_char(data)
        if message is not None:
            self.post_message(message)
        return message


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

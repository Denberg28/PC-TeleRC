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
        # by IP; the first accepted autopilot heartbeat also locks its source port.
        if self.fixed_destination and address[0] != self.fixed_destination[0]:
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

"""Native ELRS Backpack: fixed UDP peer, bounded reads, PING-only writes.

Handset authority is immutable for this transport. Even teardown cannot send
neutral/release, commands or GCS heartbeats into the native ELRS RC stream.
"""
from __future__ import annotations

import ipaddress
import socket
from pymavlink import mavutil
from pymavlink.dialects.v10 import ardupilotmega as mavlink1


class BackpackTelemetry(mavutil.mavfile):
    def __init__(self, host, listen_port=14550, target_port=14555, bind_host="0.0.0.0"):
        address = ipaddress.IPv4Address(host)
        if address.is_multicast or address.is_unspecified or str(address) == "255.255.255.255":
            raise ValueError("Enter the Backpack's unicast IPv4 address.")
        self.peer = (str(address), int(target_port))
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.bind((bind_host, int(listen_port)))
            self.socket.setblocking(False)
            super().__init__(None, "ELRS Backpack", source_system=255, source_component=190, input=True)
        except Exception:
            self.socket.close()
            raise
        self._closed = False

    @property
    def destination(self):
        return None if self._closed else self.peer

    def recv(self, n=None):
        # One datagram per worker iteration, including rejected peers. No flood
        # can indefinitely postpone shutdown, registration or watchdog checks.
        try:
            data, peer = self.socket.recvfrom(8193)
        except (BlockingIOError, ConnectionResetError):
            return b""
        return data if peer == self.peer and len(data) <= 8192 else b""

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

    def write(self, buf):
        data = bytes(buf)
        # MAVLink 1 PING has a 14-byte payload, no extensions or signatures.
        if (len(data) != 22 or data[:2] != b"\xfe\x0e" or data[3:6] != bytes((255, 190, 4))):
            raise PermissionError("ELRS Backpack is telemetry-only; handset controls the rover.")
        try:
            msg = mavlink1.MAVLink(None).parse_char(data)
        except Exception as exc:
            raise PermissionError("Invalid Backpack registration checksum.") from exc
        if msg is None or msg.get_type() != "PING" or msg.target_system != 0 or msg.target_component != 0:
            raise PermissionError("Only broadcast registration PING is permitted.")
        return self.socket.sendto(data, self.peer)

    def close(self):
        self._closed = True
        self.socket.close()

import socket
import time

import pytest
from pymavlink.dialects.v10 import ardupilotmega as mavlink1

from pctelerc.transport import VehicleUDP


def heartbeat(system=1, kind=10):
    encoder = mavlink1.MAVLink(None, srcSystem=system, srcComponent=1)
    return encoder.heartbeat_encode(kind, 3, 0, 0, 4).pack(encoder)


def read_message(link, timeout=.5):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        message = link.recv_msg()
        if message is not None:
            return message
        time.sleep(.005)
    return None


def test_dynamic_peer_does_not_use_last_address_or_broadcast_to_other_clients():
    link = VehicleUDP('127.0.0.1', 0)
    rover = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    other = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rover.bind(('127.0.0.1', 0))
    other.bind(('127.0.0.1', 0))
    destination = link.port.getsockname()
    try:
        with pytest.raises(OSError, match='No accepted'):
            link.write(b'command')
        rover.sendto(heartbeat(), destination)
        assert read_message(link).get_srcSystem() == 1
        link.lock_vehicle_peer()
        peer = link.vehicle_peer
        other.sendto(heartbeat(2), destination)
        assert read_message(link, .05) is None
        assert link.vehicle_peer == peer
        link.write(b'command')
        rover.settimeout(.5)
        assert rover.recv(100) == b'command'
        other.settimeout(.05)
        with pytest.raises(socket.timeout):
            other.recv(100)
    finally:
        link.close()
        rover.close()
        other.close()


def test_udp_send_failure_is_observable():
    link = VehicleUDP('127.0.0.1', 0)
    link.configure_target('127.0.0.1', 12345)
    link.close()
    with pytest.raises(OSError):
        link.write(b'command')


def test_multiple_messages_keep_their_original_datagram_peer():
    link = VehicleUDP('127.0.0.1', 0)
    first = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    second = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    first.bind(('127.0.0.1', 0))
    second.bind(('127.0.0.1', 0))
    try:
        first.sendto(heartbeat(1) + heartbeat(1), link.port.getsockname())
        assert read_message(link).get_srcSystem() == 1
        original_peer = link.received_peer
        second.sendto(heartbeat(2), link.port.getsockname())
        assert read_message(link).get_srcSystem() == 1
        assert link.received_peer == original_peer
        link.lock_vehicle_peer()
        assert read_message(link, .05) is None
    finally:
        link.close()
        first.close()
        second.close()


def test_bound_port_cannot_be_shared_by_a_second_listener():
    link = VehicleUDP('127.0.0.1', 0)
    try:
        with pytest.raises(OSError):
            VehicleUDP('127.0.0.1', link.port.getsockname()[1])
    finally:
        link.close()

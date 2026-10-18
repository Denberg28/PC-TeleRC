import socket
import time
from dataclasses import replace

import pytest
from pymavlink.dialects.v10 import ardupilotmega as mav1

from pctelerc.backpack import BackpackTelemetry
from pctelerc.config import AppSettings
from pctelerc.core import LinkState
from pctelerc.mavlink import MavlinkService
from test_elrs_serial import wait_until


def unused_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def test_transport_only_accepts_checksum_valid_registration_from_255_190():
    link = BackpackTelemetry('127.0.0.1', 0, unused_port())
    mav = mav1.MAVLink(None, srcSystem=255, srcComponent=190)
    try:
        assert link.write(mav.ping_encode(0, 42, 0, 0).pack(mav)) == 22
        messages = [mav.heartbeat_encode(6, 8, 0, 0, 4),
                    mav.rc_channels_override_encode(1, 1, *([1500] * 8)),
                    mav.command_long_encode(1, 1, 400, 0, 1, 0, 0, 0, 0, 0, 0),
                    mav.ping_encode(0, 1, 1, 1)]
        for msg in messages:
            with pytest.raises(PermissionError):
                link.write(msg.pack(mav))
        data = bytearray(mav.ping_encode(0, 0, 0, 0).pack(mav)); data[-1] ^= 1
        with pytest.raises(PermissionError): link.write(data)
        with pytest.raises(PermissionError): link.write(b'TELERC_DISCOVER_V1')
    finally:
        link.close()


def test_worker_retries_after_stale_rejects_foreign_peers_and_never_commands():
    base = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    base.bind(('127.0.0.1', 0)); base.settimeout(2)
    local = unused_port()
    service = MavlinkService()
    service.configure(AppSettings(link_mode='elrs_backpack', backpack_host='127.0.0.1',
        backpack_listen_port=local, backpack_target_port=base.getsockname()[1], heartbeat_timeout=1))
    mav = mav1.MAVLink(None, srcSystem=1, srcComponent=1)
    heartbeat = mav.heartbeat_encode(10, 3, 0, 0, 4).pack(mav)
    service.start()
    packets = []
    try:
        packet, peer = base.recvfrom(1024); packets.append(packet)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as foreign:
            foreign.sendto(heartbeat, peer)
        time.sleep(.04)
        assert service.snapshot().last_heartbeat is None
        base.sendto(heartbeat, peer)
        assert wait_until(lambda: service.snapshot().state == LinkState.CONNECTED)
        assert not service.enable_control()[0]
        assert not service.arm()[0] and not service.disarm()[0]
        service._send_gcs_heartbeat()
        assert not service._send_override(1600, 1700)
        service.disable_control()
        assert wait_until(lambda: service.snapshot().state == LinkState.STALE)
        # Drain registrations after an outage. All output stays PING only.
        packets.append(base.recvfrom(1024)[0])
        packets.append(base.recvfrom(1024)[0])
        base.sendto(heartbeat, peer)
        assert wait_until(lambda: service.snapshot().state == LinkState.CONNECTED)
        assert not service.snapshot().control_enabled
        assert service.stop()
        decoder = mav1.MAVLink(None)
        assert all(decoder.parse_char(p).get_type() == 'PING' for p in packets)
        assert not service.snapshot().running
    finally:
        service.stop(); base.close()


def test_live_backpack_routing_edits_require_disconnect():
    service = MavlinkService()
    settings = AppSettings(link_mode='elrs_backpack')
    service.configure(settings)
    service._link = object()
    with pytest.raises(ValueError, match='Disconnect'):
        service.configure(replace(settings, backpack_host='10.0.0.2'))

import socket
import time

from pymavlink import mavutil

from pctelerc.config import AppSettings
from pctelerc.core import LinkState
from pctelerc.mavlink import MavlinkService
from pctelerc.transport import VehicleUDP


def free_udp_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def wait_until(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def send_rover_heartbeat(conn):
    conn.mav.heartbeat_send(
        mavutil.mavlink.MAV_TYPE_GROUND_ROVER,
        mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
        0,
        0,
        mavutil.mavlink.MAV_STATE_ACTIVE,
    )


def test_real_udp_worker_acquires_vehicle_and_stops_cleanly():
    port = free_udp_port()
    service = MavlinkService()
    service.configure(
        AppSettings(
            bind_host="127.0.0.1",
            listen_port=port,
            heartbeat_timeout=1.0,
        )
    )
    service.start()

    rover = VehicleUDP("127.0.0.1", 0)
    rover.configure_target("127.0.0.1", port)
    rover.mav.srcSystem = 42
    rover.mav.srcComponent = 1
    try:
        for _ in range(8):
            send_rover_heartbeat(rover)
            if wait_until(lambda: service.snapshot().state == LinkState.CONNECTED, timeout=.35):
                break

        snap = service.snapshot()
        assert snap.state == LinkState.CONNECTED
        assert snap.vehicle_system == 42
        assert snap.vehicle_component == 1
        assert snap.rx_messages >= 1
    finally:
        assert service.stop()
        rover.close()

    stopped = service.snapshot()
    assert not stopped.running
    assert not stopped.control_enabled


def test_actual_ch1_ch2_drive_disable_disconnect_and_reconnect():
    from pctelerc.core import ControlFrame
    port = free_udp_port()
    service = MavlinkService()
    service.configure(AppSettings(bind_host='127.0.0.1', listen_port=port, heartbeat_timeout=1))
    rover = VehicleUDP('127.0.0.1', 0)
    rover.configure_target('127.0.0.1', port)
    rover.mav.srcSystem = 42
    rover.mav.srcComponent = 1
    def acquire():
        for _ in range(10):
            send_rover_heartbeat(rover)
            if wait_until(lambda: service.snapshot().state == LinkState.CONNECTED, .1):
                return
        raise AssertionError('vehicle heartbeat not acquired')
    try:
        service.start()
        acquire()
        service.set_control_frame(ControlFrame(0, 0, time.monotonic()), 3)
        assert service.enable_control()[0]
        service.set_control_frame(ControlFrame(.4, .8, time.monotonic()), 3)
        drive = None
        deadline = time.monotonic() + .3
        while time.monotonic() < deadline:
            message = rover.recv_match(type='RC_CHANNELS_OVERRIDE', blocking=True, timeout=.05)
            if message and message.chan1_raw == 1700 and message.chan2_raw == 1600:
                drive = message
                break
        assert drive is not None
        assert drive.chan1_raw == 1700 and drive.chan2_raw == 1600
        assert drive.chan3_raw == 65535
        assert drive.get_srcSystem() == 255 and drive.get_srcComponent() == 190
        assert drive.get_msgbuf()[0] == 0xFE
        assert service.disable_control()
        overrides = []
        deadline = time.monotonic() + .2
        while time.monotonic() < deadline:
            message = rover.recv_match(type='RC_CHANNELS_OVERRIDE', blocking=True, timeout=.02)
            if message:
                overrides.append(message)
        assert any(m.chan1_raw == 1500 and m.chan2_raw == 1500 for m in overrides)
        assert overrides[-1].chan1_raw == 0 and overrides[-1].chan2_raw == 0
        assert service.stop()
        assert service.snapshot().state == LinkState.DISCONNECTED
        assert service.snapshot().vehicle_system is None
        assert not service.enable_control()[0]
        # UDP port really closed and reusable.
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.bind(('127.0.0.1', port))
        probe.close()
        assert service.start()
        acquire()
        assert not service.snapshot().control_enabled
        assert not service.enable_control()[0]  # requires fresh input for new session
    finally:
        service.stop()
        rover.close()


def test_bridge_discovery_bootstraps_telemetry_and_refreshes_pairing():
    # The ESP32 sends unicast telemetry only to the client registered by discovery.
    port = free_udp_port()
    bridge = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    bridge.bind(('127.0.0.1', 0))
    bridge.settimeout(2)
    service = MavlinkService()
    service.configure(AppSettings(bind_host='127.0.0.1', listen_port=port,
                                  target_host='127.0.0.1', target_port=bridge.getsockname()[1]))
    encoder = mavutil.mavlink.MAVLink(None, srcSystem=42, srcComponent=1)
    packet = encoder.heartbeat_encode(11, 3, 0, 0, 4).pack(encoder)
    try:
        assert service.start()
        for _ in range(2):
            deadline = time.monotonic() + 2
            while True:
                data, peer = bridge.recvfrom(2048)
                if data == b'TELERC_DISCOVER_V1':
                    assert peer == ('127.0.0.1', port)
                    bridge.sendto(packet, peer)
                    break
                assert time.monotonic() < deadline
            assert wait_until(lambda: service.snapshot().state == LinkState.CONNECTED)
        assert service.snapshot().vehicle_system == 42
    finally:
        service.stop()
        bridge.close()


def test_repeated_connect_disconnect_releases_bridge_lease_and_never_resumes():
    port = free_udp_port()
    bridge = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    bridge.bind(('127.0.0.1', 0))
    bridge.settimeout(2)
    service = MavlinkService()
    service.configure(AppSettings(bind_host='127.0.0.1', listen_port=port,
                                  target_host='127.0.0.1', target_port=bridge.getsockname()[1]))
    encoder = mavutil.mavlink.MAVLink(None, srcSystem=42, srcComponent=1)
    packet = encoder.heartbeat_encode(10, 3, 0, 0, 4).pack(encoder)
    try:
        for _ in range(3):
            assert service.start()
            data, peer = bridge.recvfrom(2048)
            assert data == b'TELERC_DISCOVER_V1'
            assert peer[1] == port
            bridge.sendto(packet, peer)
            assert wait_until(lambda: service.snapshot().state == LinkState.CONNECTED)
            assert not service.snapshot().control_enabled
            assert service.stop()
            disconnects = 0
            while disconnects < service.RELEASE_RETRIES:
                data, source = bridge.recvfrom(2048)
                assert source == peer
                disconnects += data == b'TELERC_DISCONNECT_V1'
            assert not service.snapshot().running
            assert service.snapshot().vehicle_system is None
            assert not service.enable_control()[0]
    finally:
        service.stop()
        bridge.close()


def test_malformed_traffic_does_not_stop_worker_or_prevent_heartbeat_recovery():
    port = free_udp_port()
    bridge = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    bridge.bind(('127.0.0.1', 0))
    service = MavlinkService()
    service.configure(AppSettings(bind_host='127.0.0.1', listen_port=port,
                                  target_host='127.0.0.1', target_port=bridge.getsockname()[1], heartbeat_timeout=1))
    encoder = mavutil.mavlink.MAVLink(None, srcSystem=42, srcComponent=1)
    packet = encoder.heartbeat_encode(10, 3, 0, 0, 4).pack(encoder)
    try:
        service.start()
        assert wait_until(lambda: service.snapshot().running)
        for _ in range(20):
            bridge.sendto(b'TELERC_STATUS_V1,junk\x00\xff', ('127.0.0.1', port))
        bridge.sendto(packet, ('127.0.0.1', port))
        assert wait_until(lambda: service.snapshot().state == LinkState.CONNECTED)
        assert wait_until(lambda: service.snapshot().state == LinkState.STALE, 2)
        assert service.snapshot().running
        bridge.sendto(packet, ('127.0.0.1', port))
        assert wait_until(lambda: service.snapshot().state == LinkState.CONNECTED)
        assert not service.snapshot().control_enabled
    finally:
        service.stop()
        bridge.close()

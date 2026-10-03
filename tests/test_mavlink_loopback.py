import socket
import time

from pymavlink import mavutil

from pctelerc.config import AppSettings
from pctelerc.core import LinkState
from pctelerc.mavlink import MavlinkService


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

    rover = mavutil.mavlink_connection(
        f"udpout:127.0.0.1:{port}",
        source_system=42,
        source_component=1,
    )
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
    rover = mavutil.mavlink_connection(f'udpout:127.0.0.1:{port}', source_system=42, source_component=1)
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

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

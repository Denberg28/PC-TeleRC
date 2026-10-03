from pctelerc.core import LinkState
from pctelerc.mavlink import MavlinkService


class FakeHeartbeat:
    type = 10
    base_mode = 0

    def __init__(self, system, component=1):
        self._system = system
        self._component = component

    def get_type(self):
        return "HEARTBEAT"

    def get_srcSystem(self):
        return self._system

    def get_srcComponent(self):
        return self._component


def test_first_vehicle_system_id_is_locked(monkeypatch):
    service = MavlinkService()
    service._handle_message(FakeHeartbeat(1), 10.0)
    first = service.snapshot()
    assert first.vehicle_system == 1
    assert first.state == LinkState.CONNECTED

    service._handle_message(FakeHeartbeat(2), 10.1)
    second = service.snapshot()
    assert second.vehicle_system == 1
    assert second.ignored_heartbeats == 1
    assert second.last_heartbeat == 10.0


def test_same_vehicle_refreshes_heartbeat():
    service = MavlinkService()
    service._handle_message(FakeHeartbeat(7), 20.0)
    service._handle_message(FakeHeartbeat(7), 21.0)
    snap = service.snapshot()
    assert snap.vehicle_system == 7
    assert snap.last_heartbeat == 21.0
    assert snap.ignored_heartbeats == 0


def test_same_system_different_component_is_ignored():
    service = MavlinkService()
    service._handle_message(FakeHeartbeat(9, 1), 30.0)
    service._handle_message(FakeHeartbeat(9, 191), 31.0)
    snap = service.snapshot()
    assert snap.vehicle_system == 9
    assert snap.vehicle_component == 1
    assert snap.last_heartbeat == 30.0
    assert snap.ignored_heartbeats == 1


def test_generic_boat_and_nonstandard_component_autopilot_heartbeats():
    for vehicle_type in (0, 10, 11):
        service = MavlinkService()
        message = FakeHeartbeat(42, 2)
        message.type = vehicle_type
        message.autopilot = 3
        service._handle_message(message, 10.0)
        assert service.snapshot().state == LinkState.CONNECTED
        assert service.snapshot().vehicle_component == 2


def test_gcs_and_non_autopilot_heartbeats_cannot_acquire_vehicle():
    for vehicle_type, autopilot, system in ((6, 3, 42), (10, 8, 42), (10, 3, 255), (10, 3, 0)):
        service = MavlinkService()
        message = FakeHeartbeat(system)
        message.type = vehicle_type
        message.autopilot = autopilot
        service._handle_message(message, 10.0)
        assert service.snapshot().vehicle_system is None

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

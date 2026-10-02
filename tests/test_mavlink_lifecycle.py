from pctelerc.config import AppSettings
from pctelerc.mavlink import MavlinkService


class AliveThread:
    def is_alive(self):
        return True


def test_target_change_does_not_require_listener_restart():
    service = MavlinkService()
    service._thread = AliveThread()
    service._bound_host = "0.0.0.0"
    service._bound_port = 14550
    service.configure(AppSettings(
        bind_host="0.0.0.0",
        listen_port=14550,
        target_host="192.168.4.1",
        target_port=14550,
    ))
    assert not service.listener_restart_required()

    service.configure(AppSettings(
        bind_host="0.0.0.0",
        listen_port=14550,
        target_host="192.168.4.2",
        target_port=14551,
    ))
    assert not service.listener_restart_required()


def test_listener_address_or_port_change_requires_restart():
    service = MavlinkService()
    service._thread = AliveThread()
    service._bound_host = "0.0.0.0"
    service._bound_port = 14550

    service.configure(AppSettings(bind_host="127.0.0.1", listen_port=14550))
    assert service.listener_restart_required()

    service.configure(AppSettings(bind_host="0.0.0.0", listen_port=14551))
    assert service.listener_restart_required()


def test_duplicate_start_request_is_idempotent():
    service = MavlinkService()
    service._thread = AliveThread()
    assert service.start() is False

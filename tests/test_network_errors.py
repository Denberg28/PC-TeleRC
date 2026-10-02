from pctelerc.network_errors import describe_mavlink_start_error, socket_error_code


class FakeWinError(Exception):
    def __init__(self, code):
        super().__init__(f"fake {code}")
        self.winerror = code


def test_winerror_10048_is_targeted():
    message = describe_mavlink_start_error(FakeWinError(10048), 14550)
    assert "UDP 14550 is already in use" in message
    assert "Mission Planner" in message


def test_winerror_10013_is_targeted():
    message = describe_mavlink_start_error(FakeWinError(10013), 14550)
    assert "Windows denied access to UDP 14550" in message
    assert "excluded UDP port ranges" in message


def test_unknown_error_is_preserved():
    exc = RuntimeError("boom")
    assert socket_error_code(exc) is None
    assert describe_mavlink_start_error(exc, 14550) == "MAVLink worker stopped: boom"

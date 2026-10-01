from pctelerc.config import AppSettings
from pctelerc.core import ControlFrame, LinkState
from pctelerc.field_safety import can_arm, can_continue_control, can_enable_control, validate_mapping


def test_nominal_field_preflight_passes():
    settings = AppSettings(steering_channel=1, throttle_channel=3)
    frame = ControlFrame(0.0, 0.0, 10.0)
    result = can_enable_control(
        settings=settings, link_state=LinkState.CONNECTED,
        frame=frame, axis_count=3, now=10.1
    )
    assert result.allowed


def test_unplugged_or_invalid_axis_fails_closed():
    settings = AppSettings(steer_axis=4, throttle_axis=1, brake_axis=2)
    result = validate_mapping(settings, axis_count=3)
    assert not result.allowed
    assert result.code == "axis_out_of_range"


def test_stale_controller_cannot_enable():
    settings = AppSettings(controller_timeout=.35)
    frame = ControlFrame(0.0, 0.0, 10.0)
    result = can_enable_control(
        settings=settings, link_state=LinkState.CONNECTED,
        frame=frame, axis_count=3, now=10.5
    )
    assert not result.allowed
    assert result.code == "controller_stale"


def test_non_neutral_cannot_arm():
    settings = AppSettings()
    frame = ControlFrame(0.0, .3, 10.0)
    result = can_arm(
        settings=settings, link_state=LinkState.CONNECTED,
        frame=frame, axis_count=3, now=10.1
    )
    assert not result.allowed
    assert result.code == "throttle_not_neutral"


def test_duplicate_rc_channel_fails_closed():
    settings = AppSettings(steering_channel=2, throttle_channel=2)
    result = validate_mapping(settings, axis_count=3)
    assert not result.allowed
    assert result.code == "duplicate_rc_channel"


def test_active_drive_allows_non_neutral_throttle():
    settings = AppSettings()
    frame = ControlFrame(0.2, 0.6, 10.0)
    result = can_continue_control(
        settings=settings, link_state=LinkState.CONNECTED,
        frame=frame, axis_count=3, now=10.1
    )
    assert result.allowed


def test_active_drive_still_fails_on_stale_input():
    settings = AppSettings(controller_timeout=.35)
    frame = ControlFrame(0.2, 0.6, 10.0)
    result = can_continue_control(
        settings=settings, link_state=LinkState.CONNECTED,
        frame=frame, axis_count=3, now=10.5
    )
    assert not result.allowed
    assert result.code == "controller_stale"

import pytest

from pctelerc.core import ControlFrame, LinkState, control_is_fresh, heartbeat_link_state


@pytest.mark.parametrize("timestamp", [100.01, float("nan"), float("inf"), -float("inf")])
def test_future_or_invalid_input_cannot_remain_fresh(timestamp):
    assert not control_is_fresh(ControlFrame(0, 0, timestamp), now=100)
    assert heartbeat_link_state(timestamp, now=100) == LinkState.STALE


def test_monotonic_regression_does_not_restore_control():
    frame = ControlFrame(0, 0, 100)
    assert control_is_fresh(frame, now=100)
    assert not control_is_fresh(frame, now=99)
    assert not control_is_fresh(frame, now=101)

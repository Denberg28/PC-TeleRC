from __future__ import annotations

from dataclasses import dataclass

from pctelerc.config import AppSettings
from pctelerc.core import ControlFrame, LinkState
from pctelerc.field_safety import can_arm, can_enable_control


@dataclass
class Step:
    name: str
    allowed: bool
    code: str


def simulate_nominal_and_fault_recovery() -> list[Step]:
    s = AppSettings(steering_channel=1, throttle_channel=3, controller_timeout=.35)
    steps: list[Step] = []

    no_link = can_enable_control(settings=s, link_state=LinkState.CONNECTING, frame=None, axis_count=None, now=0)
    steps.append(Step("startup-no-link", no_link.allowed, no_link.code))

    neutral = ControlFrame(0.0, 0.0, 1.0)
    ready = can_enable_control(settings=s, link_state=LinkState.CONNECTED, frame=neutral, axis_count=3, now=1.1)
    steps.append(Step("ready-neutral", ready.allowed, ready.code))

    arm = can_arm(settings=s, link_state=LinkState.CONNECTED, frame=neutral, axis_count=3, now=1.1)
    steps.append(Step("arm-ready", arm.allowed, arm.code))

    driving = ControlFrame(.2, .4, 2.0)
    active = can_enable_control(settings=s, link_state=LinkState.CONNECTED, frame=driving, axis_count=3, now=2.1)
    steps.append(Step("active-nonneutral-reenable", active.allowed, active.code))

    stale = can_enable_control(settings=s, link_state=LinkState.CONNECTED, frame=driving, axis_count=3, now=2.5)
    steps.append(Step("controller-loss", stale.allowed, stale.code))

    reconnect_moving = ControlFrame(0.0, .3, 3.0)
    not_neutral = can_enable_control(settings=s, link_state=LinkState.CONNECTED, frame=reconnect_moving, axis_count=3, now=3.1)
    steps.append(Step("reconnect-still-moving", not_neutral.allowed, not_neutral.code))

    reconnect_neutral = ControlFrame(0.0, 0.0, 3.2)
    restored = can_enable_control(settings=s, link_state=LinkState.CONNECTED, frame=reconnect_neutral, axis_count=3, now=3.25)
    steps.append(Step("manual-reenable-ready", restored.allowed, restored.code))

    wifi_loss = can_enable_control(settings=s, link_state=LinkState.STALE, frame=reconnect_neutral, axis_count=3, now=3.3)
    steps.append(Step("wifi-loss", wifi_loss.allowed, wifi_loss.code))

    return steps


def test_nominal_and_fault_recovery_sequence():
    steps = simulate_nominal_and_fault_recovery()
    result = {step.name: (step.allowed, step.code) for step in steps}
    assert result["startup-no-link"] == (False, "link_unhealthy")
    assert result["ready-neutral"] == (True, "ok")
    assert result["arm-ready"] == (True, "ok")
    assert result["active-nonneutral-reenable"] == (False, "throttle_not_neutral")
    assert result["controller-loss"] == (False, "controller_stale")
    assert result["reconnect-still-moving"] == (False, "throttle_not_neutral")
    assert result["manual-reenable-ready"] == (True, "ok")
    assert result["wifi-loss"] == (False, "link_unhealthy")


def test_invalid_mapping_and_wrong_axis_fail_closed():
    duplicate = AppSettings(steering_channel=1, throttle_channel=1)
    neutral = ControlFrame(0.0, 0.0, 5.0)
    r1 = can_enable_control(settings=duplicate, link_state=LinkState.CONNECTED, frame=neutral, axis_count=3, now=5.1)
    assert not r1.allowed and r1.code == "duplicate_rc_channel"

    missing_axis = AppSettings(steer_axis=5, throttle_axis=1, brake_axis=2)
    r2 = can_enable_control(settings=missing_axis, link_state=LinkState.CONNECTED, frame=neutral, axis_count=3, now=5.1)
    assert not r2.allowed and r2.code == "axis_out_of_range"

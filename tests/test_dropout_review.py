from dataclasses import replace
from types import SimpleNamespace
import math
import sys

import pytest

from pctelerc.config import AppSettings
from pctelerc.controller import WheelService
from pctelerc.core import ControlFrame, LinkState, control_is_fresh
from pctelerc.field_safety import can_enable_control, can_continue_control, validate_mapping
from test_control_source import ready


def test_wifi_center_gate_matches_bridge_without_limiting_active_steering():
    args = dict(settings=AppSettings(), link_state=LinkState.CONNECTED,
                frame=ControlFrame(.8, 0, 10), axis_count=3, now=10)
    assert can_enable_control(**args).code == "steering_not_neutral"
    assert can_continue_control(**args).allowed
    args["frame"] = ControlFrame(.05, 0, 10)
    assert can_enable_control(**args).allowed


def test_wifi_rejects_mapping_bridge_will_drop():
    assert validate_mapping(AppSettings(throttle_channel=5), 3).code == "bridge_mapping"
    assert validate_mapping(AppSettings(link_mode="elrs_serial", throttle_channel=5), 3).allowed


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_corrupt_frame_is_not_fresh(value):
    assert not control_is_fresh(ControlFrame(value, 0, 10), now=10)


def test_fast_combined_input_does_not_latch_control(monkeypatch):
    service, sample, clock, sends, releases = ready(monkeypatch)
    for i in range(2000):
        clock.now += .05
        sample.frame = ControlFrame(1 if i % 2 else -1, .8 if i % 3 else -.8, clock.now)
        service._snapshot = replace(service.snapshot(), last_heartbeat=clock.now)
        service._control_tick(clock.now)
    assert len(sends) == 2000 and not releases and service.snapshot().control_enabled


def test_reconnect_between_control_ticks_cannot_resume_motion(monkeypatch):
    service, sample, clock, sends, releases = ready(monkeypatch)
    # Even when the short disconnected snapshot was never sampled by this worker.
    sample.frame = ControlFrame(.5, .5, clock.now, session=1)
    service._control_tick(clock.now)
    assert not sends and releases and service.snapshot().failsafe_latched
    assert "reconnected" in service.snapshot().error
    sample.frame = ControlFrame(0, 0, clock.now, session=1)
    assert service.enable_control()[0]
    service._control_tick(clock.now)
    assert sends == [(1500, 1500)]


def test_wheel_drains_bursts_and_reopens_same_guid_new_instance(monkeypatch):
    import pctelerc.controller as module
    service = WheelService()
    clock = SimpleNamespace(now=100.)
    samples = []
    state = SimpleNamespace(cycle=0, gets=0, instance=11, present=True)
    class Joystick:
        def __init__(self, index): self.instance = state.instance
        def init(self): pass
        def get_name(self): return "PXN mock"
        def get_guid(self): return "same-guid"
        def get_numaxes(self): return 3
        def get_numbuttons(self): return 0
        def get_instance_id(self): return self.instance
        def get_axis(self, index):
            assert self.instance == state.instance, "old handle reused after replug"
            return (.8 if state.cycle % 2 else -.8) if index == 0 else 1.
    def events():
        state.gets += 1
        if state.cycle == 2:
            state.instance = 12
            return [SimpleNamespace(type=2, instance_id=11), SimpleNamespace(type=1)]
        # Axis traffic is drained, not interpreted as device removal.
        return [SimpleNamespace(type=3) for _ in range(300)]
    fake = SimpleNamespace(
        display=SimpleNamespace(init=lambda: None, quit=lambda: None),
        joystick=SimpleNamespace(init=lambda: None, quit=lambda: None,
                                 get_count=lambda: 1, Joystick=Joystick),
        event=SimpleNamespace(get=events), JOYDEVICEADDED=1, JOYDEVICEREMOVED=2)
    def sleep(_):
        samples.append(service.snapshot())
        clock.now += .02
        state.cycle += 1
        if state.cycle == 5: service._stop.set()
    monkeypatch.setitem(sys.modules, "pygame", fake)
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: clock.now, sleep=sleep))
    service._run()
    assert state.gets == 5 and all(s.connected for s in samples)
    assert [s.frame.session for s in samples] == [1, 1, 2, 2, 2]
    assert len({s.frame.timestamp for s in samples}) == 5

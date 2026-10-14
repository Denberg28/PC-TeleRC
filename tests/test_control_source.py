from dataclasses import replace
from types import SimpleNamespace

from pctelerc.core import ControlFrame, LinkState
from pctelerc.mavlink import MavlinkService, MavlinkSnapshot
from test_vehicle_lock import FakeHeartbeat


def ready(monkeypatch):
    clock = SimpleNamespace(now=100.0)
    monkeypatch.setattr("pctelerc.mavlink.time.monotonic", lambda: clock.now)
    service = MavlinkService()
    service._snapshot = MavlinkSnapshot(running=True, state=LinkState.CONNECTED,
        last_heartbeat=clock.now, vehicle_system=1, vehicle_component=1)
    sample = SimpleNamespace(connected=True, axes=(0, 0, 0),
                             frame=ControlFrame(0, 0, clock.now))
    service.set_control_source(lambda: sample)
    sends, releases = [], []
    monkeypatch.setattr(service, "_send_override", lambda s, t: sends.append((s, t)) or True)
    monkeypatch.setattr(service, "_send_neutral_then_release", lambda: releases.append(True))
    assert service.enable_control()[0]
    return service, sample, clock, sends, releases


def test_wheel_updates_reach_control_with_no_gui_refresh(monkeypatch):
    service, sample, clock, sends, releases = ready(monkeypatch)
    # UI makes no set_control_frame calls for two seconds, but wheel and FC run.
    for _ in range(40):
        clock.now += .05
        sample.frame = ControlFrame(.2, .3, clock.now)
        service._handle_message(FakeHeartbeat(1), clock.now)
        service._control_tick(clock.now)
    assert len(sends) == 40 and not releases
    assert service.snapshot().control_enabled


def test_snapshot_does_not_refresh_stale_acquisition_time(monkeypatch):
    service, sample, clock, sends, releases = ready(monkeypatch)
    clock.now += service._settings.controller_timeout + .01
    service._control_tick(clock.now)
    assert service.snapshot().failsafe_latched and releases and not sends
    assert "stale" in service.snapshot().error
    sample.frame = ControlFrame(0, 0, clock.now)
    service._handle_message(FakeHeartbeat(1), clock.now)
    service._control_tick(clock.now)
    assert service.snapshot().failsafe_latched and not service.snapshot().control_enabled
    assert "stale" in service.snapshot().error
    assert service.enable_control()[0]
    assert service.snapshot().error == ""


def test_disconnected_wheel_and_supplier_exception_fail_closed(monkeypatch):
    for fail in (False, True):
        service, sample, clock, sends, releases = ready(monkeypatch)
        sample.connected = False
        if fail:
            def broken():
                raise RuntimeError("snapshot unavailable")
            service.set_control_source(broken)
        service._control_tick(clock.now)
        assert service.snapshot().failsafe_latched and releases and not sends


def test_heartbeat_latch_retains_cause_and_neutral_display_on_recovery(monkeypatch):
    service, sample, clock, sends, releases = ready(monkeypatch)
    service._snapshot = replace(service.snapshot(), steer_pwm=1718, throttle_pwm=1600)
    clock.now += service._settings.heartbeat_timeout + .1
    service._refresh_link_state(clock.now)
    assert service.snapshot().failsafe_latched and releases
    reason = service.snapshot().error
    assert "heartbeat missing" in reason
    assert (service.snapshot().steer_pwm, service.snapshot().throttle_pwm) == (1500, 1500)
    service._handle_message(FakeHeartbeat(1), clock.now)
    assert service.snapshot().state == LinkState.CONNECTED
    assert service.snapshot().error == reason
    assert not service.snapshot().control_enabled


def test_source_axis_mapping_still_validated(monkeypatch):
    service, sample, clock, sends, releases = ready(monkeypatch)
    sample.axes = (0,)
    service._control_tick(clock.now)
    assert service.snapshot().failsafe_latched and releases and not sends

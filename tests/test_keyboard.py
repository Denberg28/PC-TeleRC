from dataclasses import replace
from types import SimpleNamespace

import pytest

from pctelerc.config import AppSettings, load_settings, save_settings
from pctelerc.controller import ControllerSnapshot
from pctelerc.core import ControlFrame, LinkState
from pctelerc.diagnostics import build_targeted_status
from pctelerc.field_safety import can_enable_control, validate_mapping
from pctelerc.keyboard import InputService, KeyboardService
from pctelerc.mavlink import MavlinkService, MavlinkSnapshot


@pytest.fixture
def keyboard(monkeypatch):
    clock = SimpleNamespace(now=100.)
    monkeypatch.setattr("pctelerc.keyboard.time.monotonic", lambda: clock.now)
    service = KeyboardService()
    service.configure(AppSettings(input_source="keyboard", steering_sensitivity=.5))
    service.set_active(True)
    return service, clock


@pytest.mark.parametrize("key,steer,drive", [
    ("w", 0, 1), ("up", 0, 1), ("s", 0, -1), ("down", 0, -1),
    ("a", -.5, 0), ("left", -.5, 0), ("d", .5, 0), ("right", .5, 0),
])
def test_keys_and_release(keyboard, key, steer, drive):
    service, clock = keyboard
    service.key(key, True)
    sample = service.snapshot()
    assert (sample.steering, sample.throttle) == (steer, drive)
    assert not sample.frame.acquisition_ready
    service.key(key, False)
    assert service.snapshot().frame == ControlFrame(0, 0, clock.now, sample.frame.session)


def test_simultaneous_aliases_and_opposing_keys(keyboard):
    service, _ = keyboard
    for key in ("w", "up", "d"):
        service.key(key, True)
    service.key("w", False)
    assert (service.snapshot().steering, service.snapshot().throttle) == (.5, 1)
    service.key("down", True)
    service.key("left", True)
    assert service.snapshot().frame.neutral
    assert service.snapshot().steering == 0
    assert not service.snapshot().frame.acquisition_ready


def test_brake_blocks_held_and_new_drive_until_release(keyboard):
    service, _ = keyboard
    service.key("w", True)
    service.key("d", True)
    service.key("space", True)
    service.key("down", True)
    assert (service.snapshot().steering, service.snapshot().throttle) == (0, 0)
    service.key("space", False)
    service.key("w", True, auto_repeat=True)
    service.key("w", False, auto_repeat=True)
    assert (service.snapshot().steering, service.snapshot().throttle) == (0, 0)
    service.key("w", False)
    service.key("w", True)
    assert service.snapshot().throttle == 1


def test_focus_loss_and_repeat_cannot_reactivate_held_drive(keyboard):
    service, _ = keyboard
    service.key("w", True)
    session = service.snapshot().frame.session
    service.set_active(False)
    assert not service.snapshot().connected and service.snapshot().frame is None
    service.key("w", True)
    service.set_active(True)
    service.key("w", True, auto_repeat=True)
    assert service.snapshot().throttle == 0
    assert service.snapshot().frame.session != session


@pytest.mark.parametrize("resume", ["sample", "key"])
def test_stall_recovery_changes_session_and_blocks_held_keys(keyboard, resume):
    service, clock = keyboard
    service.key("w", True)
    original = service.snapshot().frame
    clock.now += .36
    # Worker reads do not fabricate fresh input.
    assert service.snapshot().frame.timestamp == original.timestamp
    if resume == "sample":
        service.sample()
    else:
        service.key("d", True)
    assert service.snapshot().throttle == 0
    assert service.snapshot().frame.session != original.session


def test_acquisition_requires_every_key_released_and_valid_rc_channels(keyboard):
    service, clock = keyboard
    settings = AppSettings(input_source="keyboard", steer_axis=31)
    def check():
        return can_enable_control(settings=settings, link_state=LinkState.CONNECTED,
                                  frame=service.snapshot().frame, axis_count=0, now=clock.now)
    assert check().allowed
    for key in ("w", "s", "space"):
        service.key(key, True)
    assert check().code == "keys_held"
    assert not validate_mapping(replace(settings, steering_channel=2), 0).allowed
    for key in ("w", "s", "space"):
        service.key(key, False)
    assert check().allowed


def test_keyboard_worker_uses_existing_gain_limit_and_stale_stop(keyboard, monkeypatch):
    keys, clock = keyboard
    settings = AppSettings(input_source="keyboard", steering_sensitivity=.5,
                           throttle_sensitivity=.5, throttle_limit=.4)
    wheel = SimpleNamespace(snapshot=lambda: ControllerSnapshot())
    inputs = InputService(wheel, keys)
    inputs.configure(settings)
    mav = MavlinkService()
    mav.configure(settings)
    mav._snapshot = MavlinkSnapshot(running=True, state=LinkState.CONNECTED,
                                    last_heartbeat=clock.now, vehicle_system=1, vehicle_component=1)
    mav.set_control_source(inputs.snapshot)
    sends, releases = [], []
    monkeypatch.setattr(mav, "_send_override", lambda s, t: sends.append((s, t)) or True)
    monkeypatch.setattr(mav, "_send_neutral_then_release", lambda: releases.append(True))
    assert mav.enable_control()[0]
    keys.key("w", True)
    keys.key("d", True)
    mav._control_tick(clock.now)
    assert sends[-1] == (1750, 1600)
    keys.key("space", True)
    mav._control_tick(clock.now)
    assert sends[-1] == (1500, 1500)
    clock.now += .36
    mav._control_tick(clock.now)
    assert releases and mav.snapshot().failsafe_latched
    keys.sample()
    mav._control_tick(clock.now)
    assert not mav.snapshot().control_enabled


def test_input_router_preserves_wheel_timestamp_and_separates_sessions(keyboard):
    keys, clock = keyboard
    wheel_sample = ControllerSnapshot(connected=True, axes=(0, 1, 1),
                                      frame=ControlFrame(.2, .3, 50, keys.snapshot().frame.session))
    inputs = InputService(SimpleNamespace(snapshot=lambda: wheel_sample), keys)
    assert inputs.snapshot() == wheel_sample
    inputs.configure(AppSettings(input_source="keyboard"))
    assert inputs.snapshot().frame.session != wheel_sample.frame.session
    inputs.configure(AppSettings())
    assert inputs.snapshot().frame.timestamp == 50
    assert inputs.snapshot().frame.session != wheel_sample.frame.session


def test_keyboard_diagnostics_without_joystick(keyboard):
    keys, clock = keyboard
    status = build_targeted_status(settings=AppSettings(input_source="keyboard"),
        wheel=keys.snapshot(), devices=[], mav=MavlinkSnapshot(),
        settings_dirty=False, network_dirty=False, now=clock.now)
    assert status.controller.level == "PASS"
    assert status.mapping.level == "PASS"


def test_saved_source_and_legacy_default(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(AppSettings(input_source="keyboard"), path)
    assert load_settings(path).input_source == "keyboard"
    assert AppSettings(input_source="invalid").validate().input_source == "wheel"
    path.write_text('{}')
    assert load_settings(path).input_source == "wheel"

from dataclasses import replace

import pytest

from pctelerc.config import AppSettings, load_settings, save_settings
from pctelerc.core import ControlFrame
from test_control_source import ready


def test_independent_settings_round_trip_and_legacy_default(tmp_path):
    path = tmp_path / 'settings.json'
    save_settings(AppSettings(steering_sensitivity=.35, throttle_sensitivity=.65), path)
    settings = load_settings(path)
    assert settings.steering_sensitivity == .35
    assert settings.throttle_sensitivity == .65
    path.write_text('{"settings_version": 2, "steering_sensitivity": 0.4}')
    settings = load_settings(path)
    assert settings.steering_sensitivity == .4
    assert settings.throttle_sensitivity == 1.0


@pytest.mark.parametrize('value,expected', [(0, .25), (2, 1.0)])
def test_throttle_sensitivity_validation(value, expected):
    settings = AppSettings(throttle_sensitivity=value).validate()
    assert settings.throttle_sensitivity == expected


@pytest.mark.parametrize('drive,expected', [(1, 1700), (-1, 1300), (0, 1500)])
def test_throttle_gain_before_limit_leaves_steering_unchanged(monkeypatch, drive, expected):
    service, sample, clock, sends, releases = ready(monkeypatch)
    service._settings = replace(service._settings, throttle_sensitivity=.5, throttle_limit=.8)
    sample.frame = ControlFrame(.4, drive, clock.now)
    service._control_tick(clock.now)
    assert sends == [(1700, expected)]
    assert not releases


def test_low_gain_cannot_make_pressed_pedal_pass_neutral_gate(monkeypatch):
    service, sample, clock, sends, releases = ready(monkeypatch)
    service.disable_control()
    service._settings = replace(service._settings, throttle_sensitivity=.25)
    sample.frame = ControlFrame(0, .1, clock.now)
    assert not service.enable_control()[0]
    assert not service.arm()[0]


def test_ui_applies_independent_values_and_disables_control_on_edit(monkeypatch):
    from PySide6.QtWidgets import QApplication
    import pctelerc.ui as ui
    from pctelerc.mavlink import MavlinkSnapshot

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(ui, 'load_settings', lambda: AppSettings(steering_sensitivity=.6, throttle_sensitivity=.9))
    saved = []
    monkeypatch.setattr(ui, 'save_settings', lambda settings: saved.append(replace(settings)))
    for cls in (ui.WheelService, ui.MavlinkService):
        monkeypatch.setattr(cls, 'start', lambda self: None)
        monkeypatch.setattr(cls, 'stop', lambda self: None)
    window = ui.MainWindow()
    try:
        assert window.steering_sensitivity.value() == 60
        assert window.throttle_sensitivity.value() == 90
        window.mav._snapshot = MavlinkSnapshot(control_enabled=True)
        disabled = []
        monkeypatch.setattr(window.mav, 'disable_control', lambda: disabled.append(True))
        window.throttle_sensitivity.setValue(45)
        assert disabled and window._settings_dirty
        window.mav._snapshot = MavlinkSnapshot()
        window._apply_settings()
        assert saved[-1].steering_sensitivity == .6
        assert saved[-1].throttle_sensitivity == .45
        window.steering_sensitivity.setValue(35)
        assert window._settings_from_widgets().throttle_sensitivity == .45
        assert window._settings_from_widgets().steering_sensitivity == .35
        assert not window.mav.snapshot().control_enabled
    finally:
        window.close()
        app.processEvents()

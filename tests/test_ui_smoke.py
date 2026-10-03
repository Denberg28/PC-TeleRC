import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import pctelerc.ui as ui
from pctelerc.config import AppSettings


def test_main_window_constructs_with_symmetric_columns_and_modeless_diagnostics(monkeypatch):
    app = QApplication.instance() or QApplication([])

    monkeypatch.setattr(ui, "load_settings", lambda: AppSettings())
    monkeypatch.setattr(ui, "save_settings", lambda *args, **kwargs: None)
    monkeypatch.setattr(ui.WheelService, "start", lambda self: None)
    monkeypatch.setattr(ui.WheelService, "stop", lambda self: None)
    monkeypatch.setattr(ui.MavlinkService, "start", lambda self: None)
    monkeypatch.setattr(ui.MavlinkService, "stop", lambda self: None)

    window = ui.MainWindow()
    try:
        assert [window.main_grid.columnStretch(i) for i in range(3)] == [1, 1, 1]
        assert all(window.main_grid.columnMinimumWidth(i) == 330 for i in range(3))

        window._open_diagnostics()
        app.processEvents()
        assert window._diagnostics_window is not None
        assert not window._diagnostics_window.isModal()
        assert window._diagnostics_window.isVisible()
    finally:
        if window._diagnostics_window is not None:
            window._diagnostics_window.close()
        window.close()
        app.processEvents()


def test_sensitivity_slider_requires_apply_and_preserves_drive_settings(monkeypatch):
    from dataclasses import replace
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QSlider

    app = QApplication.instance() or QApplication([])
    saved = []
    monkeypatch.setattr(ui, "load_settings", lambda: AppSettings(steering_sensitivity=.75))
    monkeypatch.setattr(ui, "save_settings", lambda settings: saved.append(replace(settings)))
    for service in (ui.WheelService, ui.MavlinkService):
        monkeypatch.setattr(service, "start", lambda self: None)
        monkeypatch.setattr(service, "stop", lambda self: None)

    window = ui.MainWindow()
    try:
        assert isinstance(window.steering_sensitivity, QSlider)
        assert window.steering_sensitivity.orientation() == Qt.Orientation.Horizontal
        assert window.steering_sensitivity.minimum() == 25
        assert window.steering_sensitivity.maximum() == 100
        assert window.steering_sensitivity.value() == 75
        assert window.sensitivity_label.text() == "Steering sensitivity: 75%"
        snapshot = replace(window.mav.snapshot(), control_enabled=True)
        monkeypatch.setattr(window.mav, "snapshot", lambda: snapshot)
        disabled = []
        monkeypatch.setattr(window.mav, "disable_control", lambda: disabled.append(True))
        window.steering_sensitivity.setValue(50)
        assert disabled
        assert window._settings_dirty
        assert window.settings.steering_sensitivity == .75
        assert window.sensitivity_label.text() == "Steering sensitivity: 50%"
        window._apply_settings()
        assert saved[-1].steering_sensitivity == .5
        assert saved[-1].throttle_limit == .25
        assert saved[-1].throttle_channel == 2
        assert not window._settings_dirty
    finally:
        window.close()
        app.processEvents()

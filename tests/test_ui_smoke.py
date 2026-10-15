import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import pctelerc.ui as ui
from pctelerc.config import AppSettings


def test_camera_first_window_with_modeless_diagnostics(monkeypatch):
    app = QApplication.instance() or QApplication([])

    monkeypatch.setattr(ui, "load_settings", lambda: AppSettings())
    monkeypatch.setattr(ui, "save_settings", lambda *args, **kwargs: None)
    monkeypatch.setattr(ui.WheelService, "start", lambda self: None)
    monkeypatch.setattr(ui.WheelService, "stop", lambda self: None)
    monkeypatch.setattr(ui.MavlinkService, "start", lambda self: None)
    monkeypatch.setattr(ui.MavlinkService, "stop", lambda self: None)

    window = ui.MainWindow()
    try:
        window.show()
        app.processEvents()
        assert not window.settings_panel.isVisible()
        assert window.camera_view.isVisible()
        assert window.map_panel.isVisible()
        assert window.camera_view.width() > window.map_panel.width()
        assert window.map_panel.y() > window.camera_view.y()
        assert window.steering_sensitivity.label.text() == "100%"
        assert not window.windowIcon().isNull()

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


def test_repeated_window_destruction_releases_native_map_manager(monkeypatch, qt_application):
    import gc
    from PySide6.QtCore import QCoreApplication, QEvent
    from shiboken6 import isValid
    monkeypatch.setattr(ui, 'load_settings', lambda: AppSettings())
    monkeypatch.setattr(ui, 'save_settings', lambda *args, **kwargs: None)
    for _ in range(12):
        window = ui.MainWindow(start_services=False)
        manager = window.rover_map._manager
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        qt_application.processEvents()
        assert not isValid(manager)
        gc.collect()

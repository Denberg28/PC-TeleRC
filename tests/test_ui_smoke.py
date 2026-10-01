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

"""Keep Qt ownership and deferred destruction deterministic across UI tests."""
import gc
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication


@pytest.fixture(autouse=True)
def isolate_operator_data_and_map_network(monkeypatch, tmp_path):
    """Never load operator coordinates or send test map requests externally."""
    from pctelerc.rover_map import RoverMap
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "operator-data"))
    monkeypatch.setattr(RoverMap, "TILE_URL", "http://127.0.0.1:9/{z}/{x}/{y}.png")


@pytest.fixture(scope="session", autouse=True)
def qt_application():
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


@pytest.fixture(autouse=True)
def dispose_test_widgets(qt_application):
    yield
    # QWidget.close() hides a window; it does not destroy its native children.
    # Drain those deletions while QApplication is alive, before Python cycle
    # collection can finalize old network/media objects during the next build.
    for widget in QApplication.topLevelWidgets():
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qt_application.processEvents()
    gc.collect()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


"""Keep one Qt application alive across all UI test modules."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session", autouse=True)
def qt_application():
    # Per-test/module local references must not destroy QApplication while Qt
    # network/media widgets from a previous test still await native cleanup.
    # Creating another QApplication in that state can crash the Windows Qt DLL.
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()

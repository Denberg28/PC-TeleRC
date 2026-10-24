from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from .logging_setup import setup_logging
from .single_instance import SingleInstanceGuard
from .fleet_window import FleetWindow, STYLE


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test-ui":
        import os
        os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
        from .fleet_self_test import run
        return run(sys.argv[2])
    setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("PC TeleRC")
    app.setOrganizationName("Denberg28")
    app.setStyleSheet(STYLE)

    guard = SingleInstanceGuard()
    if not guard.acquire():
        QMessageBox.warning(
            None,
            "PC TeleRC already running",
            "Another PC TeleRC instance is already running.\n\n"
            "Close the existing instance before starting a new one.",
        )
        return 2

    app.aboutToQuit.connect(guard.release)

    window = FleetWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())


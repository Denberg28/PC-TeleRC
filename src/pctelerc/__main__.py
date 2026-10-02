from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from .logging_setup import setup_logging
from .single_instance import SingleInstanceGuard
from .ui import MainWindow, STYLE


def main() -> int:
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

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

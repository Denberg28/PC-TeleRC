from __future__ import annotations
import sys
from PySide6.QtWidgets import QApplication
from .logging_setup import setup_logging
from .ui import MainWindow, STYLE

def main() -> int:
    setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("PC TeleRC")
    app.setOrganizationName("Denberg28")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())

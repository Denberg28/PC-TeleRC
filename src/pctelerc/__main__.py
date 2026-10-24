from __future__ import annotations

import sys

from .logging_setup import setup_logging


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test-ui":
        import os
        os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
        try:
            from .fleet_self_test import run
            return run(sys.argv[2])
        except Exception:
            # A windowed bootloader may otherwise open an invisible error dialog
            # on CI. Record the failure and terminate; never weaken the check.
            import json, traceback
            from pathlib import Path
            from . import __version__
            Path(sys.argv[2]).write_text(json.dumps(dict(version=__version__,passed=False,
                checks={},error=traceback.format_exc()),indent=2))
            return 1
    from PySide6.QtWidgets import QApplication, QMessageBox
    from .single_instance import SingleInstanceGuard
    from .fleet_window import FleetWindow, STYLE
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


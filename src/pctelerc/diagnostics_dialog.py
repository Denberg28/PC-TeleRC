from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from . import __version__
from .config import AppSettings
from .controller import WheelService
from .diagnostics import build_diagnostic_report, build_targeted_status
from .mavlink import MavlinkService


def _status_text(item):
    symbol = {"PASS": "✓", "WARN": "!", "FAIL": "×"}.get(item.level, "•")
    return f"{symbol} {item.name}: {item.detail}"


class DiagnosticsDialog(QDialog):
    def __init__(
        self,
        *,
        settings: AppSettings,
        wheel: WheelService,
        mav: MavlinkService,
        state_provider,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Diagnostics")
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setMinimumWidth(470)
        self._settings = settings
        self._wheel = wheel
        self._mav = mav
        self._state_provider = state_provider
        self._last_report = ""

        layout = QVBoxLayout(self)
        title = QLabel("Field diagnostics")
        title.setStyleSheet("font-size:13pt;font-weight:700;")
        layout.addWidget(title)

        grid = QGridLayout()
        self.rows = {}
        for idx, key in enumerate(("link", "controller", "mapping", "safety")):
            label = QLabel("Checking…")
            label.setWordWrap(True)
            self.rows[key] = label
            grid.addWidget(label, idx, 0)
        layout.addLayout(grid)

        row = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh")
        self.copy_btn = QPushButton("Copy Report")
        self.close_btn = QPushButton("Close")
        row.addWidget(self.refresh_btn)
        row.addWidget(self.copy_btn)
        row.addStretch()
        row.addWidget(self.close_btn)
        layout.addLayout(row)

        self.refresh_btn.clicked.connect(self.refresh_status)
        self.copy_btn.clicked.connect(self.copy_report)
        self.close_btn.clicked.connect(self.close)

        self.copy_reset_timer = QTimer(self)
        self.copy_reset_timer.setSingleShot(True)
        self.copy_reset_timer.timeout.connect(lambda: self.copy_btn.setText("Copy Report"))
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(2000)
        self.refresh_status()

    def _state(self):
        settings, settings_dirty, network_dirty = self._state_provider()
        self._settings = settings
        return settings_dirty, network_dirty

    def refresh_status(self):
        settings_dirty, network_dirty = self._state()
        status = build_targeted_status(
            settings=self._settings,
            wheel=self._wheel.snapshot(),
            devices=self._wheel.devices(),
            mav=self._mav.snapshot(),
            settings_dirty=settings_dirty,
            network_dirty=network_dirty,
        )
        for key in ("link", "controller", "mapping", "safety"):
            item = getattr(status, key)
            self.rows[key].setText(_status_text(item))

    def copy_report(self):
        settings_dirty, network_dirty = self._state()
        report = build_diagnostic_report(
            app_version=__version__,
            settings=self._settings,
            wheel=self._wheel.snapshot(),
            devices=self._wheel.devices(),
            mav=self._mav.snapshot(),
            settings_dirty=settings_dirty,
            network_dirty=network_dirty,
        )
        self._last_report = report.text
        QApplication.clipboard().setText(report.text)
        self.copy_btn.setText("Copied")
        self.copy_reset_timer.start(1200)

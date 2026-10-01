from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit, QVBoxLayout,
)

from . import __version__
from .config import AppSettings
from .controller import WheelService
from .diagnostics import build_diagnostic_report
from .mavlink import MavlinkService


class DiagnosticsDialog(QDialog):
    def __init__(
        self,
        *,
        settings: AppSettings,
        wheel: WheelService,
        mav: MavlinkService,
        settings_dirty: bool,
        network_dirty: bool,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("PC TeleRC Diagnostics")
        self.resize(760, 600)
        self._settings = settings
        self._wheel = wheel
        self._mav = mav
        self._settings_dirty = settings_dirty
        self._network_dirty = network_dirty
        self._last_report = ""

        layout = QVBoxLayout(self)
        title = QLabel("Troubleshooting diagnostics")
        title.setStyleSheet("font-size:15pt;font-weight:700;")
        layout.addWidget(title)

        note = QLabel("Read-only checks only — diagnostics do not ARM, DISARM, or enable PC Control.")
        note.setWordWrap(True)
        layout.addWidget(note)

        self.summary = QLabel("Running checks…")
        layout.addWidget(self.summary)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.output, 1)

        row = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh")
        self.copy_btn = QPushButton("Copy Diagnostic Report")
        self.copy_btn.setObjectName("Primary")
        self.close_btn = QPushButton("Close")
        row.addWidget(self.refresh_btn)
        row.addWidget(self.copy_btn)
        row.addStretch()
        row.addWidget(self.close_btn)
        layout.addLayout(row)

        self.refresh_btn.clicked.connect(self.refresh_report)
        self.copy_btn.clicked.connect(self.copy_report)
        self.close_btn.clicked.connect(self.accept)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_report)
        self.timer.start(1000)
        self.refresh_report()

    def refresh_report(self):
        report = build_diagnostic_report(
            app_version=__version__,
            settings=self._settings,
            wheel=self._wheel.snapshot(),
            devices=self._wheel.devices(),
            mav=self._mav.snapshot(),
            settings_dirty=self._settings_dirty,
            network_dirty=self._network_dirty,
        )
        self._last_report = report.text
        self.output.setPlainText(report.text)
        self.summary.setText(f"{report.failures} failure(s) • {report.warnings} warning(s)")

    def copy_report(self):
        QApplication.clipboard().setText(self._last_report)
        self.summary.setText("Diagnostic report copied to clipboard.")

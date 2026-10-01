from __future__ import annotations

from collections import deque
from statistics import fmean
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout

from .calibration import CalibrationError, CalibrationResult, build_calibration
from .controller import WheelService

STEP_TEXT = {
    "neutral": "Release the wheel and pedals. Center the steering wheel, then capture neutral.",
    "left": "Turn the steering wheel fully LEFT and hold it.",
    "right": "Turn the steering wheel fully RIGHT and hold it.",
    "throttle": "Fully press the THROTTLE pedal and hold it.",
    "brake": "Fully press the BRAKE pedal and hold it.",
    "forward": "Move the combined pedal axis to full FORWARD and hold it.",
    "reverse": "Move the combined pedal axis to full REVERSE and hold it.",
}

class CalibrationDialog(QDialog):
    def __init__(self, wheel: WheelService, pedal_mode: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Wheel calibration")
        self.setModal(True)
        self.setMinimumWidth(520)
        self._wheel = wheel
        self._pedal_mode = pedal_mode
        self._steps = ["neutral", "left", "right"]
        self._steps += ["forward", "reverse"] if pedal_mode == "combined" else ["throttle", "brake"]
        self._index = 0
        self._captures: dict[str, tuple[float, ...]] = {}
        self._samples: deque[tuple[float, ...]] = deque(maxlen=8)
        self.result: CalibrationResult | None = None

        layout = QVBoxLayout(self)
        title = QLabel("Guided PXN / wheel calibration")
        title.setStyleSheet("font-size:15pt;font-weight:700;")
        layout.addWidget(title)

        self.step_label = QLabel()
        self.step_label.setWordWrap(True)
        self.axes_label = QLabel("Waiting for controller axes…")
        self.axes_label.setWordWrap(True)
        self.progress_label = QLabel()
        layout.addWidget(self.step_label)
        layout.addWidget(self.axes_label)
        layout.addWidget(self.progress_label)

        row = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.capture_btn = QPushButton("Capture")
        self.capture_btn.setObjectName("Primary")
        row.addWidget(self.cancel_btn)
        row.addStretch()
        row.addWidget(self.capture_btn)
        layout.addLayout(row)

        self.cancel_btn.clicked.connect(self.reject)
        self.capture_btn.clicked.connect(self._capture)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(50)
        self._show_step()

    def _show_step(self):
        key = self._steps[self._index]
        self.step_label.setText(STEP_TEXT[key])
        self.progress_label.setText(f"Step {self._index + 1} of {len(self._steps)}")
        self.capture_btn.setText("Capture & Finish" if self._index == len(self._steps) - 1 else "Capture & Next")

    def _poll(self):
        snapshot = self._wheel.snapshot()
        if not snapshot.connected or not snapshot.axes:
            self._samples.clear()
            self.axes_label.setText("Controller not detected. Reconnect the wheel before continuing.")
            self.capture_btn.setEnabled(False)
            return
        self._samples.append(snapshot.axes)
        self.capture_btn.setEnabled(True)
        self.axes_label.setText("Live axes: " + ", ".join(f"{i}:{v:+.2f}" for i, v in enumerate(snapshot.axes[:10])))

    def _averaged_axes(self) -> tuple[float, ...]:
        if len(self._samples) < 3:
            raise CalibrationError("Hold the control steady for a moment, then capture again.")
        size = len(self._samples[-1])
        compatible = [s for s in self._samples if len(s) == size]
        if len(compatible) < 3:
            raise CalibrationError("Controller axis count changed during calibration. Reconnect and retry.")
        return tuple(fmean(sample[i] for sample in compatible) for i in range(size))

    def _capture(self):
        try:
            self._captures[self._steps[self._index]] = self._averaged_axes()
            if self._index < len(self._steps) - 1:
                self._index += 1
                self._samples.clear()
                self._show_step()
                return
            self.result = build_calibration(self._captures, self._pedal_mode)
        except CalibrationError as exc:
            QMessageBox.warning(self, "Calibration not accepted", str(exc))
            return
        self.accept()

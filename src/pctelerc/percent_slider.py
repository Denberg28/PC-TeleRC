from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSlider, QWidget


class PercentSlider(QWidget):
    """Compact keyboard-accessible percentage control with a live value label."""
    valueChanged = Signal(int)

    def __init__(self, minimum=0, maximum=100, parent=None):
        super().__init__(parent)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(minimum, maximum)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(5)
        self.label = QLabel()
        self.label.setFixedWidth(42)
        self.label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(self.slider, 1)
        row.addWidget(self.label)
        self.slider.valueChanged.connect(self._changed)
        self._changed(self.slider.value())

    def _changed(self, value):
        self.label.setText(f"{value}%")
        self.valueChanged.emit(value)

    def setValue(self, value):
        self.slider.setValue(round(value))

    def value(self):
        return self.slider.value()

    def setRange(self, minimum, maximum):
        self.slider.setRange(minimum, maximum)

    def setSuffix(self, _suffix):
        pass

"""Compact planning-only popup widgets."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QSpinBox, QVBoxLayout, QHBoxLayout, QPushButton, QAbstractSpinBox


from .theme import STYLE

POPUP_STYLE = STYLE + '''
QLabel#PopupTitle { color:#e8eef6; font-size:16px; font-weight:600; }
QSpinBox { font-size:14px; min-height:24px; }
'''


class ArrivalHoldDialog(QDialog):
    def __init__(self, parent, seconds=5):
        super().__init__(parent)
        self.setWindowTitle('Arrival hold')
        self.setObjectName('ArrivalHoldDialog')
        self.setStyleSheet(POPUP_STYLE)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20,18,20,18);layout.setSpacing(12)
        title = QLabel('Hold on arrival');title.setObjectName('PopupTitle')
        layout.addWidget(title)
        description = QLabel('Pause here, then continue the route.')
        description.setWordWrap(True);layout.addWidget(description)
        self.seconds = QSpinBox()
        self.seconds.setObjectName('holdSeconds')
        self.seconds.setRange(2,10);self.seconds.setValue(seconds)
        self.seconds.setSuffix(' s')
        self.seconds.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.seconds.setAlignment(Qt.AlignmentFlag.AlignCenter)
        duration = QHBoxLayout();duration.setSpacing(8)
        minus,plus = QPushButton('−'),QPushButton('+')
        for button in (minus,plus):
            button.setFixedSize(36,40);button.setStyleSheet('min-width:0; padding:0; font-size:18px;')
        minus.setToolTip('Shorter hold');plus.setToolTip('Longer hold')
        minus.clicked.connect(self.seconds.stepDown);plus.clicked.connect(self.seconds.stepUp)
        def bounds(value):
            minus.setEnabled(value > 2);plus.setEnabled(value < 10)
        self.seconds.valueChanged.connect(bounds);bounds(self.seconds.value())
        duration.addWidget(minus);duration.addWidget(self.seconds,1);duration.addWidget(plus)
        layout.addLayout(duration)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        apply = buttons.button(QDialogButtonBox.StandardButton.Ok)
        apply.setText('Apply');apply.setObjectName('Apply')
        buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setFixedWidth(320)
        self.adjustSize()


def choose_hold(parent):
    dialog = ArrivalHoldDialog(parent)
    accepted = dialog.exec() == QDialog.DialogCode.Accepted
    return dialog.seconds.value(), accepted

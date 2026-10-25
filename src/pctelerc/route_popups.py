"""Compact planning-only popup widgets."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QSpinBox, QVBoxLayout, QHBoxLayout, QPushButton, QAbstractSpinBox


POPUP_STYLE = '''
QDialog { background:#132032; color:#e8edf5; }
QLabel { background:transparent; color:#a5b4c7; font-size:12px; }
QLabel#PopupTitle { color:#eef3fa; font-size:16px; font-weight:600; }
QSpinBox { background:#1c2b40; color:#eef3fa; border:1px solid #3b506c;
 border-radius:5px; padding:7px 10px; font-size:14px; min-height:24px; }
QPushButton { background:#1c2b40; color:#e8edf5; border:1px solid #354961;
 border-radius:5px; padding:7px 14px; min-width:60px; }
QPushButton:hover { border-color:#57c8ac; }
QPushButton#Apply { background:#17614e; border-color:#3caa8b; }
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

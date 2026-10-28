"""Compact dark fleet theme with restrained type and fine panel borders."""
from pathlib import Path

INK = '#e8eef6'
MUTED = '#a4b2c4'
LINE = '#2a3545'

STYLE = '''
QWidget { background:#151e2a; color:#e8eef6; font-family:"Segoe UI"; font-size:12px; }
QWidget#FleetRoot { background:#0d131c; }
QLabel { background:transparent; }
QLabel#Brand { font-size:20px; font-weight:600; }
QDialog { background:#151e2a; }
QLabel#SectionTitle { font-size:15px; font-weight:600; }
QLabel#Muted { color:#a4b2c4; }
QLabel#Warn { color:#e9bd74; }
QFrame#Panel { border:1px solid #2a3545; border-radius:10px; }
QFrame#RoverCard { border:1px solid #2a3545; border-radius:8px; }
QFrame#RoverCard[selected="true"] { border:1px solid #607b94; background:#1b2b3b; }
QPushButton,QComboBox,QSpinBox,QDoubleSpinBox,QLineEdit {
 background:#1c2837; border:1px solid #344154; border-radius:6px;
 padding:6px 9px; min-height:20px; selection-background-color:#2c555f; selection-color:#ffffff; }
QPushButton { font-weight:500; }
QPushButton:hover { background:#222f40; border-color:#607b94; }
QPushButton:pressed { background:#293b50; }
QPushButton:focus,QComboBox:focus,QSpinBox:focus,QDoubleSpinBox:focus,QLineEdit:focus {
 border:1px solid #71cfc5; }
QPushButton#Primary,QPushButton#Apply { background:#1c605e; color:#f1fffd; border-color:#3b9991; }
QPushButton#Primary:hover,QPushButton#Apply:hover { background:#267773; }
QPushButton#Danger { color:#ffaaaa; border-color:#764d57; }
QPushButton#Danger:hover { background:#382530; border-color:#ffaaaa; }
QPushButton#Hold { background:#332b20; color:#f0ca83; border-color:#78613d; }
QPushButton#Hold:hover { background:#493923; }
QPushButton#Disclosure { text-align:left; background:#192331; }
QPushButton#Disclosure:checked { background:#26394d; border-color:#588d9b; }
QFrame#RoverCard QPushButton { padding:4px 7px; min-height:18px; }
QPushButton#RoverSelect { text-align:left; background:transparent; border:0; font-size:14px;
 font-weight:600; padding:2px 3px; min-height:20px; }
QPushButton:disabled,QPushButton#Primary:disabled,QPushButton#Danger:disabled,QPushButton#Hold:disabled {
 background:#19222f; color:#8190a3; border-color:#2a3545; }
QComboBox { padding-right:24px; }
QComboBox::drop-down { border:0; width:22px; }
QComboBox QAbstractItemView { background:#192534; color:#e8eef6; selection-background-color:#26394d;
 selection-color:#e8eef6; border:1px solid #344154; padding:4px; }
QCheckBox { background:transparent; spacing:7px; min-height:22px; }
QCheckBox::indicator { width:14px; height:14px; border:1px solid #607b94; border-radius:3px; background:#101924; }
QCheckBox::indicator:checked { background:#267773; border-color:#71cfc5; }
QScrollArea,QStackedWidget { border:0; background:transparent; }
QScrollArea > QWidget > QWidget { background:transparent; }
QScrollBar:vertical { background:#0d131c; width:8px; margin:0; }
QScrollBar::handle:vertical { background:#3f5065; border-radius:4px; min-height:28px; }
QScrollBar::handle:vertical:hover { background:#60758b; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical { background:none; }
QSplitter::handle { background:#0d131c; width:10px; }
QSplitter::handle:hover { background:#344154; }
QListWidget,QPlainTextEdit,QTableWidget { background:#101924; border:1px solid #2a3545;
 border-radius:6px; selection-background-color:#29445b; selection-color:#e8eef6; }
QListWidget::item { padding:7px 5px; border-bottom:1px solid #243143; }
QListWidget::item:selected { background:#29445b; color:#e8eef6; }
QHeaderView::section { background:#222f40; color:#a4b2c4; border:0; padding:8px; }
QToolTip { background:#26394d; color:#e8eef6; border:0; padding:6px; }
'''

_ASSETS = (Path(__file__).parent/'assets').as_posix()
STYLE += f'''
QCheckBox::indicator:checked {{ image:url("{_ASSETS}/check.svg"); }}
QComboBox::down-arrow {{ image:url("{_ASSETS}/chevron.svg"); width:12px; height:12px; }}
QSpinBox::up-button,QDoubleSpinBox::up-button {{ width:18px; border-left:1px solid #344154; }}
QSpinBox::down-button,QDoubleSpinBox::down-button {{ width:18px; border-left:1px solid #344154; }}
QSpinBox::up-arrow,QDoubleSpinBox::up-arrow {{ image:url("{_ASSETS}/chevron-up.svg"); width:10px; height:10px; }}
QSpinBox::down-arrow,QDoubleSpinBox::down-arrow {{ image:url("{_ASSETS}/chevron.svg"); width:10px; height:10px; }}
'''

MENU_STYLE = '''
QMenu { background:#192534; color:#e8eef6; border:1px solid #344154;
 border-radius:8px; padding:6px 0; font-size:13px; }
QMenu::item { padding:9px 16px; min-width:190px; }
QMenu::item:selected { background:#26394d; color:#e8eef6; }
QMenu::item:disabled { color:#8190a3; }
QMenu::separator { height:1px; background:#2a3545; margin:6px 12px; }
'''

"""Map-first fleet mission station; video is provided by external FPV monitors."""
from pathlib import Path
from dataclasses import replace
import json
import time
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,
    QPushButton,QComboBox,QScrollArea,QStackedWidget,QSplitter,QFrame,QSizePolicy,QLayout,
    QDialog,QLineEdit,QDialogButtonBox,QFileDialog,QCheckBox)
from . import __version__
from .config import data_dir,load_settings,save_settings
from .lora_setup_widget import refresh_ports
from .fleet import draft_path
from .fleet_transport import FleetHub
from .fleet_map import FleetMap
from .mission_widget import MissionDialog
from .mission_service import MissionService
from .core import LinkState

STYLE = '''
QWidget { background:#0f1724; color:#e2e8f0; font-size:12px; }
QPushButton,QComboBox,QSpinBox,QDoubleSpinBox,QLineEdit { background:#1e293b; border:1px solid #334155;
 border-radius:5px; padding:5px 7px; min-height:19px; }
QPushButton:hover { border-color:#34d399; }
QPushButton:disabled { color:#64748b; border-color:#243044; }
QPushButton#Primary { background:#145b48; border-color:#34d399; }
QPushButton#Danger { border-color:#b45354; }
QFrame#RoverCard { border:1px solid #334155; border-radius:7px; }
QLabel#Muted { color:#94a3b8; } QLabel#Warn { color:#fbbf24; }
QScrollArea,QStackedWidget { border:0; }
QScrollBar:vertical { background:#111b29; width:9px; margin:0; }
QScrollBar::handle:vertical { background:#475569; border-radius:4px; min-height:28px; }
QScrollBar::handle:vertical:hover { background:#64748b; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical { background:none; }
QSplitter::handle { background:#172231; width:5px; }
QSplitter::handle:hover { background:#34d399; }
QListWidget { background:#111b29; border:1px solid #243044; border-radius:5px; }
'''


class FleetWindow(QMainWindow):
    def __init__(self, *, hub_factory=FleetHub, draft_root=None):
        super().__init__()
        self.setStyleSheet(STYLE)
        self.hub_factory, self.hub = hub_factory,None
        self.draft_root = Path(draft_root) if draft_root else data_dir()/'fleet-plans'
        self.panels,self.cards = {},{}
        self.selected = 1
        self.settings = load_settings()
        self.setWindowTitle(f'PC TeleRC {__version__} · Fleet missions')
        self.setWindowIcon(QIcon(str(Path(__file__).parent/'assets/telerc.ico')))
        self.resize(1500,860);self.setMinimumSize(1080,660)
        root = QWidget();self.setCentralWidget(root)
        layout = QVBoxLayout(root);layout.setContentsMargins(14,12,14,12);layout.setSpacing(10)
        top = QHBoxLayout()
        brand = QLabel('◉  PC TeleRC');brand.setStyleSheet('font-size:18px; color:#34d399; font-weight:600;')
        top.addWidget(brand);top.addSpacing(15);top.addWidget(QLabel('BASE'))
        self.port = QComboBox();self.port.setEditable(True);self.port.setMinimumWidth(170)
        refresh_ports(self.port)
        self.port.setCurrentText(self.settings.lora_port)
        self.refresh = QPushButton('↻');self.refresh.setToolTip('Refresh native USB ports')
        self.refresh.clicked.connect(lambda:refresh_ports(self.port))
        self.base_button = QPushButton('Open BASE');self.base_button.clicked.connect(self.toggle_base)
        top.addWidget(self.port);top.addWidget(self.refresh);top.addWidget(self.base_button);top.addStretch()
        self.add_button = QPushButton('Add rover')
        self.add_button.setToolTip('Add the lowest unused rover ID; restore its saved plan if available')
        self.add_button.clicked.connect(self.add_next_rover)
        self.remove_button = QPushButton('Remove rover')
        self.remove_button.setToolTip('Remove the selected disconnected rover; keep its saved route')
        self.remove_button.clicked.connect(lambda:self.remove_rover(self.selected))
        top.addWidget(self.add_button);top.addWidget(self.remove_button)
        layout.addLayout(top)
        self.status = QLabel('Offline · plan missions, then connect each rover deliberately')
        self.status.setObjectName('Muted');self.status.setWordWrap(True);layout.addWidget(self.status)
        split = QSplitter(Qt.Orientation.Horizontal);layout.addWidget(split,1)
        self.split = split
        split.setChildrenCollapsible(False)
        split.setOpaqueResize(False)
        roster = QWidget();self.roster_layout = QVBoxLayout(roster);self.roster_layout.setContentsMargins(0,0,8,0)
        roster.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        self.roster_layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.roster_layout.addStretch()
        self.roster = QScrollArea();self.roster.setWidgetResizable(True);self.roster.setWidget(roster)
        self.roster.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.roster.setMinimumWidth(350);split.addWidget(self.roster)
        center = QWidget();center_layout = QVBoxLayout(center);center_layout.setContentsMargins(0,0,0,0)
        tools = QHBoxLayout()
        for label,callback in [('Fit fleet',lambda:self.map.fit_fleet()),('Follow selected',self.follow_selected),
            ('+',lambda:self.map.zoom(1)),('−',lambda:self.map.zoom(-1))]:
            b=QPushButton(label);b.clicked.connect(callback);tools.addWidget(b)
        center_layout.addLayout(tools)
        source_tools = QHBoxLayout()
        offline_button = QPushButton('Offline map');offline_button.clicked.connect(self.open_offline_map)
        source_tools.addWidget(offline_button)
        self.online = QCheckBox('Online tiles');self.online.setChecked(self.settings.map_online)
        source_tools.addWidget(self.online);source_tools.addStretch();center_layout.addLayout(source_tools)
        self.map = FleetMap();self.map.set_online(self.settings.map_online)
        self.map.setMinimumWidth(280)
        self.online.toggled.connect(self.map.set_online)
        if self.settings.map_file:
            try:self.map.set_offline_map(self.settings.map_file)
            except (OSError,ValueError):self.status.setText('Offline map unavailable; choose another map')
        self.map.location.connect(self.add_location)
        center_layout.addWidget(self.map,1);split.addWidget(center)
        right = QWidget();right_layout = QVBoxLayout(right);right_layout.setContentsMargins(8,0,0,0)
        self.plan_title = QLabel('Rover 1 · mission plan');self.plan_title.setStyleSheet('font-size:16px; font-weight:600;')
        right_layout.addWidget(self.plan_title)
        self.stack = QStackedWidget();right_layout.addWidget(self.stack,1)
        right.setMinimumWidth(320);split.addWidget(right)
        self.stack.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Expanding)
        split.setStretchFactor(0,0);split.setStretchFactor(1,1);split.setStretchFactor(2,0)
        split.setSizes([350,790,360])
        self.roster_path=self.draft_root.parent/'fleet-roster.json'
        ids=[1,2,3]
        try:
            if self.roster_path.stat().st_size>1024:raise ValueError
            saved=json.loads(self.roster_path.read_text())
            if not isinstance(saved,list) or not 1<=len(saved)<=20 or len(set(saved))!=len(saved) or any(type(r) is not int or not 1<=r<=20 for r in saved):raise ValueError
            ids=saved
        except (OSError,ValueError,TypeError):pass
        for rover in ids:self.add_rover(rover)
        self.select_rover(ids[0])
        self.timer=QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(100)

    def add_rover(self,rover):
        if type(rover) is not int or not 1 <= rover <= 20:
            self.status.setText('Rover ID must be between 1 and 20')
            return
        if rover in self.panels:
            self.select_rover(rover);return
        def transport(port,identity):
            if self.hub is None:
                raise RuntimeError('Open the fleet BASE first')
            return self.hub.channel(identity)
        service = MissionService(transport,fleet_actions=True,
            operation_gate=self.hub.operation if self.hub else None)
        panel = MissionDialog(lambda: self.hub is not None, service=service,
            draft_path=draft_path(self.draft_root,rover),embedded=True,rover_id=rover)
        panel.external_map=self.map
        self.panels[rover]=panel;self.stack.addWidget(panel)
        service.events.snapshot.connect(lambda s,r=rover,owner=service:self.observe_rover(r,owner,s))
        service.events.message.connect(lambda text,r=rover,owner=service:self.rover_message(r,owner,text))
        card = QFrame(self.roster.widget());card.setObjectName('RoverCard');box=QVBoxLayout(card)
        select = QPushButton(f'Rover {rover}');select.clicked.connect(lambda:self.select_rover(rover));box.addWidget(select)
        state = QLabel('Offline · no telemetry');state.setWordWrap(True);state.setObjectName('Muted')
        state.setFixedHeight(30);box.addWidget(state)
        buttons=QHBoxLayout();buttons.setSpacing(5)
        connect,arm,start,disarm = [QPushButton(t,card) for t in ('Connect','Arm','Mission start','Disarm')]
        start.setObjectName('Primary');disarm.setObjectName('Danger')
        connect.clicked.connect(lambda:self.connect_rover(rover))
        arm.clicked.connect(lambda:self.confirm_action(rover,'arm'))
        start.clicked.connect(lambda:self.start_rover(rover))
        disarm.clicked.connect(lambda:self.confirm_action(rover,'disarm'))
        for b in (connect,arm,start,disarm):
            b.ensurePolished()
            labels=('Connect','Disconnect') if b is connect else (b.text(),)
            b.setMinimumWidth(max(b.fontMetrics().horizontalAdvance(text) for text in labels)+18)
            buttons.addWidget(b)
        box.addLayout(buttons)
        hold=QPushButton('HOLD');hold.setToolTip('Request HOLD for this rover; await fresh FC confirmation')
        hold.clicked.connect(lambda:panel._hold());box.addWidget(hold)
        self.cards[rover]=dict(frame=card,select=select,state=state,connect=connect,arm=arm,start=start,disarm=disarm,hold=hold)
        self.roster_layout.insertWidget(self.roster_layout.count()-1,card)
        self.save_roster()
        self.tick()

    def observe_rover(self, rover, owner, snapshot):
        panel = self.panels.get(rover)
        if panel is not None and panel.service is owner:
            self.map.observe(rover, snapshot)

    def rover_message(self, rover, owner, text):
        panel = self.panels.get(rover)
        if panel is not None and panel.service is owner:
            self.status.setText(f'Rover {rover} · {text}')

    def save_roster(self):
        try:
            self.roster_path.parent.mkdir(parents=True,exist_ok=True)
            temp=self.roster_path.with_suffix('.tmp');temp.write_text(json.dumps(sorted(self.panels)));temp.replace(self.roster_path)
        except OSError:self.status.setText('Roster could not be saved; plans remain separate')

    def add_next_rover(self):
        free = next((i for i in range(1,21) if i not in self.panels), None)
        if free is None:
            self.status.setText('All 20 rover IDs are already in the roster')
            return
        self.add_rover(free)
        self.select_rover(free)

    def remove_rover(self, rover):
        panel = self.panels.get(rover)
        if panel is None:
            return False
        if len(self.panels) == 1:
            self.status.setText('Keep at least one rover in the roster')
            return False
        if panel.service.running or panel.busy:
            self.status.setText(f'Disconnect Rover {rover} before removing it')
            return False
        if not panel._save_draft():
            self.status.setText(f'Rover {rover} route could not be saved · export it before removal')
            return False
        if not panel._shutdown():
            self.status.setText(f'Rover {rover} is still closing; try again')
            return False
        # Save the draft before detaching either widget. Late signals from this
        # retired service cannot populate a newly added rover with the same ID.
        card = self.cards.pop(rover)
        del self.panels[rover]
        self.stack.removeWidget(panel)
        self.roster_layout.removeWidget(card['frame'])
        card['frame'].deleteLater();panel.deleteLater()
        self.map.forget(rover)
        if self.selected == rover:
            self.select_rover(min(self.panels, key=lambda i:abs(i-rover)))
        self.save_roster();self.tick()
        self.status.setText(f'Rover {rover} removed · saved route retained')
        return True

    def select_rover(self,rover):
        if rover not in self.panels:return
        self.selected=rover;self.map.selected_rover=rover
        self.stack.setCurrentWidget(self.panels[rover]);self.plan_title.setText(f'Rover {rover} · mission plan')
        self.map.points=list(self.panels[rover].map.points);self.map.update()
        if self.map.points and rover not in self.map.positions:
            self.map._center=self.map.points[0]
            self.map.auto_fit=False

    def toggle_base(self):
        if self.hub is not None:
            self.close_base();return
        try:
            if not self.port.currentText().strip():raise ValueError('Select the fleet BASE native USB COM port')
            self.hub=self.hub_factory(self.port.currentText().strip())
            for panel in self.panels.values():panel.service.operation_gate=self.hub.operation
            self.settings.lora_port=self.port.currentText().strip();save_settings(self.settings)
            self.base_button.setText('Close BASE');self.port.setEnabled(False);self.refresh.setEnabled(False)
            self.status.setText('Fleet BASE ready · connect rovers individually · measured radio capacity applies')
        except Exception as exc:self.status.setText(str(exc))

    def close_base(self):
        if self.hub is not None:self.hub.close()
        for panel in self.panels.values():panel._disconnect()
        self.hub=None;self.base_button.setText('Open BASE');self.port.setEnabled(True);self.refresh.setEnabled(True)
        self.status.setText('BASE closed · rover state unknown; configured FC loss policies apply')

    def connect_rover(self,rover):
        self.select_rover(rover);panel=self.panels[rover]
        if panel.service.running:panel._disconnect();return
        if self.hub is not None and (self.hub.stopped.is_set() or self.hub.error):self.close_base()
        if self.hub is None:self.toggle_base()
        if self.hub is None:return
        hub=self.hub
        panel.service.transport_factory=lambda _port,identity,h=hub:h.channel(identity)
        panel.port.setCurrentText(self.port.currentText());panel._connect()

    def start_rover(self,rover):
        self.select_rover(rover);self.panels[rover]._submit('start')

    def confirm_action(self,rover,action):
        self.select_rover(rover);panel=self.panels[rover]
        dialog=QDialog(self);dialog.setWindowTitle(f'{action.upper()} · Rover {rover}')
        layout=QVBoxLayout(dialog)
        phrase=f'{action.upper()} ROVER {rover}'
        label=QLabel(('Requests HOLD, verifies stationary GPS and the uploaded mission, then normal FC arming.' if action=='arm'
            else 'Requests HOLD, waits for stationary GPS, then sends normal disarm.')+f'\nType {phrase}')
        label.setWordWrap(True);layout.addWidget(label)
        confirm=QLineEdit();confirm.setObjectName('fleetConfirmation');layout.addWidget(confirm)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(action.capitalize())
        buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        confirm.textChanged.connect(lambda text:buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(text==phrase))
        buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        if dialog.exec()!=QDialog.DialogCode.Accepted or confirm.text()!=phrase:return
        try:
            if action=='disarm':panel.service.request_disarm()
            else:panel.service.submit('arm',panel._items_cache,panel.continue_loss.isChecked(),panel.aux.isChecked())
        except Exception as exc:self.status.setText(f'Rover {rover} · {exc}')

    def follow_selected(self):
        self.map.follow_rover=self.selected
        self.map.auto_fit=False
        if self.selected in self.map.positions:self.map._center=self.map.positions[self.selected][:2]
        self.map.update()

    def add_location(self,lat,lon):
        panel=self.panels[self.selected];panel._add(lat,lon)
        self.map.points=list(panel.map.points);self.map.update()

    def open_offline_map(self):
        path,_=QFileDialog.getOpenFileName(self,'Offline map','','Raster MBTiles (*.mbtiles)')
        if not path:return
        try:
            self.map.set_offline_map(path);self.settings.map_file=path;save_settings(self.settings)
        except (OSError,ValueError) as exc:self.status.setText(str(exc))

    def tick(self):
        now=time.monotonic()
        operation_busy=self.hub is not None and self.hub.operation.locked()
        pending=any(p.service.running and not p.service._confirmed for p in self.panels.values())
        for rover,panel in self.panels.items():
            card=self.cards.get(rover)
            if card is None:continue
            s=panel.service.snapshot;running=panel.service.running
            hub_live=self.hub is not None and not self.hub.stopped.is_set() and not self.hub.error
            fresh=hub_live and running and panel.connected and s.last_heartbeat is not None and 0<=now-s.last_heartbeat<=5
            if not hub_live and s.last_heartbeat is not None:
                self.map.observe(rover,replace(s,running=False,state=LinkState.STALE))
            age=f' · HB {now-s.last_heartbeat:.1f}s' if s.last_heartbeat else ''
            card['state'].setText((f'{"ARMED" if s.armed else "Disarmed"} · {s.mode}{age}' if fresh
                else 'Stale · last-known state' if s.last_heartbeat else panel.service.phase))
            card['state'].setToolTip(panel.service.phase)
            card['connect'].setText('Disconnect' if running else 'Connect')
            card['connect'].setEnabled(running or (not pending and not operation_busy and now>=panel.service.quiet_until))
            gps_live=self.map.fresh(rover)
            card['arm'].setEnabled(gps_live and fresh and not s.armed and s.mode in ('MANUAL','HOLD') and bool(panel.digest) and not panel.busy and not operation_busy and not pending)
            card['start'].setEnabled(gps_live and panel.start_btn.isEnabled() and not operation_busy and not pending)
            card['disarm'].setEnabled(fresh and s.armed)
            card['hold'].setEnabled(fresh)
            name='Primary' if rover==self.selected else ''
            if card['select'].objectName()!=name:
                card['select'].setObjectName(name);card['select'].style().unpolish(card['select']);card['select'].style().polish(card['select'])
        if self.selected in self.panels:
            points = list(self.panels[self.selected].map.points)
            if points != self.map.points:
                self.map.points = points
                self.map.update()
        selected = self.panels.get(self.selected)
        self.add_button.setEnabled(len(self.panels) < 20)
        self.remove_button.setEnabled(len(self.panels) > 1 and selected is not None
            and not selected.service.running and not selected.busy)

    def closeEvent(self,event):
        self.timer.stop();self.close_base()
        if any(panel.service.running for panel in self.panels.values()):
            event.ignore();self.timer.start(100);return
        for panel in self.panels.values():panel._shutdown()
        self.map.shutdown();super().closeEvent(event)

"""Map route editor and explicit LoRa mission commissioning UI."""
from pathlib import Path
import math
import queue
import time

from PySide6.QtCore import Qt, QTimer, Signal, QPointF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QWidget, QLabel, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QListWidget, QPlainTextEdit, QFileDialog, QLineEdit, QDialogButtonBox)

from .mission_plan import Plan, Point, Function, parse_text
from .mission_protocol.client import fingerprint
from .mission_service import MissionService
from .rover_map import RoverMap, world_pixel
from .lora_setup_widget import refresh_ports


class MissionMap(RoverMap):
    location = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.points = []
        self.press = None
        self.moved = False
        self.setMinimumSize(350, 250)

    def mousePressEvent(self, event):
        self.press = event.position() if event.button() == Qt.MouseButton.LeftButton else None
        self.moved = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.press is not None and (event.position()-self.press).manhattanLength() > 5:
            self.moved = True
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.press is not None and not self.moved and self._center is not None:
            x, y = world_pixel(*self._center, self._zoom)
            size = 256*2**self._zoom
            x += event.position().x()-self.width()/2
            y = max(0,min(size,y+event.position().y()-self.height()/2))
            lat = math.degrees(math.atan(math.sinh(math.pi*(1-2*y/size))))
            lon = (x/size*360+180)%360-180
            self.location.emit(lat,lon)
        self.press = None
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._center is None:
            return
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx,cy = world_pixel(*self._center,self._zoom); size=256*2**self._zoom
        previous = None
        for i,point in enumerate(self.points):
            x,y=world_pixel(*point,self._zoom)
            p=QPointF(self.width()/2+(x-cx+size/2)%size-size/2,self.height()/2+y-cy)
            painter.setPen(QPen(QColor('#fbbf24'),2))
            if previous is not None: painter.drawLine(previous,p)
            painter.setBrush(QColor('#142438')); painter.drawEllipse(p,12,12)
            painter.setPen(QColor('white')); painter.drawText(int(p.x()-8),int(p.y()+5),str(i+1))
            previous=p


class MissionDialog(QDialog):
    def __init__(self, prepare_link, parent=None, service=None):
        super().__init__(parent)
        self.prepare_link = prepare_link
        self.service = service or MissionService()
        self.plan = Plan(); self.imported = None; self.digest = ''; self.busy = False; self.connected = False
        self.setWindowTitle('Mission planning · LoRa Mission v0.1.0')
        self.resize(1100,760); self.setMinimumSize(850,600)
        root=QVBoxLayout(self)
        help_text=QLabel('Plan → select rover → connect BASE → upload & verify → arm with RC → confirm START.\n'
            'Mission firmware only. One active rover. No auto-arm, reconnect or resume. Existing manual LoRa uses its original Link profile.')
        help_text.setWordWrap(True); root.addWidget(help_text)
        link=QHBoxLayout(); self.port=QComboBox(); self.port.setEditable(True)
        refresh=QPushButton('Ports'); refresh.clicked.connect(lambda:refresh_ports(self.port))
        self.rover=QSpinBox(); self.rover.setRange(1,20)
        self.connect_btn=QPushButton('Connect mission BASE'); self.connect_btn.clicked.connect(self._connect)
        self.close_btn=QPushButton('Disconnect'); self.close_btn.clicked.connect(self._disconnect)
        for w in (QLabel('BASE USB'),self.port,refresh,QLabel('Rover / SYSID'),self.rover,self.connect_btn,self.close_btn):link.addWidget(w)
        root.addLayout(link)
        self.status=QLabel('Planning only · disconnected'); self.status.setWordWrap(True); root.addWidget(self.status)
        body=QHBoxLayout(); root.addLayout(body,1)
        self.map=MissionMap(); body.addWidget(self.map,2)
        editor=QWidget(); el=QVBoxLayout(editor); el.setContentsMargins(0,0,0,0); body.addWidget(editor,1)
        self.editor=editor
        self.mode=QComboBox(); self.mode.addItem('Waypoint',None)
        for i in range(3):
            for on in (True,False):self.mode.addItem(f'F{i+1} '+('ON' if on else 'OFF'),(i,on))
        el.addWidget(QLabel('Next map tap / Add location')); el.addWidget(self.mode)
        coords=QFormLayout(); self.lat=QDoubleSpinBox(); self.lat.setRange(-85,85);self.lat.setDecimals(7)
        self.lon=QDoubleSpinBox();self.lon.setRange(-180,180);self.lon.setDecimals(7)
        coords.addRow('Latitude',self.lat);coords.addRow('Longitude',self.lon);el.addLayout(coords)
        row=QHBoxLayout(); add=QPushButton('Add location');add.clicked.connect(lambda:self._add(self.lat.value(),self.lon.value()))
        center=QPushButton('Center map');center.clicked.connect(self._center)
        row.addWidget(add);row.addWidget(center);el.addLayout(row)
        self.rows=QListWidget();el.addWidget(self.rows,1)
        row=QHBoxLayout()
        for label,callback in [('↑',lambda:self._move(-1)),('↓',lambda:self._move(1)),('Remove',self._remove),('Clear',self._clear)]:
            b=QPushButton(label);b.clicked.connect(callback);row.addWidget(b)
        el.addLayout(row)
        self.functions=[]
        for i in range(3):
            row=QHBoxLayout();row.addWidget(QLabel(f'F{i+1} output / OFF / ON'))
            ch=QSpinBox();ch.setRange(0,16);ch.setSpecialValueText('Unset')
            off=QSpinBox();off.setRange(1000,2000);off.setValue(1100)
            on=QSpinBox();on.setRange(1000,2000);on.setValue(1900)
            for w in (ch,off,on):row.addWidget(w);w.valueChanged.connect(self._invalidate)
            el.addLayout(row);self.functions.append((ch,off,on))
        self.speed=QDoubleSpinBox();self.speed.setRange(.1,3);self.speed.setSingleStep(.1);self.speed.setValue(.5);self.speed.setSuffix(' m/s')
        self.speed.valueChanged.connect(self._invalidate);el.addWidget(self.speed)
        row=QHBoxLayout();load=QPushButton('Import WPL');save=QPushButton('Export WPL')
        load.clicked.connect(self._import);save.clicked.connect(self._export);row.addWidget(load);row.addWidget(save);el.addLayout(row)
        policy=QHBoxLayout();self.continue_loss=QCheckBox('Continue onboard AUTO after link loss (requires FC profile 2)')
        self.continue_loss.toggled.connect(self._invalidate);policy.addWidget(self.continue_loss);root.addLayout(policy)
        self.aux=QCheckBox('Auxiliary outputs: I verified dedicated channels, OFF PWM, firmware mask and independent cutoff')
        self.aux.toggled.connect(self._invalidate);root.addWidget(self.aux)
        warning=QLabel('Default loss policy: FC HOLD. HOLD does not disarm or guarantee auxiliary OFF. '
            'F events use ArduRover AUTO timing; this firmware cannot verify physical output state. RF delay affects upload/commands, not onboard waypoint timing.')
        warning.setWordWrap(True);root.addWidget(warning)
        row=QHBoxLayout();self.upload_btn=QPushButton('Upload & verify');self.start_btn=QPushButton('Confirm START');self.hold_btn=QPushButton('Request HOLD')
        self.hold_btn.setObjectName('Danger')
        self.upload_btn.clicked.connect(lambda:self._submit('upload'));self.start_btn.clicked.connect(lambda:self._submit('start'));self.hold_btn.clicked.connect(self._hold)
        for w in (self.upload_btn,self.start_btn,self.hold_btn):row.addWidget(w)
        root.addLayout(row)
        self.log=QPlainTextEdit();self.log.setReadOnly(True);self.log.setMaximumBlockCount(150);self.log.setMaximumHeight(105);root.addWidget(self.log)
        self.map.location.connect(self._add)
        e=self.service.events;e.message.connect(self._message);e.snapshot.connect(self._snapshot);e.ready.connect(self._ready);e.verified.connect(self._verified);e.busy.connect(self._busy)
        self.timer=QTimer(self);self.timer.timeout.connect(self._pulse);self.timer.start(100)
        self._controls()

    def _pulse(self):
        self.service.pulse();self._controls()

    def _message(self,text):
        self.status.setText(text);self.log.appendPlainText(text)

    def _snapshot(self,snapshot):
        self.map.set_snapshot(snapshot)
        if snapshot.last_heartbeat:
            self.close_btn.setToolTip(f'Rover {snapshot.vehicle_system}: {snapshot.mode}, '+('ARMED' if snapshot.armed else 'DISARMED'))

    def _ready(self,ready):self.connected=ready;self._controls()
    def _verified(self,digest):self.digest=digest;self._controls()
    def _busy(self,busy):self.busy=busy;self._controls()
    def _invalidate(self,*_):self.digest='';self._controls()

    def _controls(self):
        running=self.service.running
        self.port.setEnabled(not running);self.rover.setEnabled(not running)
        self.connect_btn.setEnabled(not running and time.monotonic()>=self.service.quiet_until)
        self.close_btn.setEnabled(running)
        self.editor.setEnabled(not running);self.mode.setEnabled(not running)
        self.continue_loss.setEnabled(not running);self.aux.setEnabled(not running)
        self.upload_btn.setEnabled(self.connected and not self.busy)
        self.start_btn.setEnabled(self.connected and not self.busy and bool(self.digest))
        self.hold_btn.setEnabled(self.connected)

    def _center(self):
        if abs(self.lat.value())<1e-7 and abs(self.lon.value())<1e-7:
            self._message('Enter reviewed coordinates or import a route to center the planning map');return
        self.map._center=(self.lat.value(),self.lon.value());self.map._follow=False;self.map.update()

    def _add(self,lat,lon):
        if self.service.running:return
        if self.imported is not None:
            self._message('Clear the imported WPL before editing a new map route');return
        if len(self.plan.points)>=60:return
        if abs(lat)<1e-7 and abs(lon)<1e-7:
            self._message('Choose a reviewed location; zero latitude AND longitude rejected');return
        action=self.mode.currentData();actions=[] if action is None else [action]
        self.plan.points.append(Point(lat,lon,actions));self.mode.setCurrentIndex(0)
        self.lat.setValue(lat);self.lon.setValue(lon);self._render();self._invalidate()

    def _render(self):
        self.rows.clear()
        if self.imported is not None:
            for r in parse_text(self.imported)[1:]:
                detail=(f'{r["x"]/1e7:.7f}, {r["y"]/1e7:.7f}' if r['command']==16 else str(r['params']))
                self.rows.addItem(f'{r["seq"]} · CMD {r["command"]} · {detail}')
            self.map.points=[(r['x']/1e7,r['y']/1e7) for r in parse_text(self.imported)[1:] if r['command']==16]
        else:
            for i,p in enumerate(self.plan.points):
                label=', '.join(f'F{f+1} '+('ON' if on else 'OFF') for f,on in p.actions)
                self.rows.addItem(f'{i+1} · {p.latitude:.7f}, {p.longitude:.7f} {label}')
            self.map.points=[(p.latitude,p.longitude) for p in self.plan.points]
        self.map.update()

    def _move(self,delta):
        if self.imported is not None:return
        i=self.rows.currentRow();j=i+delta
        if 0<=i<len(self.plan.points) and 0<=j<len(self.plan.points):
            self.plan.points[i],self.plan.points[j]=self.plan.points[j],self.plan.points[i]
            self._render();self.rows.setCurrentRow(j);self._invalidate()

    def _remove(self):
        if self.imported is None and 0<=self.rows.currentRow()<len(self.plan.points):
            del self.plan.points[self.rows.currentRow()];self._render();self._invalidate()

    def _clear(self):
        self.imported=None;self.plan.points.clear();self._render();self._invalidate()

    def _text(self):
        if self.imported is not None:return self.imported
        self.plan.functions=[Function(ch.value(),off.value(),on.value()) for ch,off,on in self.functions]
        self.plan.speed=self.speed.value()
        return self.plan.wpl()

    def _import(self):
        path,_=QFileDialog.getOpenFileName(self,'Import QGC WPL 110','','Waypoints (*.waypoints *.txt)')
        if not path:return
        try:
            if Path(path).stat().st_size>100000:raise ValueError('Plan file too large')
            text=Path(path).read_text(encoding='utf-8');items=parse_text(text)
            self.imported=text;self._render();self._invalidate()
            p=next((r for r in items[1:] if r['command']==16),None)
            if p:self.map._center=(p['x']/1e7,p['y']/1e7);self.map._follow=False;self.map.update()
        except (OSError,ValueError) as exc:self._message(str(exc))

    def _export(self):
        try:text=self._text();parse_text(text)
        except ValueError as exc:self._message(str(exc));return
        path,_=QFileDialog.getSaveFileName(self,'Export reviewed route','','Waypoints (*.waypoints)')
        if path:
            try:Path(path).write_text(text,encoding='utf-8');self._message('Plan exported; no connection or command sent')
            except OSError as exc:self._message(str(exc))

    def _connect(self):
        try:
            text=self._text();parse_text(text)  # Complete plan validation before opening BASE.
            if not self.prepare_link():return
            self.service.connect(self.port.currentText().strip(),self.rover.value())
            self._controls()
        except (RuntimeError,ValueError) as exc:self._message(str(exc))

    def _disconnect(self):
        self.service.close();self.digest='';self.connected=False
        self._message('Disconnected. Mission/auxiliary state UNKNOWN; FC loss profile applies. Use RC/physical stop as needed.')
        self._controls()

    def _submit(self,action):
        try:
            items=parse_text(self._text());rover=self.rover.value();digest=fingerprint(items,rover)
            if action=='start' and self.digest!=digest:raise ValueError('Exact plan must be uploaded and verified first')
            phrase=f'{"UPLOAD" if action=="upload" else "START"} {rover} {digest[:12]}'
            policy='CONTINUE onboard AUTO on link loss' if self.continue_loss.isChecked() else 'HOLD on GCS loss'
            review='\n'.join(f'{r["seq"]}: CMD {r["command"]} {r["params"]} {r["x"]/1e7:.7f}, {r["y"]/1e7:.7f}' for r in items[1:])
            dialog=QDialog(self);dialog.setWindowTitle(f'Review {action.upper()} · Rover {rover}')
            layout=QVBoxLayout(dialog)
            heading=QLabel(f'Rover {rover}; {len(items)-1} action rows; {policy}.\n'
                f'{"Replaces the stored mission. Rover must be DISARMED MANUAL/HOLD." if action=="upload" else "Arm with RC in MANUAL/HOLD. START is sent once; a missing ACK means UNKNOWN."}\n'
                'Review the exact route/actions below. HOLD does not guarantee accessory OFF.\n'
                f'Type {phrase}')
            heading.setWordWrap(True);layout.addWidget(heading)
            preview=QPlainTextEdit(review);preview.setReadOnly(True);layout.addWidget(preview)
            confirmation=QLineEdit();confirmation.setObjectName('missionConfirmation');layout.addWidget(confirmation)
            buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
            dialog.resize(800,450)
            if dialog.exec()!=QDialog.DialogCode.Accepted or confirmation.text().strip()!=phrase:return
            if not self.connected or self.busy or not self.service.running:raise RuntimeError('Session changed during confirmation')
            self.service.submit(action,items,self.continue_loss.isChecked(),self.aux.isChecked());self.busy=True;self._controls()
        except (ValueError,RuntimeError,queue.Full) as exc:self._message(str(exc))

    def _hold(self):
        self.digest='';self.service.hold();self._message('HOLD requested; awaiting fresh FC HOLD heartbeat. Auxiliary OFF is NOT confirmed.');self._controls()

    def _shutdown(self):
        if getattr(self, "_shutdown_complete", False):
            return True
        if not self.service.close():
            self._message('Mission worker is still closing; try closing again')
            return False
        self.connected=False;self.digest='';self.timer.stop();self.map.shutdown()
        self._shutdown_complete=True
        return True

    def done(self,result):
        if self._shutdown():
            super().done(result)

    def closeEvent(self,event):
        if not self._shutdown():
            event.ignore();return
        super().closeEvent(event)

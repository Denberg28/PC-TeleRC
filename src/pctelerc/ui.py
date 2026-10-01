from __future__ import annotations
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QCheckBox,QComboBox,QDoubleSpinBox,QFormLayout,QFrame,QGridLayout,QHBoxLayout,QLabel,QLineEdit,QMainWindow,QPushButton,QSpinBox,QVBoxLayout,QWidget
from . import __version__
from .config import AppSettings,load_settings,save_settings
from .controller import WheelService
from .core import LinkState
from .mavlink import MavlinkService

STYLE="""
QWidget { background:#11161d; color:#e7edf5; font-family:'Segoe UI'; font-size:10pt; }
QFrame#Card { background:#18202a; border:1px solid #2a3645; border-radius:10px; }
QLabel#Title { font-size:18pt; font-weight:700; }
QLabel#Muted { color:#91a0b2; } QLabel#Good { color:#64d98b; font-weight:700; }
QLabel#Warn { color:#ffc857; font-weight:700; } QLabel#Bad { color:#ff6b6b; font-weight:700; }
QPushButton { background:#253244; border:1px solid #3b4d65; padding:7px 12px; border-radius:7px; }
QPushButton#Primary { background:#1677ff; font-weight:700; } QPushButton#Danger { background:#7a2831; }
QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox { background:#0f141a; border:1px solid #344458; border-radius:6px; padding:5px; }
"""
def card(title):
    f=QFrame(); f.setObjectName("Card"); l=QVBoxLayout(f); l.setContentsMargins(14,14,14,14); h=QLabel(title); h.setStyleSheet("font-weight:700;font-size:12pt;"); l.addWidget(h); return f,l

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle(f"PC TeleRC {__version__}"); self.resize(1160,690); self.settings=load_settings()
        self.wheel=WheelService(); self.mav=MavlinkService(); self._build(); self._apply(); self._wire()
        self.wheel.configure(self.settings); self.wheel.start(); self.mav.configure(self.settings); self.mav.start()
        self.timer=QTimer(self); self.timer.timeout.connect(self._refresh); self.timer.start(50)
    def _build(self):
        root=QWidget(); main=QVBoxLayout(root); main.setContentsMargins(18,16,18,16)
        top=QHBoxLayout(); t=QLabel("PC TeleRC"); t.setObjectName("Title"); top.addWidget(t); top.addWidget(QLabel("Windows MAVLink rover bridge + wheel controller")); top.addStretch(); self.global_status=QLabel("Starting…"); top.addWidget(self.global_status); main.addLayout(top)
        grid=QGridLayout(); main.addLayout(grid,1)
        c,cl=card("MAVLink / ESP32-S3"); form=QFormLayout(); self.bind_host=QLineEdit(); self.listen_port=QSpinBox(); self.listen_port.setRange(1,65535); self.target_host=QLineEdit(); self.target_host.setPlaceholderText("optional, e.g. 192.168.4.1"); self.target_port=QSpinBox(); self.target_port.setRange(1,65535)
        for a,b in [("Listen address",self.bind_host),("UDP port",self.listen_port),("ESP32 target IP",self.target_host),("Target port",self.target_port)]: form.addRow(a,b)
        cl.addLayout(form); self.reconnect_btn=QPushButton("Reconnect"); self.reconnect_btn.setObjectName("Primary"); cl.addWidget(self.reconnect_btn); self.link_label=QLabel("No heartbeat"); self.vehicle_label=QLabel("Vehicle: —"); self.traffic_label=QLabel("RX 0 • TX 0"); cl.addWidget(self.link_label); cl.addWidget(self.vehicle_label); cl.addWidget(self.traffic_label); cl.addStretch(); grid.addWidget(c,0,0)
        w,wl=card("PXN / Game Controller"); self.device_combo=QComboBox(); self.select_btn=QPushButton("Use selected"); r=QHBoxLayout(); r.addWidget(self.device_combo,1); r.addWidget(self.select_btn); wl.addLayout(r)
        f=QFormLayout(); self.pedal_mode=QComboBox(); self.pedal_mode.addItem("Separate throttle + brake","separate"); self.pedal_mode.addItem("Combined pedal axis","combined"); self.steer_axis=QSpinBox(); self.throttle_axis=QSpinBox(); self.brake_axis=QSpinBox()
        for x in (self.steer_axis,self.throttle_axis,self.brake_axis): x.setRange(0,31)
        self.invert_steer=QCheckBox("Invert"); self.invert_throttle=QCheckBox("Invert"); self.invert_brake=QCheckBox("Invert")
        def axisrow(sp,cb):
            q=QWidget(); h=QHBoxLayout(q); h.setContentsMargins(0,0,0,0); h.addWidget(sp); h.addWidget(cb); return q
        f.addRow("Pedal mode",self.pedal_mode); f.addRow("Steering axis",axisrow(self.steer_axis,self.invert_steer)); f.addRow("Throttle axis",axisrow(self.throttle_axis,self.invert_throttle)); f.addRow("Brake axis",axisrow(self.brake_axis,self.invert_brake))
        self.deadzone=QDoubleSpinBox(); self.deadzone.setRange(0,.30); self.deadzone.setSingleStep(.01); self.expo=QDoubleSpinBox(); self.expo.setRange(0,1); self.expo.setSingleStep(.05); f.addRow("Deadzone",self.deadzone); f.addRow("Steering expo",self.expo); wl.addLayout(f)
        self.controller_label=QLabel("Controller: —"); self.axis_label=QLabel("Steer +0.00 • Drive +0.00"); self.raw_axes=QLabel("Axes: —"); self.raw_axes.setWordWrap(True); wl.addWidget(self.controller_label); wl.addWidget(self.axis_label); wl.addWidget(self.raw_axes); wl.addStretch(); grid.addWidget(w,0,1)
        s,sl=card("Safety & Control"); sf=QFormLayout(); self.throttle_limit=QSpinBox(); self.throttle_limit.setRange(5,100); self.throttle_limit.setSuffix(" %"); self.steer_channel=QSpinBox(); self.throttle_channel=QSpinBox(); self.steer_channel.setRange(1,8); self.throttle_channel.setRange(1,8); sf.addRow("Throttle limit",self.throttle_limit); sf.addRow("Steering RC channel",self.steer_channel); sf.addRow("Throttle RC channel",self.throttle_channel); sl.addLayout(sf)
        self.safety_label=QLabel("Control disabled"); self.output_label=QLabel("CH steer 1500 • throttle 1500"); sl.addWidget(self.safety_label); sl.addWidget(self.output_label); ar=QHBoxLayout(); self.arm_btn=QPushButton("ARM"); self.disarm_btn=QPushButton("DISARM"); self.disarm_btn.setObjectName("Danger"); ar.addWidget(self.arm_btn); ar.addWidget(self.disarm_btn); sl.addLayout(ar); self.control_btn=QPushButton("Enable PC Control"); self.control_btn.setObjectName("Primary"); sl.addWidget(self.control_btn); note=QLabel("Never auto-arms. Control requires healthy MAVLink, fresh controller input and neutral throttle."); note.setWordWrap(True); sl.addWidget(note); sl.addStretch(); grid.addWidget(s,0,2)
        st,stl=card("Session status"); self.message=QLabel("Ready"); self.message.setWordWrap(True); stl.addWidget(self.message); guide=QLabel("On controller/link loss PC control latches OFF. Configure ArduRover GCS failsafe independently for network-loss safety."); guide.setWordWrap(True); stl.addWidget(guide); grid.addWidget(st,1,0,1,3)
        self.setCentralWidget(root)
    def _wire(self):
        self.reconnect_btn.clicked.connect(self._reconnect); self.select_btn.clicked.connect(self._select); self.control_btn.clicked.connect(self._toggle); self.arm_btn.clicked.connect(lambda:self._command(self.mav.arm)); self.disarm_btn.clicked.connect(lambda:self._command(self.mav.disarm))
        for x in (self.bind_host,self.listen_port,self.target_host,self.target_port,self.pedal_mode,self.steer_axis,self.throttle_axis,self.brake_axis,self.invert_steer,self.invert_throttle,self.invert_brake,self.deadzone,self.expo,self.throttle_limit,self.steer_channel,self.throttle_channel):
            for sig in ("editingFinished","currentIndexChanged","toggled","valueChanged"):
                q=getattr(x,sig,None)
                if q: q.connect(self._save)
    def _apply(self):
        s=self.settings; self.bind_host.setText(s.bind_host); self.listen_port.setValue(s.listen_port); self.target_host.setText(s.target_host); self.target_port.setValue(s.target_port); self.pedal_mode.setCurrentIndex(max(0,self.pedal_mode.findData(s.pedal_mode))); self.steer_axis.setValue(s.steer_axis); self.throttle_axis.setValue(s.throttle_axis); self.brake_axis.setValue(s.brake_axis); self.invert_steer.setChecked(s.invert_steer); self.invert_throttle.setChecked(s.invert_throttle); self.invert_brake.setChecked(s.invert_brake); self.deadzone.setValue(s.deadzone); self.expo.setValue(s.expo); self.throttle_limit.setValue(round(s.throttle_limit*100)); self.steer_channel.setValue(s.steering_channel); self.throttle_channel.setValue(s.throttle_channel)
    def _read(self):
        return AppSettings(bind_host=self.bind_host.text().strip() or "0.0.0.0",listen_port=self.listen_port.value(),target_host=self.target_host.text().strip(),target_port=self.target_port.value(),wheel_guid=self.settings.wheel_guid,steer_axis=self.steer_axis.value(),throttle_axis=self.throttle_axis.value(),brake_axis=self.brake_axis.value(),pedal_mode=self.pedal_mode.currentData(),invert_steer=self.invert_steer.isChecked(),invert_throttle=self.invert_throttle.isChecked(),invert_brake=self.invert_brake.isChecked(),deadzone=self.deadzone.value(),expo=self.expo.value(),throttle_limit=self.throttle_limit.value()/100,steering_channel=self.steer_channel.value(),throttle_channel=self.throttle_channel.value(),heartbeat_timeout=self.settings.heartbeat_timeout,controller_timeout=self.settings.controller_timeout).validate()
    def _save(self,*_):
        self.settings=self._read(); save_settings(self.settings); self.wheel.configure(self.settings); self.mav.configure(self.settings)
    def _reconnect(self):
        self._save(); self.mav.stop(); self.mav.configure(self.settings); self.mav.start(); self.message.setText("MAVLink listener restarted.")
    def _select(self):
        guid=self.device_combo.currentData()
        if guid: self.settings.wheel_guid=guid; save_settings(self.settings); self.wheel.select(guid); self.message.setText("Controller selection saved.")
    def _toggle(self):
        if self.mav.snapshot().control_enabled: self.mav.disable_control(); self.message.setText("PC control disabled; neutral sent and overrides released.")
        else:
            ok,msg=self.mav.enable_control(); self.message.setText(msg)
            if not ok: QApplication.beep()
    def _command(self,fn):
        ok,msg=fn(); self.message.setText(msg)
        if not ok: QApplication.beep()
    def _refresh(self):
        ws=self.wheel.snapshot(); ms=self.mav.snapshot(); self.mav.set_control_frame(ws.frame)
        devices=self.wheel.devices(); guids=[self.device_combo.itemData(i) for i in range(self.device_combo.count())]
        if guids!=[d.guid for d in devices]:
            self.device_combo.clear()
            for d in devices: self.device_combo.addItem(f"{d.name} ({d.axes} axes)",d.guid)
            idx=self.device_combo.findData(self.settings.wheel_guid)
            if idx>=0: self.device_combo.setCurrentIndex(idx)
        self.controller_label.setText(f"Controller: {ws.name}" if ws.connected else (ws.error or "Controller: not detected")); self.axis_label.setText(f"Steer {ws.steering:+.2f} • Drive {ws.throttle:+.2f}"); self.raw_axes.setText("Axes: "+(", ".join(f"{i}:{v:+.2f}" for i,v in enumerate(ws.axes[:8])) or "—"))
        if ms.state==LinkState.CONNECTED: self.link_label.setText(f"Connected • heartbeat {(ms.heartbeat_age or 0):.1f}s ago")
        elif ms.state==LinkState.STALE: self.link_label.setText("Heartbeat stale — control inhibited")
        else: self.link_label.setText("Waiting for MAVLink heartbeat…")
        self.vehicle_label.setText(f"Vehicle: sys {ms.vehicle_system or '—'} / comp {ms.vehicle_component or '—'} • {ms.mode or 'mode —'} • {'ARMED' if ms.armed else 'disarmed'}"); self.traffic_label.setText(f"RX {ms.rx_messages} • TX {ms.tx_messages}"); self.output_label.setText(f"CH{self.settings.steering_channel} {ms.steer_pwm} • CH{self.settings.throttle_channel} {ms.throttle_pwm}")
        if ms.control_enabled: self.safety_label.setText("PC CONTROL ACTIVE"); self.control_btn.setText("Disable PC Control")
        elif ms.failsafe_latched: self.safety_label.setText("FAIL-SAFE LATCHED — re-enable manually"); self.control_btn.setText("Re-enable PC Control")
        else: self.safety_label.setText("Control disabled"); self.control_btn.setText("Enable PC Control")
        if ms.error: self.message.setText(ms.error)
        self.global_status.setText("Ready" if ms.state==LinkState.CONNECTED and ws.connected else "Setup required"); self.arm_btn.setEnabled(ms.state==LinkState.CONNECTED); self.disarm_btn.setEnabled(ms.state==LinkState.CONNECTED)
    def closeEvent(self,event):
        self.mav.disable_control(); self.mav.stop(); self.wheel.stop(); save_settings(self.settings); event.accept()

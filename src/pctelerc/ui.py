from __future__ import annotations

from dataclasses import replace
import time
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton,
    QSpinBox, QSizePolicy, QVBoxLayout, QWidget, QDialog, QScrollArea, QTabWidget,
)

from . import __version__
from .calibration_dialog import CalibrationDialog
from .config import AppSettings, load_settings, save_settings
from .controller import WheelService
from .keyboard import InputService, KeyboardService
from .core import LinkState
from .diagnostics_dialog import DiagnosticsDialog
from .mavlink import MavlinkService
from .lora_setup_widget import LoRaSetupWidget, refresh_ports
from .camera import CameraView, stored_camera_url
from .percent_slider import PercentSlider
from .rover_map import RoverMap, position_fresh

STYLE = """
QWidget { background:#10151c; color:#e7edf5; font-family:'Segoe UI'; font-size:9pt; }
QLabel { background:transparent; }
QFrame#Card { background:#17202b; border:1px solid #2a3645; border-radius:8px; }
QLabel#Title { font-size:13pt; font-weight:700; }
QLabel#Muted { color:#91a0b2; }
QLabel#Good { color:#64d98b; font-weight:700; }
QLabel#Warn { color:#ffc857; font-weight:700; }
QLabel#Bad { color:#ff6b6b; font-weight:700; }
QPushButton { background:#253244; border:1px solid #3b4d65; padding:5px 9px; border-radius:6px; min-height:18px; }
QPushButton:hover { border-color:#5c7392; }
QPushButton:disabled { color:#677587; background:#1a222d; border-color:#273342; }
QPushButton#Primary { background:#1677ff; font-weight:700; }
QPushButton#Danger { background:#7a2831; }
QComboBox QAbstractItemView { background:#18202a; color:#e7edf5; selection-background-color:#1677ff; selection-color:#ffffff; }
QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox { background:#0f141a; border:1px solid #344458; border-radius:6px; padding:5px; }
QSlider::groove:horizontal { height:4px; background:#344458; border-radius:2px; }
QSlider::sub-page:horizontal { background:#38bdf8; border-radius:2px; }
QSlider::handle:horizontal { background:#e2e8f0; width:12px; margin:-4px 0; border-radius:6px; }
QTabWidget::pane { border:0; }
QTabBar::tab { background:#17202b; padding:7px 10px; }
QTabBar::tab:selected { color:#38bdf8; border-bottom:2px solid #38bdf8; }
QScrollArea { border:0; }
"""

def card(title: str):
    frame = QFrame()
    frame.setObjectName("Card")
    frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 14, 14, 14)
    heading = QLabel(title)
    heading.setStyleSheet("font-weight:700;font-size:12pt;")
    layout.addWidget(heading)
    return frame, layout


class MainWindow(QMainWindow):
    def __init__(self, *, start_services=True):
        super().__init__()
        self.setWindowTitle(f"PC TeleRC {__version__}")
        self.resize(1180, 720)
        self.setMinimumSize(900, 580)
        self.setWindowIcon(QIcon(str(Path(__file__).parent / "assets" / "telerc.ico")))
        self.settings = load_settings()
        self._settings_dirty = False
        self._network_dirty = False
        self._diagnostics_window = None
        self._lora_dialog = None
        self._restart_pending = False
        self._restart_generation = 0
        self._restart_settings = None
        self._connected_settings = replace(self.settings)

        self.wheel = WheelService()
        self.keyboard = KeyboardService()
        self.inputs = InputService(self.wheel, self.keyboard)
        self.mav = MavlinkService()
        self.mav.set_control_source(self.inputs.snapshot)

        self._build()
        self._apply_settings_to_widgets()
        self._wire_buttons_and_fields()

        self.wheel.configure(self.settings)
        self.inputs.configure(self.settings)
        if start_services:
            self.wheel.start()
        self.mav.configure(self.settings)
        if start_services:
            self.mav.start()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(50)
        self.keyboard_timer = QTimer(self)
        self.keyboard_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.keyboard_timer.timeout.connect(self._sample_keyboard)
        self.keyboard_timer.start(20)
        QApplication.instance().installEventFilter(self)
        self._update_input_fields()

    def _build(self):
        root = QWidget()
        main = QVBoxLayout(root)
        main.setContentsMargins(18, 16, 18, 16)
        main.setSpacing(12)

        top = QHBoxLayout()
        title = QLabel("PC TeleRC")
        title.setObjectName("Title")
        top.addWidget(title)
        subtitle = QLabel("MAVLink rover bridge • wheel / keyboard")
        subtitle.setObjectName("Muted")
        top.addWidget(subtitle)
        top.addStretch()
        self.global_status = QLabel("Starting…")
        top.addWidget(self.global_status)
        main.addLayout(top)

        grid = QGridLayout()
        self.main_grid = grid
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        for column in range(3):
            grid.setColumnStretch(column, 1)
            grid.setColumnMinimumWidth(column, 330)
        main.addLayout(grid, 1)

        connection_card, connection = card("1. Connection")
        form = QFormLayout()
        self.connection_form = form
        self.link_mode = QComboBox()
        self.link_mode.addItem("ESP32-S3 / LilyGO · Wi-Fi", "telerc_udp")
        self.link_mode.addItem("LilyGO T3S3 SX1262 · LoRa", "lora_usb")
        self.link_mode.addItem("HGLRC T ONE 900 MHz · ELRS", "elrs_serial")
        self.link_mode.setAccessibleName("Radio connection")
        form.addRow("Link", self.link_mode)
        self.bind_host = QLineEdit()
        self.listen_port = QSpinBox()
        self.listen_port.setRange(1, 65535)
        self.target_host = QLineEdit()
        self.target_host.setPlaceholderText("optional, e.g. 192.168.4.1")
        self.target_port = QSpinBox()
        self.target_port.setRange(1, 65535)
        form.addRow("Listen address", self.bind_host)
        form.addRow("UDP port", self.listen_port)
        form.addRow("ESP32 target IP", self.target_host)
        form.addRow("Target port", self.target_port)
        self.lora_port = QComboBox()
        self.elrs_port = QComboBox()
        for port in (self.lora_port, self.elrs_port):
            port.setEditable(True)
            port.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            port.lineEdit().setPlaceholderText("Select COM port")
        form.addRow("LoRa BASE port", self.lora_port)
        form.addRow("ELRS module port", self.elrs_port)
        connection.addLayout(form)
        self.link_hint = QLabel()
        self.link_hint.setWordWrap(True)
        self.link_hint.setObjectName("Muted")
        connection.addWidget(self.link_hint)
        radio_buttons = QHBoxLayout()
        self.refresh_ports_btn = QPushButton("Refresh ports")
        self.lora_setup_btn = QPushButton("LoRa setup…")
        radio_buttons.addWidget(self.refresh_ports_btn)
        radio_buttons.addWidget(self.lora_setup_btn)
        connection.addLayout(radio_buttons)

        self.reconnect_btn = QPushButton("Apply & Reconnect")
        self.reconnect_btn.setObjectName("Primary")
        self.reconnect_btn.setToolTip("Release the old link, apply the selected radio, and wait for a fresh heartbeat.")
        self.disconnect_btn = QPushButton("Disconnect")
        connection.addWidget(self.reconnect_btn)
        connection.addWidget(self.disconnect_btn)

        self.link_label = QLabel("No heartbeat")
        self.vehicle_label = QLabel("Vehicle: —")
        self.traffic_label = QLabel("RX 0 • TX 0")
        connection.addWidget(self.link_label)
        connection.addWidget(self.vehicle_label)
        connection.addWidget(self.traffic_label)
        connection.addStretch()
        grid.addWidget(connection_card, 0, 0)

        wheel_card, wheel_layout = card("2. Driving Input")
        self.input_source = QComboBox()
        self.input_source.addItem("Wheel / game controller", "wheel")
        self.input_source.addItem("Keyboard — WASD / arrows", "keyboard")
        wheel_layout.addWidget(self.input_source)
        self.keyboard_pad = QLabel("Click here to drive\nW / ↑ forward • S / ↓ reverse\nA / ← left • D / → right\nHold Space: brake / neutral")
        self.keyboard_pad.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.keyboard_pad.setStyleSheet("QLabel { padding:12px; border:1px solid #344458; border-radius:6px; } QLabel:focus { border:2px solid #1677ff; }")
        self.keyboard_pad.setToolTip("Enable PC Control with all keys released. Focus loss stops control; re-enable manually. Space commands neutral, not reverse torque.")
        wheel_layout.addWidget(self.keyboard_pad)
        device_row = QHBoxLayout()
        self.device_combo = QComboBox()
        self.select_btn = QPushButton("Use selected")
        self.select_btn.setToolTip("Select the highlighted Windows controller for PC TeleRC.")
        device_row.addWidget(self.device_combo, 1)
        device_row.addWidget(self.select_btn)
        wheel_layout.addLayout(device_row)

        self.calibrate_btn = QPushButton("Calibrate wheel & pedals")
        self.calibrate_btn.setObjectName("Primary")
        self.calibrate_btn.setToolTip("Capture neutral, steering extremes, and pedal extremes. PC control is disabled before calibration.")
        wheel_layout.addWidget(self.calibrate_btn)

        wheel_form = QFormLayout()
        self.wheel_form = wheel_form
        self.pedal_mode = QComboBox()
        self.pedal_mode.addItem("Separate throttle + brake", "separate")
        self.pedal_mode.addItem("Combined pedal axis", "combined")
        self.steer_axis = QSpinBox()
        self.throttle_axis = QSpinBox()
        self.brake_axis = QSpinBox()
        for control in (self.steer_axis, self.throttle_axis, self.brake_axis):
            control.setRange(0, 31)

        self.invert_steer = QCheckBox("Invert")
        self.invert_throttle = QCheckBox("Invert")
        self.invert_brake = QCheckBox("Invert")

        def axis_row(spin, checkbox):
            widget = QWidget()
            row = QHBoxLayout(widget)
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(spin)
            row.addWidget(checkbox)
            return widget

        wheel_form.addRow("Pedal mode", self.pedal_mode)
        wheel_form.addRow("Steering axis", axis_row(self.steer_axis, self.invert_steer))
        wheel_form.addRow("Throttle axis", axis_row(self.throttle_axis, self.invert_throttle))
        wheel_form.addRow("Brake axis", axis_row(self.brake_axis, self.invert_brake))

        self.deadzone = PercentSlider(0,30)
        self.expo = PercentSlider(0,100)
        self.steering_sensitivity = PercentSlider()
        self.steering_sensitivity.setRange(25, 100)
        self.steering_sensitivity.setSuffix(" %")
        self.steering_sensitivity.setToolTip("Scale steering authority. 100% = full steering command; lower values reduce steering gain.")
        self.throttle_sensitivity = PercentSlider()
        self.throttle_sensitivity.setRange(25, 100)
        self.throttle_sensitivity.setSuffix(" %")
        self.throttle_sensitivity.setToolTip("Scale forward/reverse pedal commands independently of steering, before the throttle limit. Neutral checks use the unscaled pedal input.")
        wheel_form.addRow("Deadzone", self.deadzone)
        wheel_form.addRow("Steering expo", self.expo)
        wheel_form.addRow("Steering sensitivity", self.steering_sensitivity)
        wheel_form.addRow("Throttle sensitivity", self.throttle_sensitivity)
        wheel_layout.addLayout(wheel_form)

        self.apply_btn = QPushButton("Apply Settings")
        self.apply_btn.setToolTip("Save controller and safety settings without restarting the MAVLink listener.")
        wheel_layout.addWidget(self.apply_btn)

        self.controller_label = QLabel("Controller: —")
        self.axis_label = QLabel("Steer +0.00 • Drive +0.00")
        self.raw_axes = QLabel("Axes: —")
        self.raw_axes.setWordWrap(True)
        wheel_layout.addWidget(self.controller_label)
        wheel_layout.addWidget(self.axis_label)
        wheel_layout.addWidget(self.raw_axes)
        wheel_layout.addStretch()
        grid.addWidget(wheel_card, 0, 1)

        safety_card, safety = card("3. Safety & Control")
        safety_form = QFormLayout()
        self.throttle_limit = PercentSlider()
        self.throttle_limit.setRange(5, 100)
        self.throttle_limit.setSuffix(" %")
        self.steer_channel = QSpinBox()
        self.throttle_channel = QSpinBox()
        self.steer_channel.setRange(1, 8)
        self.throttle_channel.setRange(1, 8)
        safety_form.addRow("Throttle limit", self.throttle_limit)
        safety_form.addRow("Steering RC channel", self.steer_channel)
        safety_form.addRow("Throttle RC channel", self.throttle_channel)
        safety.addLayout(safety_form)

        self.safety_label = QLabel("Control disabled")
        self.output_label = QLabel("CH steer 1500 • throttle 1500")
        safety.addWidget(self.safety_label)
        safety.addWidget(self.output_label)

        arm_row = QHBoxLayout()
        self.arm_btn = QPushButton("ARM")
        self.arm_btn.setToolTip("Send explicit ARM after neutral/link checks. For LilyGO Wi-Fi, enable PC Control at neutral first.")
        self.disarm_btn = QPushButton("DISARM")
        self.disarm_btn.setObjectName("Danger")
        self.disarm_btn.setToolTip("Send an explicit disarm command to the linked vehicle.")
        arm_row.addWidget(self.arm_btn)
        arm_row.addWidget(self.disarm_btn)
        safety.addLayout(arm_row)

        self.control_btn = QPushButton("Enable PC Control")
        self.control_btn.setObjectName("Primary")
        self.control_btn.setToolTip("Enable RC override only with a healthy link and fresh selected input at neutral. Keyboard requires all driving keys released.")
        safety.addWidget(self.control_btn)

        self.diagnostics_btn = QPushButton("Diagnostics")
        self.diagnostics_btn.setToolTip("Run read-only troubleshooting checks and copy a diagnostic report.")
        safety.addWidget(self.diagnostics_btn)

        note = QLabel("Never auto-arms or auto-resumes control. Link/controller loss latches PC control OFF.")
        note.setWordWrap(True)
        safety.addWidget(note)
        safety.addStretch()
        grid.addWidget(safety_card, 0, 2)

        status_card, status = card("Session status")
        self.settings_state = QLabel("Settings applied")
        self.settings_state.setObjectName("Muted")
        self.message = QLabel("Ready")
        self.message.setWordWrap(True)
        guide = QLabel("ArduRover GCS/telemetry fail-safe remains mandatory for true Wi-Fi-loss protection.")
        self.guide = guide
        guide.setWordWrap(True)
        guide.setObjectName("Muted")
        status.addWidget(self.settings_state)
        status.addWidget(self.message)
        status.addWidget(guide)
        grid.addWidget(status_card, 1, 0, 1, 3)

        # Rehome the established controls into a compact flight-view shell.
        # Their handlers and control-worker paths remain the same.
        old_keyboard_pad = self.keyboard_pad
        old_keyboard_pad.hide()
        old_keyboard_pad.deleteLater()
        self.keyboard_pad = CameraView()
        self.camera_view = self.keyboard_pad
        self.camera_view.setToolTip("Click the camera area for keyboard driving. WASD / arrows; hold Space for neutral brake. Focus loss disables PC Control.")
        for layout, widget in ((wheel_form, self.steering_sensitivity),
                               (wheel_form, self.throttle_sensitivity),
                               (safety_form, self.throttle_limit), (form, self.link_mode)):
            row = layout.takeRow(widget)
            if row.labelItem and row.labelItem.widget():
                row.labelItem.widget().deleteLater()
        for widget in (self.input_source, self.arm_btn, self.disarm_btn, self.control_btn,
                       self.diagnostics_btn, self.global_status, self.link_label,
                       self.vehicle_label, self.controller_label, self.axis_label,
                       self.safety_label, self.output_label, self.message, self.settings_state):
            widget.setParent(None)
        screen = QWidget()
        screen_layout = QVBoxLayout(screen)
        screen_layout.setContentsMargins(10, 8, 10, 8)
        screen_layout.setSpacing(8)
        header = QHBoxLayout()
        self.brand_logo = QLabel()
        self.brand_logo.setPixmap(QPixmap(str(Path(__file__).parent / "assets" / "telerc.png")).scaled(36,36,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        self.brand_logo.setFixedSize(36,36)
        header.addWidget(self.brand_logo)
        brand = QLabel(f"PC TeleRC\n{__version__}")
        brand.setObjectName("Title")
        header.addWidget(brand)
        header.addSpacing(14)
        self.link_mode.setMaximumWidth(220)
        self.input_source.setMaximumWidth(190)
        header.addWidget(self.link_mode)
        header.addWidget(self.input_source)
        header.addStretch()
        header.addWidget(self.global_status)
        self.global_status.setMinimumWidth(105)
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setCheckable(True)
        self.settings_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        header.addWidget(self.settings_btn)
        screen_layout.addLayout(header)
        health = QHBoxLayout()
        self.link_label.setMinimumWidth(220)
        health.addWidget(self.link_label, 1)
        health.addWidget(self.vehicle_label)
        self.telemetry_label = QLabel("GPS —   Speed —   Battery —")
        health.addWidget(self.telemetry_label)
        self.camera_status = QLabel("Camera off")
        self.camera_status.setObjectName("Muted")
        health.addStretch()
        health.addWidget(self.camera_status)
        screen_layout.addLayout(health)
        self.camera_view.statusChanged.connect(self._camera_status_changed)
        body = QHBoxLayout()
        self.camera_surface = QWidget()
        self.camera_surface.setMinimumWidth(480)
        viewport = QGridLayout(self.camera_surface)
        viewport.setContentsMargins(0,0,0,0)
        viewport.addWidget(self.camera_view, 0, 0)
        self.map_panel = QFrame()
        self.map_panel.setObjectName("Card")
        self.map_panel.setFixedSize(282,214)
        map_layout = QVBoxLayout(self.map_panel)
        map_layout.setContentsMargins(3,3,3,3)
        map_layout.setSpacing(2)
        self.rover_map = RoverMap()
        map_layout.addWidget(self.rover_map,1)
        map_buttons = QHBoxLayout()
        map_buttons.addWidget(QLabel("Rover map"),1)
        for text, step in (("−",-1),("+",1)):
            button = QPushButton(text)
            button.setFixedWidth(28)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(lambda _checked=False, value=step:self.rover_map.zoom(value))
            map_buttons.addWidget(button)
        map_layout.addLayout(map_buttons)
        viewport.addWidget(self.map_panel,0,0,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignBottom)
        body.addWidget(self.camera_surface,1)
        self.settings_panel = QWidget()
        self.settings_panel.setFixedWidth(338)
        panel_layout = QVBoxLayout(self.settings_panel)
        panel_layout.setContentsMargins(0,0,0,0)
        self.settings_tabs = QTabWidget()
        def tab(widget, title):
            scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(widget)
            self.settings_tabs.addTab(scroll,title)
        tab(connection_card,"Link")
        self.guide.setParent(connection_card)
        connection.addWidget(self.guide)
        input_page=QWidget(); input_layout=QVBoxLayout(input_page)
        input_layout.setContentsMargins(0,0,0,0)
        input_layout.addWidget(wheel_card)
        input_layout.addWidget(safety_card)
        tab(input_page,"Input")
        camera_card, camera_layout=card("Camera & map")
        camera_form=QFormLayout()
        self.camera_form=camera_form
        self.camera_mode=QComboBox()
        self.camera_mode.addItem("USB camera","usb")
        self.camera_mode.addItem("RTSP / HTTP video","network")
        self.camera_mode.addItem("HTTP MJPEG","mjpeg")
        self.camera_device=QComboBox()
        self.camera_url=QLineEdit()
        self.camera_url.setPlaceholderText("rtsp://camera/stream or http://camera:81/stream")
        self.camera_url.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        camera_form.addRow("Source",self.camera_mode)
        camera_form.addRow("USB device",self.camera_device)
        camera_form.addRow("Stream URL",self.camera_url)
        camera_layout.addLayout(camera_form)
        camera_row=QHBoxLayout()
        self.camera_refresh_btn=QPushButton("Refresh")
        self.camera_start_btn=QPushButton("Start")
        self.camera_stop_btn=QPushButton("Stop")
        for button in (self.camera_refresh_btn,self.camera_start_btn,self.camera_stop_btn):
            camera_row.addWidget(button)
        camera_layout.addLayout(camera_row)
        camera_note=QLabel("Video needs its own USB or network camera connection. LoRa carries driving commands, not video. Camera starts only when requested.")
        camera_note.setWordWrap(True); camera_note.setObjectName("Muted")
        camera_layout.addWidget(camera_note)
        self.map_online=QCheckBox("Online map tiles")
        camera_layout.addWidget(self.map_online)
        camera_layout.addStretch()
        tab(camera_card,"Camera")
        panel_layout.addWidget(self.settings_tabs)
        panel_layout.addWidget(self.settings_state)
        self.settings_panel.hide()
        body.addWidget(self.settings_panel)
        screen_layout.addLayout(body,1)
        adjustments=QHBoxLayout()
        for title, widget in (("Steer",self.steering_sensitivity),("Drive",self.throttle_sensitivity),("Limit",self.throttle_limit)):
            adjustments.addWidget(QLabel(title))
            widget.setMinimumWidth(140)
            adjustments.addWidget(widget,1)
        screen_layout.addLayout(adjustments)
        controls=QHBoxLayout()
        for button in (self.control_btn,self.arm_btn,self.disarm_btn,self.diagnostics_btn):
            controls.addWidget(button)
        controls.addWidget(self.safety_label,1)
        self.keyboard_hint=QLabel("WASD / arrows • Space brake")
        self.keyboard_hint.setObjectName("Muted")
        controls.addWidget(self.keyboard_hint)
        screen_layout.addLayout(controls)
        footer=QHBoxLayout()
        footer.addWidget(self.message,1)
        footer.addWidget(self.axis_label)
        footer.addWidget(self.output_label)
        screen_layout.addLayout(footer)
        self.controller_label.hide()
        self.setCentralWidget(screen)
        root.deleteLater()

    def _wire_buttons_and_fields(self):
        self.settings_btn.toggled.connect(self._toggle_settings_panel)
        self.camera_mode.currentIndexChanged.connect(self._update_camera_fields)
        self.camera_refresh_btn.clicked.connect(self._refresh_cameras)
        self.camera_start_btn.clicked.connect(self._start_camera)
        self.camera_stop_btn.clicked.connect(self.camera_view.stop)
        self.map_online.toggled.connect(self._set_map_online)
        self.input_source.currentIndexChanged.connect(self._update_input_fields)
        self.control_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.arm_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.disarm_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # Button audit: every operator action has exactly one explicit handler.
        self.reconnect_btn.clicked.connect(self._apply_and_reconnect)
        self.disconnect_btn.clicked.connect(self._disconnect_link)
        self.refresh_ports_btn.clicked.connect(self._refresh_radio_ports)
        self.lora_setup_btn.clicked.connect(self._open_lora_setup)
        self.link_mode.currentIndexChanged.connect(self._update_link_fields)
        self.lora_port.currentTextChanged.connect(lambda *_: self._mark_dirty(True))
        self.elrs_port.currentTextChanged.connect(lambda *_: self._mark_dirty(True))
        self.select_btn.clicked.connect(self._select_controller)
        self.calibrate_btn.clicked.connect(self._calibrate_controller)
        self.apply_btn.clicked.connect(self._apply_settings)
        self.control_btn.clicked.connect(self._toggle_control)
        self.diagnostics_btn.clicked.connect(self._open_diagnostics)
        self.arm_btn.clicked.connect(lambda: self._vehicle_command(self.mav.arm))
        self.disarm_btn.clicked.connect(lambda: self._vehicle_command(self.mav.disarm, allow_dirty=True))

        non_network = (
            self.input_source,
            self.pedal_mode, self.steer_axis, self.throttle_axis, self.brake_axis,
            self.invert_steer, self.invert_throttle, self.invert_brake,
            self.deadzone, self.expo, self.steering_sensitivity, self.throttle_sensitivity, self.throttle_limit,
            self.steer_channel, self.throttle_channel,
        )
        for widget in non_network:
            self._connect_change(widget, network=False)
        for widget in (self.link_mode, self.bind_host, self.listen_port, self.target_host, self.target_port):
            self._connect_change(widget, network=True)

    def _connect_change(self, widget, *, network: bool):
        for signal_name in ("textChanged", "currentIndexChanged", "toggled", "valueChanged"):
            signal = getattr(widget, signal_name, None)
            if signal is not None:
                signal.connect(lambda *_args, is_network=network: self._mark_dirty(is_network))
                return

    def _update_input_fields(self, *_):
        keyboard = self.input_source.currentData() == "keyboard"
        self.keyboard_hint.setVisible(keyboard)
        for row in range(6):
            self.wheel_form.setRowVisible(row, not keyboard)
        for widget in (self.device_combo, self.select_btn, self.calibrate_btn, self.raw_axes):
            widget.setVisible(not keyboard)
        for widget in (self.device_combo, self.select_btn, self.calibrate_btn,
                       self.pedal_mode, self.steer_axis, self.throttle_axis,
                       self.brake_axis, self.invert_steer, self.invert_throttle,
                       self.invert_brake, self.deadzone, self.expo):
            widget.setEnabled(not keyboard)

    def _toggle_settings_panel(self, visible):
        if visible:
            self._stop_keyboard()
        self.settings_panel.setVisible(visible)

    def _camera_status_changed(self, text):
        self.camera_status.setText(text if len(text) <= 32 else text[:29]+"…")
        self.camera_status.setToolTip(text)

    def _refresh_cameras(self):
        selected=self.camera_device.currentData() or self.settings.camera_device
        self.camera_device.clear()
        for device_id, name in self.camera_view.devices():
            self.camera_device.addItem(name,device_id)
        index=self.camera_device.findData(selected)
        if index >= 0:
            self.camera_device.setCurrentIndex(index)

    def _update_camera_fields(self, *_):
        usb=self.camera_mode.currentData() == "usb"
        self.camera_form.setRowVisible(self.camera_device,usb)
        self.camera_form.setRowVisible(self.camera_url,not usb)

    def _start_camera(self):
        mode=self.camera_mode.currentData()
        url=self.camera_url.text()
        if self.camera_view.start(mode,device_id=self.camera_device.currentData() or "",url=url):
            self.settings.camera_mode=mode
            self.settings.camera_device=self.camera_device.currentData() or ""
            self.settings.camera_url=stored_camera_url(url) if mode != "usb" else self.settings.camera_url
            try:
                save_settings(self.settings)
            except OSError:
                self.camera_status.setText("Camera started; preferences could not be saved")

    def _set_map_online(self, enabled):
        self.rover_map.set_online(enabled)
        self.settings.map_online=enabled
        try:
            save_settings(self.settings)
        except OSError:
            self.message.setText("Map preference could not be saved")

    def _stop_keyboard(self):
        self.keyboard.set_active(False)
        if self.settings.input_source == "keyboard" and self.mav.snapshot().control_enabled:
            self.mav.disable_control()
            self.message.setText("Keyboard focus lost — PC Control stopped. Release keys and re-enable manually.")

    def _sample_keyboard(self):
        active = (self.settings.input_source == "keyboard"
                  and self.input_source.currentData() == "keyboard"
                  and QApplication.activeWindow() == self
                  and QApplication.activeModalWidget() is None
                  and QApplication.focusWidget() == self.keyboard_pad)
        if not active:
            self._stop_keyboard()
        else:
            self.keyboard.set_active(True)
            self.keyboard.sample()

    def eventFilter(self, watched, event):
        kind = event.type()
        if ((watched == self and kind == QEvent.Type.WindowDeactivate)
                or (watched == self.keyboard_pad and kind == QEvent.Type.FocusOut)):
            self._stop_keyboard()
        key_events = (QEvent.Type.KeyPress, QEvent.Type.KeyRelease, QEvent.Type.ShortcutOverride)
        if (kind in key_events and watched == self.keyboard_pad
                and self.settings.input_source == "keyboard"):
            names = {Qt.Key.Key_W: "w", Qt.Key.Key_A: "a", Qt.Key.Key_S: "s", Qt.Key.Key_D: "d",
                     Qt.Key.Key_Up: "up", Qt.Key.Key_Left: "left", Qt.Key.Key_Down: "down",
                     Qt.Key.Key_Right: "right", Qt.Key.Key_Space: "space"}
            name = names.get(event.key())
            if name is not None:
                if kind == QEvent.Type.ShortcutOverride:
                    event.accept()
                elif kind == QEvent.Type.KeyRelease:
                    self.keyboard.key(name, False, auto_repeat=event.isAutoRepeat())
                elif event.modifiers() & (Qt.KeyboardModifier.ControlModifier
                        | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier):
                    self._stop_keyboard()
                else:
                    self._sample_keyboard()
                    self.keyboard.key(name, True, auto_repeat=event.isAutoRepeat())
                return True
        return super().eventFilter(watched, event)

    def _mark_dirty(self, network: bool):
        if self._restart_pending:
            self._restart_pending = False
            self._restart_generation += 1
            self.reconnect_btn.setEnabled(True)
            self.message.setText("Connection cancelled because settings changed. Apply & Connect again.")
        if self.mav.snapshot().control_enabled:
            self.mav.disable_control()
            self.message.setText("PC control disabled because configuration was edited. Apply settings and re-enable manually.")
        self._settings_dirty = True
        self._network_dirty = self._network_dirty or network
        self.settings_state.setText("Pending network restart" if self._network_dirty else "Pending settings — click Apply Settings")

    def _apply_settings_to_widgets(self):
        s = self.settings
        self.camera_mode.setCurrentIndex(max(0,self.camera_mode.findData(s.camera_mode)))
        self.camera_url.setText(s.camera_url)
        self._update_camera_fields()
        self._refresh_cameras()
        self.map_online.setChecked(s.map_online)
        self.rover_map.set_online(s.map_online)
        self.input_source.setCurrentIndex(max(0, self.input_source.findData(s.input_source)))
        self.link_mode.setCurrentIndex(max(0, self.link_mode.findData(s.link_mode)))
        self.lora_port.setCurrentText(s.lora_port)
        self.elrs_port.setCurrentText(s.elrs_port)
        self._update_link_fields()
        self.bind_host.setText(s.bind_host)
        self.listen_port.setValue(s.listen_port)
        self.target_host.setText(s.target_host)
        self.target_port.setValue(s.target_port)
        self.pedal_mode.setCurrentIndex(max(0, self.pedal_mode.findData(s.pedal_mode)))
        self.steer_axis.setValue(s.steer_axis)
        self.throttle_axis.setValue(s.throttle_axis)
        self.brake_axis.setValue(s.brake_axis)
        self.invert_steer.setChecked(s.invert_steer)
        self.invert_throttle.setChecked(s.invert_throttle)
        self.invert_brake.setChecked(s.invert_brake)
        self.deadzone.setValue(round(s.deadzone*100))
        self.expo.setValue(round(s.expo*100))
        self.steering_sensitivity.setValue(round(s.steering_sensitivity * 100))
        self.throttle_sensitivity.setValue(round(s.throttle_sensitivity * 100))
        self.throttle_limit.setValue(round(s.throttle_limit * 100))
        self.steer_channel.setValue(s.steering_channel)
        self.throttle_channel.setValue(s.throttle_channel)
        self._settings_dirty = False
        self._network_dirty = False

    def _settings_from_widgets(self) -> AppSettings:
        return AppSettings(
            input_source=self.input_source.currentData(),
            link_mode=self.link_mode.currentData(),
            lora_port=self.lora_port.currentText().strip(),
            elrs_port=self.elrs_port.currentText().strip(),
            bind_host=self.bind_host.text().strip() or "0.0.0.0",
            listen_port=self.listen_port.value(),
            target_host=self.target_host.text().strip(),
            target_port=self.target_port.value(),
            wheel_guid=self.settings.wheel_guid,
            steer_axis=self.steer_axis.value(),
            throttle_axis=self.throttle_axis.value(),
            brake_axis=self.brake_axis.value(),
            pedal_mode=self.pedal_mode.currentData(),
            invert_steer=self.invert_steer.isChecked(),
            invert_throttle=self.invert_throttle.isChecked(),
            invert_brake=self.invert_brake.isChecked(),
            deadzone=self.deadzone.value()/100,
            expo=self.expo.value()/100,
            steering_sensitivity=self.steering_sensitivity.value() / 100,
            throttle_sensitivity=self.throttle_sensitivity.value() / 100,
            throttle_limit=self.throttle_limit.value() / 100,
            steering_channel=self.steer_channel.value(),
            throttle_channel=self.throttle_channel.value(),
            heartbeat_timeout=self.settings.heartbeat_timeout,
            controller_timeout=self.settings.controller_timeout,
            camera_mode=self.settings.camera_mode,
            camera_device=self.settings.camera_device,
            camera_url=self.settings.camera_url,
            map_online=self.settings.map_online,
        ).validate()

    def _persist_and_configure(self):
        try:
            candidate = self._settings_from_widgets()
            save_settings(candidate)
        except (OSError, ValueError, TypeError) as exc:
            self.message.setText(f"Settings could not be applied: {exc}")
            QApplication.beep()
            return False
        self.settings = candidate
        self.wheel.configure(self.settings)
        self.keyboard.set_active(False)
        self.inputs.configure(self.settings)
        if self.settings.input_source == "keyboard":
            self.keyboard_pad.setFocus()
            self._sample_keyboard()
        active_settings = self.settings
        if self._network_dirty:
            # Save the radio draft without redirecting the live session.
            fields = ("link_mode", "lora_port", "elrs_port", "bind_host", "listen_port", "target_host", "target_port")
            active_settings = replace(self.settings, **{name: getattr(self._connected_settings, name) for name in fields})
        self.mav.configure(active_settings)
        self._settings_dirty = False
        self.settings_state.setText("Pending network restart" if self._network_dirty else "Settings applied")
        return True

    def _apply_settings(self):
        if self.mav.snapshot().control_enabled:
            self.mav.disable_control()
        network_pending = self._network_dirty
        if not self._persist_and_configure():
            return False
        self._network_dirty = network_pending
        if network_pending:
            self.settings_state.setText("Network settings saved — click Apply & Reconnect")
            self.message.setText("Controller/safety settings applied. Radio changes need Apply & Reconnect.")
        else:
            self.message.setText("Settings applied.")
        return True

    def _update_link_fields(self, *_):
        mode = self.link_mode.currentData()
        for widget in (self.bind_host, self.listen_port, self.target_host, self.target_port):
            self.connection_form.setRowVisible(widget, mode == "telerc_udp")
        self.connection_form.setRowVisible(self.lora_port, mode == "lora_usb")
        self.connection_form.setRowVisible(self.elrs_port, mode == "elrs_serial")
        self.refresh_ports_btn.setVisible(mode != "telerc_udp")
        self.lora_setup_btn.setVisible(mode == "lora_usb")
        self.guide.setText("Verify radio-loss stop and transmitter takeover before driving." if mode == "lora_usb" else "ArduRover GCS/telemetry fail-safe remains mandatory for true link-loss protection.")
        self.link_hint.setText({
            "telerc_udp": "Join TeleRC-Rover Wi-Fi. ESP32-S3 and LilyGO use UDP 14550.",
            "lora_usb": "Connect the paired SX1262 BASE using native USB (115200). Use the matching BASE/ROVER firmware; supports ArduRover MANUAL or the legacy DIRECT motor controller.",
            "elrs_serial": "Select the TX module USB port, then Apply & Connect. Wait for a rover heartbeat, release pedals, and enable PC Control. ELRS MAVLink mode · 460800 baud · 5 Hz. Pocket handover requires bench verification.",
        }[mode])

    def _refresh_radio_ports(self):
        try:
            refresh_ports(self.lora_port)
            refresh_ports(self.elrs_port)
            self.message.setText("Ports refreshed. Select the intended module; the active connection is unchanged.")
        except OSError as exc:
            self.message.setText(f"Could not list USB ports: {exc}")

    def _disconnect_link(self):
        self._restart_pending = False
        self._restart_generation += 1
        self.reconnect_btn.setEnabled(True)
        stopped = self.mav.stop()
        self.message.setText("Disconnected. PC Control is OFF." if stopped else "Link did not stop. Close PC TeleRC before reconnecting.")
        return stopped

    def _open_lora_setup(self):
        if self._lora_dialog is None:
            dialog = QDialog(self)
            dialog.setWindowTitle("LilyGO SX1262 · LoRa setup")
            dialog.resize(720, 420)
            dialog.setModal(False)
            layout = QVBoxLayout(dialog)
            dialog.setup = LoRaSetupWidget(self._disconnect_link, dialog)
            dialog.setup.port.setCurrentText(self.lora_port.currentText())
            layout.addWidget(dialog.setup)
            dialog.finished.connect(lambda *_: (dialog.setup.close_usb(), dialog.setup.clear_secret()))
            self._lora_dialog = dialog
        self._lora_dialog.show()
        self._lora_dialog.raise_()

    def _apply_and_reconnect(self):
        self.reconnect_btn.setEnabled(False)
        if self._lora_dialog is not None:
            self._lora_dialog.close()
        # Old settings remain active until neutral/release and port close finish.
        if not self._disconnect_link():
            self.reconnect_btn.setEnabled(True)
            return
        self.reconnect_btn.setEnabled(False)
        network_pending = self._network_dirty
        self._network_dirty = False
        if not self._persist_and_configure():
            self._network_dirty = network_pending
            self.reconnect_btn.setEnabled(True)
            return
        self._connected_settings = replace(self.settings)
        self.settings_state.setText("Connecting selected radio…")
        self._restart_pending = True
        self._restart_settings = replace(self.settings)
        generation = self._restart_generation
        QTimer.singleShot(250, lambda: self._restart_mavlink_after_release(generation))

    def _restart_mavlink_after_release(self, generation=None):
        if not self._restart_pending or (generation is not None and generation != self._restart_generation):
            return
        self._restart_pending = False
        self.mav.configure(self._restart_settings)
        self.mav.start()
        self._network_dirty = False
        self.reconnect_btn.setEnabled(True)
        self.settings_state.setText("Settings applied")
        self.message.setText("Waiting for a fresh heartbeat. Enable PC Control manually when ready.")

    def _select_controller(self):
        if self.mav.snapshot().control_enabled:
            self.mav.disable_control()
            self.message.setText("PC control disabled before changing controller.")
        guid = self.device_combo.currentData()
        if not guid:
            QApplication.beep()
            self.message.setText("No controller is available to select.")
            return
        self.settings.wheel_guid = guid
        save_settings(self.settings)
        self.wheel.select(guid)
        self.message.setText("Controller selection saved.")

    def _calibrate_controller(self):
        if self.input_source.currentData() == "keyboard":
            return
        snapshot = self.wheel.snapshot()
        if not snapshot.connected:
            QApplication.beep()
            self.message.setText("Connect and select a wheel/controller before calibration.")
            return

        if self.mav.snapshot().control_enabled:
            self.mav.disable_control()
            self.message.setText("PC control disabled before calibration.")

        dialog = CalibrationDialog(self.wheel, self.pedal_mode.currentData(), self)
        if dialog.exec() != CalibrationDialog.DialogCode.Accepted or dialog.result is None:
            self.message.setText("Calibration cancelled. Existing mapping was kept.")
            return

        result = dialog.result
        self.steer_axis.setValue(result.steer_axis)
        self.invert_steer.setChecked(result.invert_steer)
        self.throttle_axis.setValue(result.throttle_axis)
        self.invert_throttle.setChecked(result.invert_throttle)
        self.brake_axis.setValue(result.brake_axis)
        self.invert_brake.setChecked(result.invert_brake)
        self.pedal_mode.setCurrentIndex(self.pedal_mode.findData(result.pedal_mode))
        self._apply_settings()
        self.message.setText(
            f"Calibration applied: steer axis {result.steer_axis}, "
            f"throttle axis {result.throttle_axis}, brake axis {result.brake_axis}. "
            "Verify the live Steer/Drive values before enabling PC control."
        )

    def _open_diagnostics(self):
        if self._diagnostics_window is not None and self._diagnostics_window.isVisible():
            self._diagnostics_window.raise_()
            self._diagnostics_window.activateWindow()
            return

        def state_provider():
            return self.settings, self._settings_dirty, self._network_dirty

        self._diagnostics_window = DiagnosticsDialog(
            settings=self.settings,
            wheel=self.inputs,
            mav=self.mav,
            state_provider=state_provider,
            parent=self,
        )
        self._diagnostics_window.destroyed.connect(lambda *_: setattr(self, "_diagnostics_window", None))
        self._diagnostics_window.show()

    def _toggle_control(self):
        if self.mav.snapshot().control_enabled:
            released = self.mav.disable_control()
            self.message.setText("PC control disabled; neutral/release written to USB. Verify rover handover." if released is True else
                                 "PC control disabled; verify rover failsafe and transmitter handover.")
            return
        if self._settings_dirty or self._network_dirty or self._restart_pending:
            QApplication.beep()
            self.message.setText("Apply pending settings before enabling PC control.")
            return
        ok, message = self.mav.enable_control()
        self.message.setText(message)
        if not ok:
            QApplication.beep()

    def _vehicle_command(self, command, allow_dirty: bool = False):
        if (self._settings_dirty or self._network_dirty or self._restart_pending) and not allow_dirty:
            QApplication.beep()
            self.message.setText("Apply pending settings before ARM.")
            return
        ok, message = command()
        self.message.setText(message)
        if not ok:
            QApplication.beep()

    def _refresh(self):
        wheel = self.inputs.snapshot()
        mav = self.mav.snapshot()
        self.rover_map.set_snapshot(mav)
        gps=f"GPS {mav.satellites or '—'}" if position_fresh(mav) else "GPS —"
        speed=f"{mav.speed:.1f} m/s" if position_fresh(mav) and mav.speed is not None else "—"
        battery=f"{mav.voltage:.1f} V" if (mav.state == LinkState.CONNECTED and mav.voltage is not None
            and mav.battery_timestamp is not None and time.monotonic()-mav.battery_timestamp <= 5) else "—"
        self.telemetry_label.setText(f"{gps}   Speed {speed}   Battery {battery}")

        devices = self.wheel.devices()
        displayed_guids = [self.device_combo.itemData(i) for i in range(self.device_combo.count())]
        detected_guids = [device.guid for device in devices]
        if displayed_guids != detected_guids:
            self.device_combo.blockSignals(True)
            self.device_combo.clear()
            for device in devices:
                self.device_combo.addItem(f"{device.name} ({device.axes} axes)", device.guid)
            index = self.device_combo.findData(self.settings.wheel_guid)
            if index >= 0:
                self.device_combo.setCurrentIndex(index)
            self.device_combo.blockSignals(False)

        self.controller_label.setText(
            f"Controller: {wheel.name}" if wheel.connected else (wheel.error or "Controller: not detected")
        )
        self.axis_label.setText(f"Steer {wheel.steering:+.2f} • Drive {wheel.throttle:+.2f}")
        axes = ", ".join(f"{i}:{value:+.2f}" for i, value in enumerate(wheel.axes[:10]))
        self.raw_axes.setText("Axes: " + (axes or "—"))

        if not mav.running:
            self.link_label.setText("Disconnected — click Apply & Connect")
        elif mav.state == LinkState.CONNECTED:
            self.link_label.setText(f"Connected • heartbeat {(mav.heartbeat_age or 0):.1f}s ago")
        elif mav.state == LinkState.STALE:
            self.link_label.setText("Heartbeat stale — control inhibited")
        else:
            if self._connected_settings.link_mode == "elrs_serial":
                age = time.monotonic() - (mav.opened_at or time.monotonic())
                self.link_label.setText("USB open — waiting for rover heartbeat…" if age < 10 else
                                        "USB open, no rover — check TX/RX MAVLink mode, power and UART")
            else:
                self.link_label.setText("Waiting for MAVLink heartbeat…")

        self.vehicle_label.setText(f"{'ARMED' if mav.armed else 'DISARMED'} • {mav.mode or 'mode —'}")
        self.vehicle_label.setStyleSheet("color:#fbbf24;font-weight:700;" if mav.armed else "color:#91a0b2;")
        self.traffic_label.setText(f"RX {mav.rx_messages} • TX {mav.tx_messages}")
        self.output_label.setText(
            f"CH{self.settings.steering_channel} {mav.steer_pwm} • "
            f"CH{self.settings.throttle_channel} {mav.throttle_pwm}"
        )

        if mav.control_enabled:
            self.safety_label.setText("PC CONTROL ACTIVE")
            self.safety_label.setStyleSheet("color:#64d98b;font-weight:700;")
            self.control_btn.setText("Disable PC Control")
        elif mav.failsafe_latched:
            self.safety_label.setText("Stopped • re-enable manually")
            self.safety_label.setStyleSheet("color:#ff6b6b;font-weight:700;")
            self.control_btn.setText("Re-enable PC Control")
        else:
            self.safety_label.setText("Control disabled")
            self.safety_label.setStyleSheet("color:#91a0b2;")
            self.control_btn.setText("Enable PC Control")

        if mav.error:
            self.message.setText(mav.error)

        link_ok = mav.running and mav.state == LinkState.CONNECTED
        wheel_ok = wheel.connected
        self.global_status.setText("Control stopped" if mav.failsafe_latched else
                                  "Ready" if link_ok and wheel_ok and not self._settings_dirty and not self._network_dirty else "Setup required")

        self.select_btn.setEnabled(self.device_combo.count() > 0)
        self.calibrate_btn.setEnabled(self.input_source.currentData() == "wheel" and self.wheel.snapshot().connected)
        neutral_ok = wheel.frame is not None and wheel.frame.neutral
        if self.settings.input_source == "keyboard" and wheel.frame is not None:
            neutral_ok = neutral_ok and wheel.frame.acquisition_ready
        if self.settings.link_mode in ("telerc_udp", "lora_usb"):
            neutral_ok = neutral_ok and abs(wheel.frame.steering) <= .05
        self.reconnect_btn.setText("Apply & Reconnect" if mav.running else "Apply & Connect")
        self.arm_btn.setEnabled(link_ok and wheel_ok and neutral_ok and not mav.armed and not self._settings_dirty and not self._network_dirty)
        self.disarm_btn.setEnabled(link_ok and mav.armed)
        self.control_btn.setEnabled(
            mav.control_enabled or (link_ok and wheel_ok and neutral_ok and not self._settings_dirty and not self._network_dirty)
        )

    def closeEvent(self, event):
        self.camera_view.shutdown()
        self.rover_map.shutdown()
        QApplication.instance().removeEventFilter(self)
        self.keyboard_timer.stop()
        self.keyboard.set_active(False)
        self.timer.stop()
        self._restart_pending = False
        self._restart_generation += 1
        if self._lora_dialog is not None:
            self._lora_dialog.close()
        self.mav.disable_control()
        self.mav.stop()
        self.wheel.stop()
        if not self._settings_dirty:
            save_settings(self.settings)
        event.accept()



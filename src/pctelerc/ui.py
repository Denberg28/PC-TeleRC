from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
)

from . import __version__
from .calibration_dialog import CalibrationDialog
from .config import AppSettings, load_settings, save_settings
from .controller import WheelService
from .core import LinkState
from .diagnostics_dialog import DiagnosticsDialog
from .mavlink import MavlinkService

STYLE = """
QWidget { background:#11161d; color:#e7edf5; font-family:'Segoe UI'; font-size:10pt; }
QFrame#Card { background:#18202a; border:1px solid #2a3645; border-radius:10px; }
QLabel#Title { font-size:18pt; font-weight:700; }
QLabel#Muted { color:#91a0b2; }
QLabel#Good { color:#64d98b; font-weight:700; }
QLabel#Warn { color:#ffc857; font-weight:700; }
QLabel#Bad { color:#ff6b6b; font-weight:700; }
QPushButton { background:#253244; border:1px solid #3b4d65; padding:7px 12px; border-radius:7px; }
QPushButton:hover { border-color:#5c7392; }
QPushButton:disabled { color:#677587; background:#1a222d; border-color:#273342; }
QPushButton#Primary { background:#1677ff; font-weight:700; }
QPushButton#Danger { background:#7a2831; }
QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox { background:#0f141a; border:1px solid #344458; border-radius:6px; padding:5px; }
"""

NETWORK_FIELDS = ("bind_host", "listen_port", "target_host", "target_port")


def card(title: str):
    frame = QFrame()
    frame.setObjectName("Card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 14, 14, 14)
    heading = QLabel(title)
    heading.setStyleSheet("font-weight:700;font-size:12pt;")
    layout.addWidget(heading)
    return frame, layout


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"PC TeleRC {__version__}")
        self.resize(1180, 720)
        self.settings = load_settings()
        self._settings_dirty = False
        self._network_dirty = False

        self.wheel = WheelService()
        self.mav = MavlinkService()

        self._build()
        self._apply_settings_to_widgets()
        self._wire_buttons_and_fields()

        self.wheel.configure(self.settings)
        self.wheel.start()
        self.mav.configure(self.settings)
        self.mav.start()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(50)

    def _build(self):
        root = QWidget()
        main = QVBoxLayout(root)
        main.setContentsMargins(18, 16, 18, 16)
        main.setSpacing(12)

        top = QHBoxLayout()
        title = QLabel("PC TeleRC")
        title.setObjectName("Title")
        top.addWidget(title)
        subtitle = QLabel("Windows MAVLink rover bridge + wheel controller")
        subtitle.setObjectName("Muted")
        top.addWidget(subtitle)
        top.addStretch()
        self.global_status = QLabel("Starting…")
        top.addWidget(self.global_status)
        main.addLayout(top)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        main.addLayout(grid, 1)

        connection_card, connection = card("1. MAVLink / ESP32-S3")
        form = QFormLayout()
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
        connection.addLayout(form)

        self.reconnect_btn = QPushButton("Apply & Reconnect")
        self.reconnect_btn.setObjectName("Primary")
        self.reconnect_btn.setToolTip("Save all settings, restart the MAVLink socket, and require manual PC-control re-enable.")
        connection.addWidget(self.reconnect_btn)

        self.link_label = QLabel("No heartbeat")
        self.vehicle_label = QLabel("Vehicle: —")
        self.traffic_label = QLabel("RX 0 • TX 0")
        connection.addWidget(self.link_label)
        connection.addWidget(self.vehicle_label)
        connection.addWidget(self.traffic_label)
        connection.addStretch()
        grid.addWidget(connection_card, 0, 0)

        wheel_card, wheel_layout = card("2. PXN / Game Controller")
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

        self.deadzone = QDoubleSpinBox()
        self.deadzone.setRange(0, .30)
        self.deadzone.setSingleStep(.01)
        self.expo = QDoubleSpinBox()
        self.expo.setRange(0, 1)
        self.expo.setSingleStep(.05)
        wheel_form.addRow("Deadzone", self.deadzone)
        wheel_form.addRow("Steering expo", self.expo)
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
        self.throttle_limit = QSpinBox()
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
        self.arm_btn.setToolTip("Send MAV_CMD_COMPONENT_ARM_DISARM only when link and neutral-controller checks pass.")
        self.disarm_btn = QPushButton("DISARM")
        self.disarm_btn.setObjectName("Danger")
        self.disarm_btn.setToolTip("Send an explicit disarm command to the linked vehicle.")
        arm_row.addWidget(self.arm_btn)
        arm_row.addWidget(self.disarm_btn)
        safety.addLayout(arm_row)

        self.control_btn = QPushButton("Enable PC Control")
        self.control_btn.setObjectName("Primary")
        self.control_btn.setToolTip("Enable RC override only with healthy MAVLink, a fresh wheel, and neutral throttle.")
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
        guide.setWordWrap(True)
        guide.setObjectName("Muted")
        status.addWidget(self.settings_state)
        status.addWidget(self.message)
        status.addWidget(guide)
        grid.addWidget(status_card, 1, 0, 1, 3)

        self.setCentralWidget(root)

    def _wire_buttons_and_fields(self):
        # Button audit: every operator action has exactly one explicit handler.
        self.reconnect_btn.clicked.connect(self._apply_and_reconnect)
        self.select_btn.clicked.connect(self._select_controller)
        self.calibrate_btn.clicked.connect(self._calibrate_controller)
        self.apply_btn.clicked.connect(self._apply_settings)
        self.control_btn.clicked.connect(self._toggle_control)
        self.diagnostics_btn.clicked.connect(self._open_diagnostics)
        self.arm_btn.clicked.connect(lambda: self._vehicle_command(self.mav.arm))
        self.disarm_btn.clicked.connect(lambda: self._vehicle_command(self.mav.disarm))

        non_network = (
            self.pedal_mode, self.steer_axis, self.throttle_axis, self.brake_axis,
            self.invert_steer, self.invert_throttle, self.invert_brake,
            self.deadzone, self.expo, self.throttle_limit,
            self.steer_channel, self.throttle_channel,
        )
        for widget in non_network:
            self._connect_change(widget, network=False)
        for widget in (self.bind_host, self.listen_port, self.target_host, self.target_port):
            self._connect_change(widget, network=True)

    def _connect_change(self, widget, *, network: bool):
        for signal_name in ("textChanged", "currentIndexChanged", "toggled", "valueChanged"):
            signal = getattr(widget, signal_name, None)
            if signal is not None:
                signal.connect(lambda *_args, is_network=network: self._mark_dirty(is_network))
                return

    def _mark_dirty(self, network: bool):
        if self.mav.snapshot().control_enabled:
            self.mav.disable_control()
            self.message.setText("PC control disabled because configuration was edited. Apply settings and re-enable manually.")
        self._settings_dirty = True
        self._network_dirty = self._network_dirty or network
        self.settings_state.setText("Pending network restart" if self._network_dirty else "Pending settings — click Apply Settings")

    def _apply_settings_to_widgets(self):
        s = self.settings
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
        self.deadzone.setValue(s.deadzone)
        self.expo.setValue(s.expo)
        self.throttle_limit.setValue(round(s.throttle_limit * 100))
        self.steer_channel.setValue(s.steering_channel)
        self.throttle_channel.setValue(s.throttle_channel)
        self._settings_dirty = False
        self._network_dirty = False

    def _settings_from_widgets(self) -> AppSettings:
        return AppSettings(
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
            deadzone=self.deadzone.value(),
            expo=self.expo.value(),
            throttle_limit=self.throttle_limit.value() / 100,
            steering_channel=self.steer_channel.value(),
            throttle_channel=self.throttle_channel.value(),
            heartbeat_timeout=self.settings.heartbeat_timeout,
            controller_timeout=self.settings.controller_timeout,
        ).validate()

    def _persist_and_configure(self):
        self.settings = self._settings_from_widgets()
        save_settings(self.settings)
        self.wheel.configure(self.settings)
        self.mav.configure(self.settings)
        self._settings_dirty = False
        self.settings_state.setText("Pending network restart" if self._network_dirty else "Settings applied")

    def _apply_settings(self):
        if self.mav.snapshot().control_enabled:
            self.mav.disable_control()
        network_pending = self._network_dirty
        self._persist_and_configure()
        self._network_dirty = network_pending
        if network_pending:
            self.settings_state.setText("Network settings saved — click Apply & Reconnect")
            self.message.setText("Controller/safety settings applied. MAVLink address/port changes need Apply & Reconnect.")
        else:
            self.message.setText("Settings applied.")

    def _apply_and_reconnect(self):
        self.mav.disable_control()
        self._persist_and_configure()
        self.mav.stop()
        self.mav.configure(self.settings)
        self.mav.start()
        self._network_dirty = False
        self.settings_state.setText("Settings applied • MAVLink restarted")
        self.message.setText("MAVLink restarted. PC control remains OFF until manually enabled.")

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
        dialog = DiagnosticsDialog(
            settings=self.settings,
            wheel=self.wheel,
            mav=self.mav,
            settings_dirty=self._settings_dirty,
            network_dirty=self._network_dirty,
            parent=self,
        )
        dialog.exec()

    def _toggle_control(self):
        if self._settings_dirty:
            QApplication.beep()
            self.message.setText("Apply pending settings before enabling PC control.")
            return
        if self.mav.snapshot().control_enabled:
            self.mav.disable_control()
            self.message.setText("PC control disabled; neutral sent and overrides released.")
            return
        ok, message = self.mav.enable_control()
        self.message.setText(message)
        if not ok:
            QApplication.beep()

    def _vehicle_command(self, command):
        if self._settings_dirty:
            QApplication.beep()
            self.message.setText("Apply pending settings before ARM/DISARM.")
            return
        ok, message = command()
        self.message.setText(message)
        if not ok:
            QApplication.beep()

    def _refresh(self):
        wheel = self.wheel.snapshot()
        mav = self.mav.snapshot()
        self.mav.set_control_frame(wheel.frame, len(wheel.axes) if wheel.connected else None)

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

        if mav.state == LinkState.CONNECTED:
            self.link_label.setText(f"Connected • heartbeat {(mav.heartbeat_age or 0):.1f}s ago")
        elif mav.state == LinkState.STALE:
            self.link_label.setText("Heartbeat stale — control inhibited")
        else:
            self.link_label.setText("Waiting for MAVLink heartbeat…")

        self.vehicle_label.setText(
            f"Vehicle: sys {mav.vehicle_system or '—'} / comp {mav.vehicle_component or '—'} • "
            f"{mav.mode or 'mode —'} • {'ARMED' if mav.armed else 'disarmed'}"
        )
        self.traffic_label.setText(f"RX {mav.rx_messages} • TX {mav.tx_messages}")
        self.output_label.setText(
            f"CH{self.settings.steering_channel} {mav.steer_pwm} • "
            f"CH{self.settings.throttle_channel} {mav.throttle_pwm}"
        )

        if mav.control_enabled:
            self.safety_label.setText("PC CONTROL ACTIVE")
            self.safety_label.setObjectName("Good")
            self.control_btn.setText("Disable PC Control")
        elif mav.failsafe_latched:
            self.safety_label.setText("FAIL-SAFE LATCHED — manual re-enable required")
            self.safety_label.setObjectName("Bad")
            self.control_btn.setText("Re-enable PC Control")
        else:
            self.safety_label.setText("Control disabled")
            self.safety_label.setObjectName("Muted")
            self.control_btn.setText("Enable PC Control")

        if mav.error:
            self.message.setText(mav.error)

        link_ok = mav.state == LinkState.CONNECTED
        wheel_ok = wheel.connected
        self.global_status.setText("Ready" if link_ok and wheel_ok and not self._settings_dirty else "Setup required")

        self.select_btn.setEnabled(self.device_combo.count() > 0)
        self.calibrate_btn.setEnabled(wheel_ok)
        self.arm_btn.setEnabled(link_ok and not mav.armed and not self._settings_dirty)
        self.disarm_btn.setEnabled(link_ok and mav.armed and not self._settings_dirty)
        self.control_btn.setEnabled(link_ok and wheel_ok and not self._settings_dirty)

    def closeEvent(self, event):
        self.timer.stop()
        self.mav.disable_control()
        self.mav.stop()
        self.wheel.stop()
        if not self._settings_dirty:
            save_settings(self.settings)
        event.accept()

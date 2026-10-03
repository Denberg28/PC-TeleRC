from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton,
    QSlider, QSpinBox, QSizePolicy, QVBoxLayout, QWidget,
)

from . import __version__
from .calibration_dialog import CalibrationDialog
from .config import AppSettings, load_settings, save_settings
from .controller import WheelService
from .core import LinkState, control_is_fresh
from .field_safety import can_enable_control
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
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"PC TeleRC {__version__}")
        self.resize(1180, 720)
        self.settings = load_settings()
        self._settings_dirty = False
        self._network_dirty = False
        self._diagnostics_window = None
        self._active_network_settings = replace(self.settings)
        self._wheel_generation = None
        self._closing = False
        self._last_command_status = ""

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
        self.main_grid = grid
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        for column in range(3):
            grid.setColumnStretch(column, 1)
            grid.setColumnMinimumWidth(column, 330)
        main.addLayout(grid, 1)

        connection_card, connection = card("1. Rover connection")
        form = QFormLayout()
        self.link_mode = QComboBox()
        self.link_mode.addItem("TeleRC ESP32 · Wi-Fi", "telerc_udp")
        self.link_mode.addItem("ELRS external TX · USB MAVLink (experimental)", "elrs_serial")
        self.serial_port = QLineEdit()
        self.serial_port.setPlaceholderText("ELRS module COM port, e.g. COM5")
        self.serial_port.setToolTip("Requires USB MAVLink firmware and compatible receiver; fixed 460800 baud, DTR/RTS low. Not raw CRSF module-bay input.")
        form.addRow("Connection", self.link_mode)
        form.addRow("ELRS COM port", self.serial_port)
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
        self.link_mode.currentIndexChanged.connect(self._update_link_fields)
        self.connection_hint = QLabel("ELRS USB requires a MAVLink-capable TX/receiver. HGLRC T ONE USB compatibility is unverified; a module-bay CRSF adapter is not supported.")
        self.connection_hint.setWordWrap(True)
        connection.addWidget(self.connection_hint)

        self.reconnect_btn = QPushButton("Apply & Reconnect")
        self.reconnect_btn.setObjectName("Primary")
        self.reconnect_btn.setToolTip("Apply network settings. The UDP listener restarts only if the listen address or port changed.")
        connection.addWidget(self.reconnect_btn)
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setToolTip("Disable PC control, send neutral/release, stop heartbeats, and close the UDP socket.")
        connection.addWidget(self.disconnect_btn)

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
        self.steering_sensitivity = QSlider(Qt.Orientation.Horizontal)
        self.steering_sensitivity.setRange(25, 100)
        self.steering_sensitivity.setSingleStep(1)
        self.steering_sensitivity.setPageStep(5)
        self.steering_sensitivity.setAccessibleName("Steering sensitivity percent")
        self.steering_sensitivity.setToolTip("Scale steering authority. 100% = full steering command; lower values reduce steering gain.")
        sensitivity_widget = QWidget()
        sensitivity_layout = QVBoxLayout(sensitivity_widget)
        sensitivity_layout.setContentsMargins(0, 0, 0, 0)
        sensitivity_layout.setSpacing(4)
        sensitivity_layout.addWidget(self.steering_sensitivity)
        self.sensitivity_label = QLabel()
        self.sensitivity_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sensitivity_layout.addWidget(self.sensitivity_label)
        self.steering_sensitivity.valueChanged.connect(
            lambda value: self.sensitivity_label.setText(f"Steering sensitivity: {value}%")
        )
        wheel_form.addRow("Deadzone", self.deadzone)
        wheel_form.addRow("Steering expo", self.expo)
        wheel_layout.addLayout(wheel_form)
        wheel_layout.addWidget(sensitivity_widget)
        self.drive_sensitivity = QSlider(Qt.Orientation.Horizontal)
        self.drive_sensitivity.setRange(25, 100)
        self.drive_sensitivity.setSingleStep(1)
        self.drive_sensitivity.setPageStep(5)
        self.drive_sensitivity.setAccessibleName("Drive sensitivity percent")
        self.drive_sensitivity.setToolTip("Scale forward/reverse drive input independently of steering. The throttle limit still applies.")
        drive_widget = QWidget()
        drive_layout = QVBoxLayout(drive_widget)
        drive_layout.setContentsMargins(0, 0, 0, 0)
        drive_layout.setSpacing(4)
        drive_layout.addWidget(self.drive_sensitivity)
        self.drive_sensitivity_label = QLabel()
        self.drive_sensitivity_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drive_layout.addWidget(self.drive_sensitivity_label)
        self.drive_sensitivity.valueChanged.connect(
            lambda value: self.drive_sensitivity_label.setText(f"Drive sensitivity: {value}%")
        )
        wheel_layout.addWidget(drive_widget)

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
        self.steer_channel.setToolTip("TeleRC bridge supports channels 1–4. Channels 5–8 block ARM/PC Control.")
        self.throttle_channel.setToolTip("TeleRC bridge supports channels 1–4. Channels 5–8 block ARM/PC Control.")
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
        self.message = QLabel("Connect the rover network and verify wheel input before enabling PC control.")
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
        self.disconnect_btn.clicked.connect(self._disconnect)
        self.select_btn.clicked.connect(self._select_controller)
        self.calibrate_btn.clicked.connect(self._calibrate_controller)
        self.apply_btn.clicked.connect(self._apply_settings)
        self.control_btn.clicked.connect(self._toggle_control)
        self.diagnostics_btn.clicked.connect(self._open_diagnostics)
        self.arm_btn.clicked.connect(lambda: self._vehicle_command(self.mav.arm))
        self.disarm_btn.clicked.connect(lambda: self._vehicle_command(self.mav.disarm, allow_dirty=True))

        non_network = (
            self.pedal_mode, self.steer_axis, self.throttle_axis, self.brake_axis,
            self.invert_steer, self.invert_throttle, self.invert_brake,
            self.deadzone, self.expo, self.steering_sensitivity, self.drive_sensitivity, self.throttle_limit,
            self.steer_channel, self.throttle_channel,
        )
        for widget in non_network:
            self._connect_change(widget, network=False)
        for widget in (self.bind_host, self.listen_port, self.target_host, self.target_port, self.link_mode, self.serial_port):
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
        self.link_mode.setCurrentIndex(self.link_mode.findData(s.link_mode))
        self.serial_port.setText(s.serial_port)
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
        self.deadzone.setValue(s.deadzone)
        self.expo.setValue(s.expo)
        self.steering_sensitivity.setValue(round(s.steering_sensitivity * 100))
        self.drive_sensitivity.setValue(round(s.drive_sensitivity * 100))
        self.throttle_limit.setValue(round(s.throttle_limit * 100))
        self.steer_channel.setValue(s.steering_channel)
        self.throttle_channel.setValue(s.throttle_channel)
        self._settings_dirty = False
        self._network_dirty = False

    def _update_link_fields(self):
        serial_mode = self.link_mode.currentData() == "elrs_serial"
        self.serial_port.setEnabled(serial_mode)
        for widget in (self.bind_host, self.listen_port, self.target_host, self.target_port):
            widget.setEnabled(not serial_mode)

    def _settings_from_widgets(self) -> AppSettings:
        return AppSettings(
            link_mode=self.link_mode.currentData(),
            serial_port=self.serial_port.text().strip(),
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
            steering_sensitivity=self.steering_sensitivity.value() / 100,
            drive_sensitivity=self.drive_sensitivity.value() / 100,
            throttle_limit=self.throttle_limit.value() / 100,
            steering_channel=self.steer_channel.value(),
            throttle_channel=self.throttle_channel.value(),
            heartbeat_timeout=self.settings.heartbeat_timeout,
            controller_timeout=self.settings.controller_timeout,
        ).validate()

    def _persist_and_configure(self, *, apply_network=False):
        try:
            candidate = self._settings_from_widgets()
            save_settings(candidate)
        except (OSError, ValueError, TypeError) as exc:
            QApplication.beep()
            self.message.setText(f"Settings could not be applied: {exc}")
            return False
        self.settings = candidate
        self.wheel.configure(candidate)
        if apply_network:
            live = candidate
            self._active_network_settings = replace(candidate)
        else:
            network = self._active_network_settings
            live = replace(candidate, bind_host=network.bind_host, listen_port=network.listen_port,
                           target_host=network.target_host, target_port=network.target_port,
                           link_mode=network.link_mode, serial_port=network.serial_port)
        self.mav.configure(live)
        self._settings_dirty = False
        self.settings_state.setText("Pending network restart" if self._network_dirty else "Settings applied")
        return True

    def _apply_settings(self):
        self.mav.disable_control()
        if not self._persist_and_configure():
            return False
        if self._network_dirty:
            self.settings_state.setText("Network settings saved — click Apply & Reconnect")
            self.message.setText("Controller settings applied. Click Apply & Reconnect to activate network changes.")
        else:
            self.message.setText("Settings applied. PC control remains OFF until manually enabled.")
        return True

    def _apply_and_reconnect(self):
        # Disconnect using the OLD routing/mapping before changing either one.
        if not self.mav.stop():
            QApplication.beep()
            self.message.setText("MAVLink worker did not stop cleanly. Close PC TeleRC before reconnecting.")
            return
        if not self._persist_and_configure(apply_network=True):
            return
        if self._closing:
            return
        self.mav.start()
        self._network_dirty = False
        self.settings_state.setText("Settings applied • waiting for heartbeat")
        self.message.setText("MAVLink link started. Wait for a new heartbeat, then manually enable PC control.")

    def _disconnect(self):
        if not self.mav.stop():
            self.message.setText("Disconnect did not complete. Close PC TeleRC before reconnecting.")
            return
        self.message.setText("Disconnected. PC control is OFF; GCS heartbeats stopped and link closed.")

    def _select_controller(self):
        if self.mav.snapshot().control_enabled:
            self.mav.disable_control()
            self.message.setText("PC control disabled before changing controller.")
        guid = self.device_combo.currentData()
        if not guid:
            QApplication.beep()
            self.message.setText("No controller is available to select.")
            return
        candidate = replace(self.settings, wheel_guid=guid)
        try:
            save_settings(candidate)
        except (OSError, ValueError, TypeError) as exc:
            self.message.setText(f"Controller selection could not be saved: {exc}")
            return
        self.settings = candidate
        self.wheel.select(guid)
        self.mav.set_control_frame(None)
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
        if not self._apply_settings():
            return
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
            wheel=self.wheel,
            mav=self.mav,
            state_provider=state_provider,
            parent=self,
        )
        self._diagnostics_window.destroyed.connect(lambda *_: setattr(self, "_diagnostics_window", None))
        self._diagnostics_window.show()

    def _toggle_control(self):
        if self.mav.snapshot().control_enabled:
            released = self.mav.disable_control()
            self.message.setText("PC control disabled; neutral/release sent." if released else
                                 "PC control disabled; neutral/release transmission failed. Verify vehicle failsafe.")
            return
        if self._settings_dirty or self._network_dirty:
            QApplication.beep()
            self.message.setText("Apply pending settings before enabling PC control.")
            return
        ok, message = self.mav.enable_control()
        self.message.setText(message)
        if not ok:
            QApplication.beep()

    def _vehicle_command(self, command, allow_dirty: bool = False):
        if (self._settings_dirty or self._network_dirty) and not allow_dirty:
            QApplication.beep()
            self.message.setText("Apply pending settings before ARM.")
            return
        ok, message = command()
        self.message.setText(message)
        if not ok:
            QApplication.beep()

    def _refresh(self):
        wheel = self.wheel.snapshot()
        if self._wheel_generation is not None and wheel.generation != self._wheel_generation:
            if self.mav.snapshot().control_enabled:
                self.mav.disable_control()
                self.message.setText("Controller connection changed. Verify neutral input and manually re-enable control.")
        self._wheel_generation = wheel.generation
        mav = self.mav.snapshot()
        self.mav.set_control_frame(wheel.frame if wheel.connected else None, len(wheel.axes) if wheel.connected else None)

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
            self.link_label.setText("Disconnected — link stopped")
        elif mav.state == LinkState.CONNECTED:
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
            self.safety_label.setStyleSheet("color:#64d98b;font-weight:700;")
            self.control_btn.setText("Disable PC Control")
        elif mav.failsafe_latched:
            self.safety_label.setText("FAIL-SAFE LATCHED — manual re-enable required")
            self.safety_label.setStyleSheet("color:#ff6b6b;font-weight:700;")
            self.control_btn.setText("Re-enable PC Control")
        else:
            self.safety_label.setText("Control disabled")
            self.safety_label.setStyleSheet("color:#91a0b2;")
            self.control_btn.setText("Enable PC Control")

        if mav.command_status and mav.command_status != self._last_command_status:
            self.message.setText(mav.command_status)
        self._last_command_status = mav.command_status
        if mav.error:
            self.message.setText(mav.error)

        link_ok = mav.running and mav.state == LinkState.CONNECTED
        wheel_ok = wheel.connected and control_is_fresh(wheel.frame, stale_after=self.settings.controller_timeout)
        pending = self._settings_dirty or self._network_dirty
        decision = can_enable_control(settings=self.settings, link_state=mav.state if link_ok else LinkState.DISCONNECTED,
                                      frame=wheel.frame, axis_count=len(wheel.axes) if wheel.connected else 0)
        ready = decision.allowed and not pending
        self.disconnect_btn.setEnabled(mav.running)
        self.reconnect_btn.setText("Apply & Reconnect" if mav.running else "Apply & Connect")
        self.global_status.setText("Ready" if ready else "Setup required")

        self.select_btn.setEnabled(self.device_combo.count() > 0)
        self.calibrate_btn.setEnabled(wheel_ok)
        self.arm_btn.setEnabled(ready and not mav.armed and not mav.command_pending)
        self.disarm_btn.setEnabled(link_ok and mav.armed)
        self.control_btn.setEnabled(
            mav.control_enabled or ready
        )

    def closeEvent(self, event):
        self._closing = True
        self.timer.stop()
        self.mav.disable_control()
        self.mav.stop()
        self.wheel.stop()
        if not self._settings_dirty:
            try:
                save_settings(self.settings)
            except (OSError, ValueError, TypeError):
                pass
        event.accept()

"""Nonblocking local USB provisioning. No MAVLink/control commands are sent here."""
from __future__ import annotations

import secrets
import time

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget

from .lora import SetupExchange, password_pairing_key
from .transport import VehicleLoRa
from .serial_errors import describe_serial_error


def refresh_ports(combo):
    from serial.tools import list_ports
    selected = combo.currentText().strip()
    # Enumerating ports never opens them or switches an active session.
    ports = sorted(list_ports.comports(), key=lambda port: port.device)
    was_blocked = combo.blockSignals(True)
    try:
        combo.clear()
        for port in ports:
            combo.addItem(port.device)
            combo.setItemData(combo.count() - 1, getattr(port, "description", ""), Qt.ItemDataRole.ToolTipRole)
        combo.setCurrentText(selected)
    finally:
        combo.blockSignals(was_blocked)


class LoRaSetupWidget(QWidget):
    def __init__(self, stop_link, parent=None):
        super().__init__(parent)
        self.stop_link = stop_link
        self.link = None
        self.exchange = SetupExchange()
        self.deadline = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        title = QLabel('LoRa Setup')
        title.setStyleSheet('font-size:12pt;font-weight:700;')
        layout.addWidget(title)
        hint = QLabel('Configure one board at a time with motor power disconnected. Hold BOOT after startup to pause the board, then open native USB and read it. Set the same frequency and password on BASE and ROVER. Compiled-password presets need no setup: connect BASE directly from the main window. Their pairing can only be changed in the sketches.')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        form = QFormLayout()
        self.port = QComboBox()
        self.port.setEditable(True)
        self.port.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.port.setAccessibleName('LoRa setup COM port')
        port_row = QWidget()
        row = QHBoxLayout(port_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.port, 1)
        self.scan = QPushButton('Refresh')
        row.addWidget(self.scan)
        self.open_button = QPushButton('Open USB')
        row.addWidget(self.open_button)
        self.close_button = QPushButton('Close USB')
        row.addWidget(self.close_button)
        form.addRow('Board port', port_row)
        self.mhz = QLineEdit()
        self.mhz.setPlaceholderText('MHz, e.g. 915.000 for appropriate 915 MHz hardware')
        self.mhz.setAccessibleName('LoRa frequency in MHz')
        self.mhz.setToolTip('Enter MHz, not kHz. Zero means the board has no saved pairing frequency.')
        self.power = QSpinBox()
        self.power.setRange(2, 17)
        self.power.setSuffix(' dBm')
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_type = QComboBox()
        self.key_type.addItems(['Password (8–32 characters)', 'Advanced hex key'])
        self.key_type.setAccessibleName('LoRa credential type')
        self._credential_type()
        key_row = QWidget()
        row = QHBoxLayout(key_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.key, 1)
        self.show_key = QPushButton('Show')
        self.show_key.setCheckable(True)
        row.addWidget(self.show_key)
        self.generate = QPushButton('Generate')
        row.addWidget(self.generate)
        form.addRow('Frequency (MHz)', self.mhz)
        form.addRow('Power', self.power)
        form.addRow('Credential type', self.key_type)
        form.addRow('Password / key', key_row)
        layout.addLayout(form)
        row = QHBoxLayout()
        self.read_button = QPushButton('Read board')
        self.save_button = QPushButton('Save to board')
        self.save_button.setObjectName('Primary')
        row.addWidget(self.read_button)
        row.addWidget(self.save_button)
        layout.addLayout(row)
        self.status = QLabel('USB closed. The pairing key stays in memory only and is never read back from a board.')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addStretch()
        self.scan.clicked.connect(self.refresh_usb_ports)
        self.open_button.clicked.connect(self.open_usb)
        self.close_button.clicked.connect(self.close_usb)
        self.read_button.clicked.connect(self.read_board)
        self.save_button.clicked.connect(self.save_board)
        self.show_key.toggled.connect(self._show_key)
        self.generate.clicked.connect(self._generate)
        self.key_type.currentIndexChanged.connect(self._credential_type)
        self.timer = QTimer(self)
        self.timer.setInterval(5)
        self.timer.timeout.connect(self.poll)
        self._buttons()

    def refresh_usb_ports(self):
        try:
            refresh_ports(self.port)
        except OSError:
            self.status.setText('Could not list USB ports. Enter the COM number from Device Manager manually.')

    def _credential_type(self):
        self.key.clear()
        password = self.key_type.currentIndex() == 0
        # Keep one excess character so overlong input fails validation instead of
        # silently becoming a different valid password/key.
        self.key.setMaxLength(33 if password else 65)
        self.key.setPlaceholderText('8–32 visible ASCII characters; no spaces' if password else '64 hexadecimal characters')
        self.key.setAccessibleName('LoRa link password' if password else 'LoRa pairing key')

    def _generate(self):
        alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'
        self.key.setText(''.join(secrets.choice(alphabet) for _ in range(8))
                         if self.key_type.currentIndex() == 0 else secrets.token_hex(32))

    def _show_key(self, show):
        self.key.setEchoMode(QLineEdit.EchoMode.Normal if show else QLineEdit.EchoMode.Password)
        self.show_key.setText('Hide' if show else 'Show')

    def _buttons(self):
        opened = self.link is not None
        pending = self.exchange.pending is not None
        self.open_button.setEnabled(not opened)
        self.close_button.setEnabled(opened)
        self.port.setEnabled(not opened)
        self.scan.setEnabled(not opened)
        self.read_button.setEnabled(opened and not pending and not self.exchange.blocked and not self.exchange.restart_required)
        self.save_button.setEnabled(opened and self.exchange.can_save)
        for field in (self.mhz, self.power, self.key, self.key_type, self.generate):
            field.setEnabled(not pending)

    def open_usb(self):
        port = self.port.currentText().strip()
        if not port:
            self.status.setText('Choose the connected board COM port.')
            return
        if not self.stop_link():
            self.status.setText('Driving link did not stop. Close PC TeleRC before provisioning.')
            return
        if not self.close_usb():
            return
        try:
            self.link = VehicleLoRa(port)
            self.exchange = SetupExchange()
            self.timer.start()
            self.read_board()
        except Exception as exc:
            if self.close_usb():
                self.status.setText(describe_serial_error(exc, port, 'open'))
        self._buttons()

    def close_usb(self):
        self.timer.stop()
        if self.link is not None:
            try:
                self.link.close()
            except Exception:
                self.deadline = None
                self.exchange = SetupExchange()
                self.exchange.blocked = True
                self.status.setText('USB close failed. Unplug the board and retry Close USB, or exit PC TeleRC before reconnecting.')
                self._buttons()
                return False
        self.link = None
        self.deadline = None
        self.exchange = SetupExchange()
        self.show_key.setChecked(False)
        self.status.setText('USB closed. Pairing draft retained in memory for the partner board.')
        self._buttons()
        return True

    def _send(self, request):
        try:
            self.link.write(request)
            self.deadline = time.monotonic() + 2.0
            self.status.setText('Waiting for board reply…')
        except Exception as exc:
            if self.close_usb():
                self.status.setText(describe_serial_error(exc, self.port.currentText(), 'write'))
        self._buttons()

    def read_board(self):
        if not self.link:
            return
        try:
            request = self.exchange.begin_read()
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        self._send(request)

    def save_board(self):
        if not self.link:
            return
        try:
            credential = self.key.text()
            if self.key_type.currentIndex() == 0:
                credential = password_pairing_key(credential)
            request = self.exchange.begin_save(self.mhz.text(), self.power.value(), credential)
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        self._send(request)

    def poll(self):
        if not self.link:
            return
        try:
            for _ in range(8):
                packet = self.link.read_packet()
                if not packet:
                    break
                message = self.exchange.receive(packet)
                if message:
                    self.deadline = None
                    self.status.setText(message)
                    board = self.exchange.board
                    if board:
                        self.mhz.setText(f'{board.khz / 1000:g}' if board.khz else '')
                        self.power.setValue(board.power)
                        if not board.khz:
                            self.status.setText(message + '\nPairing is not configured. Enter the hardware frequency in MHz and a matching password on both boards, or upload the matching compiled preset.')
                    self._buttons()
            if self.deadline is not None and time.monotonic() >= self.deadline:
                self.exchange.timeout()
                self.deadline = None
                self.status.setText('Reply timed out. Close and reopen USB before retrying; delayed replies are ignored.')
                self._buttons()
        except Exception as exc:
            if self.close_usb():
                self.status.setText(describe_serial_error(exc, self.port.currentText(), 'read'))

    def clear_secret(self):
        self.key.clear()
        self.show_key.setChecked(False)



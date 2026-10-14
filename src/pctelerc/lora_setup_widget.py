"""Nonblocking local USB provisioning. No MAVLink/control commands are sent here."""
from __future__ import annotations

import secrets
import time

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget

from .lora import SetupExchange, password_pairing_key
from .transport import VehicleLoRa


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
        hint = QLabel('Disconnect motor power. On LilyGO firmware 0.4.0, hold BOOT after startup to pause the link. Plug in native USB, read the board, then save. Use the same frequency and password on BASE and ROVER. Exit the BOOT menu to restart.')
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
        self.mhz.setPlaceholderText('MHz, matching your board and permitted band')
        self.power = QSpinBox()
        self.power.setRange(2, 17)
        self.power.setSuffix(' dBm')
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_type = QComboBox()
        self.key_type.addItems(['8-character password', 'Advanced hex key'])
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
        form.addRow('Frequency', self.mhz)
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
        self.scan.clicked.connect(lambda: refresh_ports(self.port))
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

    def _credential_type(self):
        self.key.clear()
        password = self.key_type.currentIndex() == 0
        self.key.setMaxLength(8 if password else 64)
        self.key.setPlaceholderText('Exactly 8 visible ASCII characters' if password else '64 hexadecimal characters')
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
        self.close_usb()
        try:
            self.link = VehicleLoRa(port)
            self.exchange = SetupExchange()
            self.timer.start()
            self.read_board()
        except Exception:
            # No exception text is displayed: serial driver errors may include buffers.
            self.close_usb()
            self.status.setText('USB open failed. Check the selected native USB port and close other serial applications.')
        self._buttons()

    def close_usb(self):
        self.timer.stop()
        if self.link:
            self.link.close()
        self.link = None
        self.deadline = None
        self.exchange = SetupExchange()
        self.show_key.setChecked(False)
        self.status.setText('USB closed. Pairing draft retained in memory for the partner board.')
        self._buttons()

    def _send(self, request):
        try:
            self.link.write(request)
            self.deadline = time.monotonic() + 2.0
            self.status.setText('Waiting for board reply…')
        except Exception:
            self.close_usb()
            self.status.setText('USB write failed. Reopen and read the board before retrying.')
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
                    if board and board.khz:
                        self.mhz.setText(f'{board.khz / 1000:g}')
                        self.power.setValue(board.power)
                    self._buttons()
            if self.deadline is not None and time.monotonic() >= self.deadline:
                self.exchange.timeout()
                self.deadline = None
                self.status.setText('Reply timed out. Close and reopen USB before retrying; delayed replies are ignored.')
                self._buttons()
        except Exception:
            self.close_usb()
            self.status.setText('USB disconnected or unreadable. Reopen the selected board to continue.')

    def clear_secret(self):
        self.key.clear()
        self.show_key.setChecked(False)


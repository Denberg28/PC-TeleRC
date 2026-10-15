import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import errno
import logging

import pytest
from PySide6.QtWidgets import QApplication

from pctelerc.config import AppSettings
from pctelerc.lora import password_pairing_key
from pctelerc.lora_setup_widget import LoRaSetupWidget
from pctelerc.mavlink import MavlinkService
from pctelerc.serial_errors import describe_serial_error
from test_elrs_serial import wait_until


@pytest.fixture
def setup_widget():
    app = QApplication.instance() or QApplication([])
    widget = LoRaSetupWidget(lambda: True)
    widget.port.setCurrentText('COM9')
    yield widget
    if widget.link is not None:
        widget.link.close = lambda: None
    widget.close_usb()
    widget.close()
    app.processEvents()


def test_nine_and_32_character_passwords_match_full_length_vectors():
    assert password_pairing_key('telerc123') == '0d2035ed3309daf0729c00a9371d72cc19517347695bec5954abec99e53d2f9e'
    assert password_pairing_key('telerc123') != password_pairing_key('telerc12')
    assert len(password_pairing_key('x' * 32)) == 64


def test_setup_does_not_silently_accept_truncated_password_or_hex_key(setup_widget):
    widget = setup_widget
    widget.key.setText('telerc123')
    assert widget.key.text() == 'telerc123'
    widget.exchange.begin_read()
    widget.exchange.receive(b'TELERC_LORA_INFO_V2,BASE,1262,0,915000,2,0000,0,0,0,0,ARDUROVER')
    sent = []
    widget.link = type('Link', (), {'write': lambda self, value: sent.append(value), 'close': lambda self: None})()
    widget.mhz.setText('915')
    widget.key.setText('x' * 40)
    widget.save_board()
    assert not sent and '8–32' in widget.status.text()
    widget.key_type.setCurrentIndex(1)
    widget.key.setText('12' * 40)
    widget.save_board()
    assert not sent and '64 hexadecimal' in widget.status.text()


@pytest.mark.parametrize('exc,expected', [
    (PermissionError(errno.EACCES, 'secret-buffer'), 'Access denied or port busy'),
    (FileNotFoundError(errno.ENOENT, 'secret-buffer'), 'Port not found'),
    (OSError(errno.ENODEV, 'secret-buffer'), 'Device unavailable'),
    (RuntimeError('secret-buffer'), 'Check the native USB COM port'),
])
def test_serial_errors_are_actionable_and_never_echo_buffers(exc, expected):
    result = describe_serial_error(exc, 'COM9')
    assert 'COM9' in result and expected in result and 'secret-buffer' not in result


def test_wrapped_pyserial_permission_error_is_classified_without_raw_text():
    import serial
    exc = serial.SerialException("could not open port 'COM9': PermissionError(13, 'Access is denied.', None, 5), SECRET")
    assert 'Access denied or port busy' in describe_serial_error(exc, 'COM9')
    assert 'SECRET' not in describe_serial_error(exc, 'COM9')
    assert 'SECRET' not in describe_serial_error(exc, 'SECRET')


def test_setup_open_failure_reports_cause_without_key_or_exception(monkeypatch, setup_widget):
    import pctelerc.lora_setup_widget as module
    def fail(port):
        raise PermissionError(errno.EACCES, 'private-driver-buffer')
    monkeypatch.setattr(module, 'VehicleLoRa', fail)
    setup_widget.key.setText('telerc123')
    setup_widget.open_usb()
    assert setup_widget.link is None and not setup_widget.timer.isActive()
    assert 'COM9' in setup_widget.status.text() and 'Access denied' in setup_widget.status.text()
    assert 'private-driver-buffer' not in setup_widget.status.text()
    assert 'telerc123' not in setup_widget.status.text()


def test_close_failure_keeps_port_owned_and_blocks_further_operations(setup_widget):
    class Link:
        def close(self):
            raise OSError('secret-buffer')
    setup_widget.link = Link()
    assert setup_widget.close_usb() is False
    assert setup_widget.link is not None and setup_widget.exchange.blocked
    assert not setup_widget.open_button.isEnabled()
    assert not setup_widget.save_button.isEnabled() and not setup_widget.read_button.isEnabled()
    assert 'secret-buffer' not in setup_widget.status.text()
    setup_widget.link.close = lambda: None
    assert setup_widget.close_usb() is True and setup_widget.link is None


def test_blank_board_clears_previous_frequency_and_explains_pairing(setup_widget):
    replies = [b'TELERC_LORA_INFO_V2,BASE,1262,0,0,2,0000,0,0,0,0,ARDUROVER']
    setup_widget.link = type('Link', (), {'read_packet': lambda self: replies.pop(0) if replies else b'', 'close': lambda self: None})()
    setup_widget.mhz.setText('915')
    setup_widget.exchange.begin_read()
    setup_widget.poll()
    assert setup_widget.mhz.text() == ''
    assert 'not configured' in setup_widget.status.text()


def test_main_worker_reports_usb_permission_failure_without_logging_buffer(monkeypatch, caplog):
    import serial
    def factory(**kwargs):
        raise PermissionError(errno.EACCES, 'private-driver-buffer')
    monkeypatch.setattr(serial, 'Serial', factory)
    service = MavlinkService()
    service.configure(AppSettings(link_mode='lora_usb', lora_port='COM9'))
    with caplog.at_level(logging.ERROR):
        service.start()
        try:
            assert wait_until(lambda: bool(service.snapshot().error))
            assert 'Access denied' in service.snapshot().error
            assert not service.snapshot().control_enabled
        finally:
            service.stop()
    assert 'private-driver-buffer' not in caplog.text


def test_port_refresh_failure_keeps_manual_selection(monkeypatch, setup_widget):
    import serial.tools.list_ports
    def fail():
        raise OSError('private-driver-buffer')
    monkeypatch.setattr(serial.tools.list_ports, 'comports', fail)
    setup_widget.refresh_usb_ports()
    assert setup_widget.port.currentText() == 'COM9'
    assert 'manually' in setup_widget.status.text()
    assert 'private-driver-buffer' not in setup_widget.status.text()

@pytest.mark.parametrize('password', ['telerc123', 'x' * 32])
def test_setup_sends_full_length_derived_key_only(setup_widget, password):
    sent = []
    setup_widget.link = type('Link', (), {'write': lambda self, value: sent.append(value), 'close': lambda self: None})()
    setup_widget.exchange.begin_read()
    setup_widget.exchange.receive(b'TELERC_LORA_INFO_V2,BASE,1262,0,915000,2,0000,0,0,0,0,ARDUROVER')
    setup_widget.mhz.setText('915.000')
    setup_widget.key.setText(password)
    setup_widget.save_board()
    assert sent == [f'TELERC_LORA_SET_V1,915000,2,{password_pairing_key(password)}'.encode()]
    assert password.encode() not in sent[0]


@pytest.mark.parametrize('transport_name', ['VehicleLoRa', 'VehicleSerial'])
def test_failed_constructor_cleanup_preserves_original_error(monkeypatch, transport_name):
    import serial
    from pctelerc import transport
    class Port:
        def __init__(self, **kwargs):
            pass
        def open(self):
            raise PermissionError(errno.EACCES, 'primary')
        def close(self):
            raise OSError('cleanup')
    monkeypatch.setattr(serial, 'Serial', Port)
    with pytest.raises(PermissionError):
        getattr(transport, transport_name)('COM9')

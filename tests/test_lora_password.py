import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtWidgets import QApplication, QLineEdit
from pctelerc.lora import password_pairing_key
from pctelerc.lora_setup_widget import LoRaSetupWidget

VECTOR = '1bd10955bf293a2ec597c50b47cc23f28f560b9f3c3c0eaf214d61b545849fba'


def test_password_matches_firmware_known_vector_and_is_case_sensitive():
    assert password_pairing_key('Ab12Cd34') == VECTOR
    assert password_pairing_key('ab12Cd34') != VECTOR


@pytest.mark.parametrize('password', ['', 'short', 'x' * 33, '1234 678', '1234567\n', '1234567é', '1234567\x7f'])
def test_password_rejects_invalid_length_and_characters_without_echo(password):
    with pytest.raises(ValueError) as error:
        password_pairing_key(password)
    assert password not in str(error.value) or not password


def test_setup_password_and_advanced_key_send_derived_key_only():
    app = QApplication.instance() or QApplication([])
    widget = LoRaSetupWidget(lambda: True)
    sent = []
    class Link:
        def write(self, value): sent.append(value)
        def close(self): pass
    widget.link = Link()
    def ready():
        widget.exchange.begin_read()
        widget.exchange.receive(b'TELERC_LORA_INFO_V2,BASE,1262,0,915000,2,0000,0,0,0,0,ARDUROVER')
    ready()
    widget.mhz.setText('915')
    widget.key.setText('Ab12Cd34')
    assert widget.key.maxLength() == 33 and widget.key.echoMode() == QLineEdit.EchoMode.Password
    widget.save_board()
    assert sent == [f'TELERC_LORA_SET_V1,915000,2,{VECTOR}'.encode()]
    assert b'Ab12Cd34' not in sent[0]
    assert not widget.key_type.isEnabled()
    widget.close_usb()
    assert widget.key.text() == 'Ab12Cd34'  # pair the partner using the same draft
    widget.generate.click()
    assert len(widget.key.text()) == 8
    widget.key_type.setCurrentIndex(1)
    assert widget.key.text() == '' and widget.key.maxLength() == 65
    widget.key.setText('12' * 32)
    widget.link = Link()
    ready()
    widget.save_board()
    assert sent[-1].endswith(('12' * 32).encode())
    widget.close_usb()
    widget.clear_secret()
    assert not widget.key.text()
    widget.close()
    app.processEvents()


def test_sketch_pairing_lock_is_reported_without_echoing_a_secret():
    from pctelerc.lora import SetupExchange
    state = SetupExchange()
    state.begin_read()
    state.receive(b'TELERC_LORA_INFO_V2,BASE,1262,0,915000,2,0000,0,0,0,0,ARDUROVER')
    state.begin_save('915', 2, VECTOR)
    message = state.receive(b'TELERC_LORA_RESULT_V1,SKETCH_PAIRING_LOCKED')
    assert 'sketch' in message and VECTOR not in message
    assert state.board is None and not state.pending and not state.can_save


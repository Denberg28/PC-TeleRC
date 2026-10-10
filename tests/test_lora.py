import binascii
import struct
import time

import pytest
from pymavlink.dialects.v10 import ardupilotmega as mavlink1

from pctelerc.config import AppSettings, save_settings
from pctelerc.core import ControlFrame, LinkState
from pctelerc.field_safety import can_enable_control, validate_mapping
from pctelerc.lora import Board, Parser, SetupExchange, encode, setup_request
from pctelerc.mavlink import MavlinkService
from pctelerc.transport import VehicleLoRa
from test_elrs_serial import FakeSerial, wait_until

ACTIVE = b'TELERC_LORA_INFO_V1,BASE,1262,1,915000,2,ab12,3,0,0,0'
BLANK = b'TELERC_LORA_INFO_V1,ROVER,1276,0,0,2,0000,0,0,0,0'
KEY = '12' * 32


def test_usb_frame_matches_firmware_crc_and_resynchronizes():
    packet = b'TELERC_DISCOVER_V1'
    frame = encode(packet)
    body = struct.pack('<H', len(packet)) + packet
    assert frame == b'\xa5\x5a' + body + struct.pack('<H', binascii.crc_hqx(body, 0xffff))
    parser = Parser()
    damaged = bytearray(frame); damaged[-1] ^= 1
    assert parser.feed(b'noise\xa5\x5a\xff\xff' + damaged + frame[:3], 1) == []
    assert parser.feed(frame[3:] + encode(b'x'), 1.01) == [packet, b'x']
    assert len(parser.buffer) == 0


def test_partial_frame_expires_even_during_empty_polls():
    frame = encode(b'abc')
    parser = Parser()
    assert parser.feed(frame[:4], 1) == []
    assert parser.feed(b'', 1.01) == []
    assert parser.feed(frame[4:], 1.03) == []
    assert parser.feed(frame, 1.04) == [b'abc']
    for invalid in (b'', bytes(281)):
        with pytest.raises(ValueError): encode(invalid)


@pytest.mark.parametrize('packet', [ACTIVE.replace(b'BASE', b'OTHER'), ACTIVE.replace(b'1262', b'1280'), ACTIVE.replace(b'ab12', b'KEY'), ACTIVE.replace(b',3,', b',4294967296,'), ACTIVE.replace(b'915000', b'0'), b'\xff'])
def test_invalid_board_replies_are_rejected(packet):
    assert Board.parse(packet) is None


def test_setup_exact_precision_key_and_exchange_timeout():
    assert Board.parse(BLANK).role == 'ROVER'
    assert setup_request('915.125', 2, KEY) == f'TELERC_LORA_SET_V1,915125,2,{KEY}'.encode()
    for frequency, power, key in [('NaN', 2, KEY), ('Infinity', 2, KEY), ('915.0001', 2, KEY), ('149', 2, KEY), ('915', 18, KEY), ('915', 2, '0'*64), ('915', 2, 'z'*64)]:
        with pytest.raises(ValueError): setup_request(frequency, power, key)
    state = SetupExchange()
    with pytest.raises(ValueError): state.begin_save('915', 2, KEY)
    state.begin_read()
    assert state.receive(b'TELERC_LORA_RESULT_V1,SAVED_RESTART_BOARD') is None
    assert state.receive(BLANK)
    assert state.can_save
    assert KEY.encode() in state.begin_save('915', 2, KEY)
    with pytest.raises(ValueError): state.begin_read()
    state.timeout()
    assert state.blocked
    assert state.receive(b'TELERC_LORA_RESULT_V1,SAVED_RESTART_BOARD') is None
    with pytest.raises(ValueError): state.begin_read()
    assert KEY not in repr(vars(state))


def test_active_board_cannot_be_saved_and_success_requires_restart():
    state = SetupExchange(); state.begin_read(); state.receive(ACTIVE)
    assert not state.can_save
    with pytest.raises(ValueError): state.begin_save('915', 2, KEY)
    state = SetupExchange(); state.begin_read(); state.receive(BLANK)
    state.begin_save('915', 2, KEY)
    assert 'restart' in state.receive(b'TELERC_LORA_RESULT_V1,SAVED_RESTART_BOARD')
    assert state.restart_required and not state.can_save
    with pytest.raises(ValueError): state.begin_read()


class LoRaSerial(FakeSerial):
    board_reply = ACTIVE
    def reset_input_buffer(self): self.rx.clear()
    def write(self, data):
        count = super().write(data)
        for packet in Parser().feed(data, time.monotonic()):
            if packet == b'TELERC_LORA_GET_V1':
                self.rx.extend(encode(self.board_reply))
        return count


def test_lora_transport_native_cdc_crc_and_backpressure(monkeypatch):
    import serial
    monkeypatch.setattr(serial, 'Serial', LoRaSerial)
    link = VehicleLoRa('COM7')
    try:
        assert link.port.options['baudrate'] == 115200
        assert link.port.options['write_timeout'] == .02
        assert link.port.open_signals == (True, False)
        assert link.write(b'abc') == 3
        assert link.port.tx[-1] == encode(b'abc')
        link.port.rx.extend(encode(ACTIVE))
        assert link.recv() == b''  # local text never contaminates MAVLink
        link.port.out_waiting = 1
        with pytest.raises(OSError, match='backed up'): link.write(b'abc')
    finally:
        link.close()
    assert not link.port.is_open


@pytest.mark.parametrize('reply, expected', [(BLANK, 'ROVER board'), (ACTIVE.replace(b',1,915000', b',0,915000'), 'inactive')])
def test_wrong_or_inactive_board_fails_before_control(monkeypatch, reply, expected):
    import serial
    ports = []
    def factory(**kwargs):
        port = LoRaSerial(**kwargs); port.board_reply = reply; ports.append(port); return port
    monkeypatch.setattr(serial, 'Serial', factory)
    service = MavlinkService()
    service.configure(AppSettings(link_mode='lora_usb', lora_port='COM7'))
    service.start()
    try:
        assert wait_until(lambda: expected in service.snapshot().error)
        assert not service.snapshot().running
        packets = [Parser().feed(frame, time.monotonic())[0] for frame in ports[0].tx]
        assert packets == [b'TELERC_LORA_GET_V1']
        assert wait_until(lambda: not ports[0].is_open)
    finally:
        service.stop()


def test_native_lora_worker_drive_arm_stop_and_manual_reconnect(monkeypatch):
    import serial
    ports = []
    def factory(**kwargs):
        port = LoRaSerial(**kwargs); ports.append(port); return port
    monkeypatch.setattr(serial, 'Serial', factory)
    service = MavlinkService()
    service.configure(AppSettings(link_mode='lora_usb', lora_port='COM7'))
    service.start()
    try:
        assert wait_until(lambda: service.snapshot().running)
        encoder = mavlink1.MAVLink(None, srcSystem=1, srcComponent=1)
        ports[0].rx.extend(encode(encoder.heartbeat_encode(10, 0, 0, 1, 4).pack(encoder)))
        assert wait_until(lambda: service.snapshot().state == LinkState.CONNECTED)
        service.set_control_frame(ControlFrame(0, 0, time.monotonic()), 3)
        assert not service.arm()[0]  # ownership must be explicitly enabled first
        assert service.enable_control()[0]
        assert service.arm()[0]
        service.set_control_frame(ControlFrame(.4, .8, time.monotonic()), 3)
        assert wait_until(lambda: service.snapshot().steer_pwm == 1700)
        assert service.stop()
        packets = [Parser().feed(frame, time.monotonic())[0] for frame in ports[0].tx]
        assert b'TELERC_DISCOVER_V1' in packets
        assert b'TELERC_DISCONNECT_V1' in packets
        decoder = mavlink1.MAVLink(None)
        messages = [decoder.parse_char(p) for p in packets if p[0] == 0xfe]
        overrides = [m for m in messages if m.get_type() == 'RC_CHANNELS_OVERRIDE']
        assert any(m.chan1_raw == 1700 and m.chan2_raw == 1600 for m in overrides)
        assert overrides[-1].chan1_raw == 0 and overrides[-1].chan2_raw == 0
        assert not service.snapshot().control_enabled and not ports[0].is_open
        service.start()
        assert wait_until(lambda: len(ports) == 2 and service.snapshot().running)
        assert service.snapshot().state == LinkState.CONNECTING
        assert not service.snapshot().control_enabled
    finally:
        service.stop()


def test_lora_mapping_neutral_gate_and_credentials_not_persisted(tmp_path):
    settings = AppSettings(link_mode='lora_usb', lora_port='COM7').validate()
    assert validate_mapping(settings, 3).allowed
    assert not validate_mapping(AppSettings(link_mode='lora_usb', throttle_channel=3), 3).allowed
    assert not validate_mapping(AppSettings(link_mode='lora_usb', throttle_channel=5), 3).allowed
    assert not can_enable_control(settings=settings, link_state=LinkState.CONNECTED,
                                  frame=ControlFrame(.2, 0, time.monotonic()), axis_count=3).allowed
    file = save_settings(settings, tmp_path/'settings.json')
    assert KEY not in file.read_text() and 'pairing_key' not in file.read_text()

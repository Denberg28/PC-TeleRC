import time
from types import SimpleNamespace

import pytest
from pymavlink.dialects.v10 import ardupilotmega as mavlink1

from pctelerc.config import AppSettings
from pctelerc.core import ControlFrame, LinkState
from pctelerc.lora import Board, RemoteStatus, encode
from pctelerc.mavlink import MavlinkService
from test_elrs_serial import wait_until
from test_lora import LoRaSerial

BOARD = b'TELERC_LORA_INFO_V2,BASE,1262,1,915000,2,ab12,3,0,0,0,ARDUROVER'


def status(ready=0, owned=0, stops=0, boot=123, reason=0, at=None):
    return RemoteStatus.parse(f'TELERC_LORA_STATUS_V1,{ready},{owned},{stops},{boot},{reason},0'.encode(),
                              time.monotonic() if at is None else at)


def service():
    svc = MavlinkService()
    svc.configure(AppSettings(link_mode='lora_usb', lora_port='COM7'))
    svc._lora_backend = 'ARDUROVER'
    svc._link = SimpleNamespace(remote_status=status())
    svc._send_override = lambda steer, drive: True
    svc._send_neutral_then_release = lambda: True
    heartbeat(svc)
    svc.set_control_frame(ControlFrame(0, 0, time.monotonic()), 3)
    return svc


def heartbeat(svc, autopilot=3, mode=0, system=1):
    encoder = mavlink1.MAVLink(None, srcSystem=system, srcComponent=1)
    msg = encoder.heartbeat_encode(10, autopilot, 1, mode, 4)
    msg.pack(encoder)
    svc._handle_message(msg, time.monotonic())


def test_versioned_board_profile_does_not_confuse_direct_or_unknown_firmware():
    assert Board.parse(BOARD).backend == 'ARDUROVER'
    assert Board.parse(BOARD.replace(b'ARDUROVER', b'OTHER')) is None
    assert Board.parse(BOARD.replace(b'INFO_V2', b'INFO_V1')) is None
    for packet in (b'TELERC_LORA_STATUS_V1,2,0,0,123,0,0',
                   b'TELERC_LORA_STATUS_V1,0,4,0,123,0,0',
                   b'TELERC_LORA_STATUS_V1,0,0,0,0,0,0',
                   b'TELERC_LORA_STATUS_V1,0,0,0,123,8,0',
                   b'TELERC_LORA_STATUS_V1,0,0,4294967296,123,0,0'):
        assert RemoteStatus.parse(packet, 1) is None


def test_real_ardurover_heartbeat_and_fresh_remote_status_required():
    svc = service()
    assert svc.snapshot().mode == 'MANUAL'
    assert svc.enable_control()[0]
    svc.disable_control()
    svc._link.remote_status = status(at=time.monotonic() - .6)
    assert not svc.enable_control()[0]
    svc._link.remote_status = status()
    heartbeat(svc, mode=4)  # HOLD
    assert not svc.enable_control()[0]
    svc = MavlinkService(); svc.configure(AppSettings(link_mode='lora_usb'))
    svc._lora_backend = 'ARDUROVER'
    heartbeat(svc, autopilot=0)
    assert svc.snapshot().last_heartbeat is None
    heartbeat(svc, system=42)
    assert svc.snapshot().last_heartbeat is None


def test_acquisition_sends_only_neutral_until_rover_accepts_then_drives():
    svc = service(); sent = []
    svc._send_override = lambda steer, drive: sent.append((steer, drive)) or True
    assert svc.enable_control()[0]
    svc.set_control_frame(ControlFrame(.6, .8, time.monotonic()), 3)
    svc._control_tick(time.monotonic())
    assert sent == [(1500, 1500)]
    svc._link.remote_status = status(1, 3)
    svc._control_tick(time.monotonic())
    assert sent[-1][0] == 1800 and sent[-1][1] > 1500
    assert svc._lora_direct_deadline is None


@pytest.mark.parametrize('fault', ['stop', 'boot', 'stale', 'ownership', 'mode'])
def test_remote_faults_latch_pc_off_and_never_auto_resume(fault):
    svc = service(); assert svc.enable_control()[0]
    svc._link.remote_status = status(1, 3); svc._control_tick(time.monotonic())
    if fault == 'stop': svc._link.remote_status = status(0, 0, stops=1, reason=1)
    elif fault == 'boot': svc._link.remote_status = status(boot=456)
    elif fault == 'stale': svc._link.remote_status = status(1, 3, at=time.monotonic()-.6)
    elif fault == 'ownership': svc._link.remote_status = status()
    elif fault == 'mode': heartbeat(svc, mode=4)
    svc._control_tick(time.monotonic())
    assert svc.snapshot().failsafe_latched and not svc.snapshot().control_enabled
    svc._link.remote_status = status(1, 3)
    heartbeat(svc)
    svc._control_tick(time.monotonic())
    assert not svc.snapshot().control_enabled and svc.snapshot().error


def test_missing_neutral_acceptance_times_out_without_motion():
    svc = service(); assert svc.enable_control()[0]
    svc._lora_direct_deadline = time.monotonic() - .01
    svc._control_tick(time.monotonic())
    assert not svc.snapshot().control_enabled
    assert '2.5 seconds' in svc.snapshot().error


def test_native_usb_worker_accepts_new_profile_and_real_fc_telemetry(monkeypatch):
    import serial
    ports = []
    def factory(**kwargs):
        port = LoRaSerial(**kwargs); port.board_reply = BOARD; ports.append(port); return port
    monkeypatch.setattr(serial, 'Serial', factory)
    svc = MavlinkService()
    svc.configure(AppSettings(link_mode='lora_usb', lora_port='COM7'))
    svc.start()
    try:
        assert wait_until(lambda: svc.snapshot().running)
        encoder = mavlink1.MAVLink(None, srcSystem=1, srcComponent=1)
        ports[0].rx.extend(encode(b'TELERC_LORA_STATUS_V1,0,0,0,123,0,0'))
        ports[0].rx.extend(encode(encoder.heartbeat_encode(10, 3, 1, 0, 4).pack(encoder)))
        assert wait_until(lambda: svc.snapshot().state == LinkState.CONNECTED)
        svc.set_control_frame(ControlFrame(0, 0, time.monotonic()), 3)
        assert svc.enable_control()[0]
        ports[0].rx.extend(encode(b'TELERC_LORA_STATUS_V1,1,3,0,123,0,0'))
        assert wait_until(lambda: svc._lora_direct_deadline is None)
        ports[0].rx.extend(encode(b'TELERC_LORA_STATUS_V1,0,0,1,123,1,500'))
        assert wait_until(lambda: svc.snapshot().failsafe_latched)
        assert 'command-timeout' in svc.snapshot().error
    finally:
        svc.stop()

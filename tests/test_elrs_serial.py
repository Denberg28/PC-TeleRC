import time
from types import SimpleNamespace

import pytest
from pymavlink.dialects.v10 import ardupilotmega as mavlink1

from pctelerc.config import AppSettings
from pctelerc.core import ControlFrame, LinkState
from pctelerc.mavlink import MavlinkService
from pctelerc.transport import VehicleSerial


class FakeSerial:
    def __init__(self, **kwargs):
        self.options = kwargs
        self.is_open = False
        self.rx = bytearray()
        self.tx = []
        self.out_waiting = 0
        self.open_signals = None

    def open(self):
        self.open_signals = (self.dtr, self.rts)
        self.is_open = True

    @property
    def in_waiting(self): return len(self.rx)

    def read(self, count):
        result = bytes(self.rx[:count])
        del self.rx[:count]
        return result

    def write(self, data):
        if not self.is_open: raise OSError('USB removed')
        self.tx.append(bytes(data))
        return len(data)

    def reset_output_buffer(self): self.out_waiting = 0
    def close(self): self.is_open = False


def wait_until(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate(): return True
        time.sleep(.01)
    return False


def test_serial_configures_signals_before_open_and_surfaces_backpressure(monkeypatch):
    import serial
    monkeypatch.setattr(serial, 'Serial', FakeSerial)
    link = VehicleSerial('COM5')
    try:
        assert link.port.options['baudrate'] == 460800
        assert link.port.options['timeout'] == 0
        assert link.port.open_signals == (False, False)
        assert link.write(b'x') == 1
        link.port.out_waiting = 129
        with pytest.raises(OSError, match='backed up'): link.write(b'x')
    finally:
        link.close()
    assert link.destination is None


def test_elrs_worker_sends_heartbeat_without_bridge_packets_then_drive_release(monkeypatch):
    import serial
    ports = []
    def factory(**kwargs):
        port = FakeSerial(**kwargs)
        ports.append(port)
        return port
    monkeypatch.setattr(serial, 'Serial', factory)
    service = MavlinkService()
    service.configure(AppSettings(link_mode='elrs_serial', elrs_port='COM5'))
    service.start()
    try:
        assert wait_until(lambda: bool(ports) and ports[0].tx)
        port = ports[0]
        assert all(frame[0] == 0xFE for frame in port.tx)
        decoder = mavlink1.MAVLink(None)
        assert decoder.parse_char(port.tx[0]).get_type() == 'HEARTBEAT'
        encoder = mavlink1.MAVLink(None, srcSystem=42, srcComponent=1)
        port.rx.extend(encoder.heartbeat_encode(10, 3, 0, 0, 4).pack(encoder))
        assert wait_until(lambda: service.snapshot().state == LinkState.CONNECTED)
        service.set_control_frame(ControlFrame(0, 0, time.monotonic()), 3)
        assert service.enable_control()[0]
        service.set_control_frame(ControlFrame(.4, .8, time.monotonic()), 3)
        assert wait_until(lambda: service.snapshot().steer_pwm == 1700, .3)
        assert service.stop()
        assert not port.is_open
        messages = [decoder.parse_char(frame) for frame in port.tx]
        overrides = [m for m in messages if m.get_type() == 'RC_CHANNELS_OVERRIDE']
        assert any(m.chan1_raw == 1700 for m in overrides)
        assert overrides[-1].chan1_raw == 0 and overrides[-1].chan2_raw == 0
        assert not service.snapshot().control_enabled
    finally:
        service.stop()


def test_serial_mode_missing_port_fails_without_opening_anything(monkeypatch):
    import serial
    monkeypatch.setattr(serial, 'Serial', lambda **kwargs: pytest.fail('unexpected port open'))
    service = MavlinkService()
    service.configure(AppSettings(link_mode='elrs_serial'))
    service.start()
    try:
        assert wait_until(lambda: 'COM port' in service.snapshot().error)
        assert not service.snapshot().running
    finally:
        service.stop()

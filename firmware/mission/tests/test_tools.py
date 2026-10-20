import importlib.util
from pathlib import Path
import random
import sys
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from provision import provision
from usb_gateway import encode, Decoder, split_mav
from mission_client import read_plan, compare, fingerprint

def test_private_profiles_are_isolated(tmp_path):
    a = tmp_path/'a'
    b = tmp_path/'b'
    provision(a, count=20, relays=2)
    provision(b, count=20, relays=2)
    assert len(list(a.glob('TeleRCMission_*'))) == 23
    base = (a/'TeleRCMission_BASE/Config.h').read_text()
    rover = (a/'TeleRCMission_ROVER_001/Config.h').read_text()
    node = (a/'TeleRCMission_NODE_1/Config.h').read_text()
    assert 'ROVERS[]={{0,{0}}}' in node
    assert '#define ROVER_ID 1' in rover
    # Only BASE holds all vehicle keys; NODE has none.
    assert len(base) > len(rover) * 4
    assert base != (b/'TeleRCMission_BASE/Config.h').read_text()
    with pytest.raises(ValueError):
        provision(a)
    with pytest.raises(ValueError):
        provision(tmp_path/'bad', password='telerc123')

def test_usb_chunking_noise_crc_and_bounded_input():
    payload = bytes(range(100))
    packet = encode(20, 1, payload)
    d = Decoder()
    results = []
    for byte in b'noise'+packet:
        results.extend(d.feed(bytes([byte])))
    assert results == [(20, 1, payload)]
    for index in range(len(packet)):
        corrupt = bytearray(packet)
        corrupt[index] ^= 128
        assert not Decoder().feed(corrupt)
    d.feed(b'\xff'*100000)
    assert len(d.buf) <= 1

def test_mav_datagram_splitting():
    from pymavlink.dialects.v20 import common as m
    raw = bytes(m.MAVLink_heartbeat_message(6, 8, 0, 0, 4, 3).pack(m.MAVLink(None)))
    assert split_mav(raw+raw) == [raw, raw]
    with pytest.raises(ValueError):
        split_mav(raw[:-1])

def plan(tmp_path, command=16):
    p = tmp_path/'mission.waypoints'
    p.write_text(f'QGC WPL 110\n0\t1\t3\t16\t0\t0\t0\t0\t13.6\t123.2\t0\t1\n1\t0\t3\t{command}\t0\t0\t0\t0\t13.6001\t123.2\t0\t1\n')
    return p

def test_plan_and_readback_fail_closed(tmp_path):
    items = read_plan(plan(tmp_path))
    compare(items, items)
    assert fingerprint(items, 1) != fingerprint(items, 2)
    import copy
    changed = copy.deepcopy(items)
    changed[1]['x'] += 1
    with pytest.raises(RuntimeError):
        compare(items, changed)
    changed = copy.deepcopy(items)
    changed[1]['params'][0] = float('nan')
    with pytest.raises(RuntimeError):
        compare(items, changed)
    with pytest.raises(ValueError):
        read_plan(plan(tmp_path, command=400))

def test_password_generation_is_salted(tmp_path):
    provision(tmp_path/'a', password='a long private phrase with spaces')
    provision(tmp_path/'b', password='a long private phrase with spaces')
    assert (tmp_path/'a/TeleRCMission_BASE/Config.h').read_text() != (tmp_path/'b/TeleRCMission_BASE/Config.h').read_text()

def test_separate_start_never_uploads_or_arms(tmp_path, monkeypatch):
    import mission_client as mod
    path = plan(tmp_path)
    items = mod.read_plan(path)
    phrase = f'START 1 {mod.fingerprint(items, 1)[:12]}'
    calls = []
    class Fake:
        start_attempted = False
        def __init__(self, endpoint, rover):
            self.link = self
        def heartbeat(self, **kwargs):
            calls.append('heartbeat')
        def loss_policy(self, value, **kwargs):
            calls.append('policy')
        def download(self):
            calls.append('readback')
            return items
        def start_once(self):
            calls.append('start')
            self.start_attempted = True
        def recv(self, *args):
            raise KeyboardInterrupt
        def hold(self):
            calls.append('hold')
        def close(self):
            calls.append('close')
    monkeypatch.setattr(mod, 'Client', Fake)
    monkeypatch.setattr('builtins.input', lambda text: phrase)
    monkeypatch.setattr(sys, 'argv', ['mission_client.py', '--rover', '1', '--relays', '0', 'start', str(path)])
    mod.main()
    assert calls == ['heartbeat', 'policy', 'readback', 'readback', 'policy', 'start', 'hold', 'close']

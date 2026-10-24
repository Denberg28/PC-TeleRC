"""Run the unchanged PC v1.0.1 serial drivers against the actual native BASE."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import threading
import types

import pytest

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT.parents[1]/'src'
sys.path.insert(0,str(APP))
spec=importlib.util.spec_from_file_location('unified_provision',ROOT/'tools/provision.py')
generator=importlib.util.module_from_spec(spec);spec.loader.exec_module(generator)

@pytest.fixture
def base(tmp_path,monkeypatch):
    generator.provision(tmp_path/'private',relays=2)
    binary=tmp_path/'base'
    subprocess.run(['g++','-std=c++17','-I'+str(tmp_path/'private/TeleRCUnified_BASE'),
        '-I'+str(ROOT/'tests/stubs'),str(ROOT/'tests/usb_bridge.cpp'),'-lcrypto','-o',str(binary)],check=True)
    processes=[]
    class Port:
        def __init__(self,**_):
            self.proc=subprocess.Popen([str(binary)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
            processes.append(self.proc);self.buffer=bytearray();self.is_open=False;self.out_waiting=0;self.port=None
        def open(self):self.is_open=True
        def close(self):self.is_open=False;self.proc.terminate();self.proc.wait(timeout=2)
        def reset_input_buffer(self):self.buffer.clear()
        def reset_output_buffer(self):pass
        @property
        def in_waiting(self):return len(self.buffer)
        def write(self,data):
            self.proc.stdin.write(bytes(data).hex()+'\n');self.proc.stdin.flush()
            self.buffer.extend(bytes.fromhex(self.proc.stdout.readline().strip()));return len(data)
        def read(self,n):
            out=bytes(self.buffer[:n]);del self.buffer[:n];return out
    monkeypatch.setitem(sys.modules,'serial',types.SimpleNamespace(Serial=Port))
    yield
    for proc in processes:
        if proc.poll() is None:proc.terminate();proc.wait(timeout=2)

def test_released_manual_driver_accepts_unified_base(base):
    from pctelerc.transport import VehicleLoRa
    link=VehicleLoRa('TEST')
    try:
        board=link.require_active_base(threading.Event())
        assert board.role=='BASE' and board.active and board.backend=='ARDUROVER'
        assert board.khz==915000
    finally:link.close()

def test_released_mission_driver_accepts_unified_base(base):
    from pctelerc.mission_transport import MissionUSB
    link=MissionUSB('TEST',1)
    try:
        caps=link.handshake()
        assert caps==dict(relays=2,mask=0,firmware='0.2.0')
    finally:link.close()

def test_one_private_generation_has_both_validators_and_no_endpoint_keys_in_nodes(tmp_path):
    generator.provision(tmp_path/'profiles',count=2,relays=2)
    for role in ('BASE','ROVER_001','NODE_1','NODE_2'):
        folder=tmp_path/'profiles'/('TeleRCUnified_'+role)
        assert (folder/'Manual.h').exists()
        config=(folder/'Config.h').read_text()
        assert '#define PROVISIONED 1' in config
        if role.startswith('NODE'):
            assert 'ROVERS[]={{0,{0}}}' in config

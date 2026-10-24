"""Graph delivery of real role packets; no RF physics or measured capacity claim."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import pytest
from pymavlink.dialects.v10 import common as m

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from provision import provision,add_device
sys.path.insert(0,str(ROOT.parents[1]/'src'))
from pctelerc.mission_protocol.usb_gateway import encode

@pytest.fixture(scope='module')
def binaries(tmp_path_factory):
    temp=tmp_path_factory.mktemp('network');profiles=temp/'profiles';provision(profiles,relays=3)
    add_device(profiles/'NETWORK.private.json',profiles/'TeleRCScale_NODE_200','NODE',200)
    result={}
    for role in ['BASE','ROVER_001','NODE_1','NODE_3','NODE_200']:
        binary=temp/role
        subprocess.run(['g++','-std=c++17','-I'+str(profiles/('TeleRCScale_'+role)),'-I'+str(ROOT/'tests/stubs'),str(ROOT/'tests/radio_bridge.cpp'),'-lcrypto','-o',str(binary)],check=True)
        result[role]=binary
    return result

class Network:
    def __init__(self,binaries,edges):
        self.procs={r:subprocess.Popen([str(p)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True) for r,p in binaries.items()}
        self.edges={frozenset(e) for e in edges};self.incoming=[];self.states={};self.trace=[];self.now=0
    def close(self):
        for p in self.procs.values():p.terminate();p.wait(timeout=2)
    def step(self,now,usb=b'',duplicate=False):
        self.now=now
        due=[e for e in self.incoming if e[0]<=now];self.incoming=[e for e in self.incoming if e[0]>now]
        gcs=m.MAVLink(None,srcSystem=1,srcComponent=1)
        hb=bytes(m.MAVLink_heartbeat_message(10,3,1,0,3,3).pack(gcs)) if now%200==0 else b''
        for role,p in self.procs.items():
            packets=[e[2] for e in due if e[1]==role] or [b'']
            for i,packet in enumerate(packets):
                command=f'{now} {packet.hex() or "-"} {(usb.hex() if role=="BASE" and i==0 else "-") or "-"} {(hb.hex() if role=="ROVER_001" and i==0 else "-") or "-"}\n'
                p.stdin.write(command);p.stdin.flush();fields=p.stdout.readline().split();assert fields,role
                self.states[role]=list(map(int,fields[1:]))
                if fields[0]!='-':
                    raw=bytes.fromhex(fields[0]);self.trace.append((now,role,raw))
                    for dest in self.procs:
                        if frozenset((role,dest)) in self.edges:
                            self.incoming.append((now+20,dest,raw))
                            if duplicate:self.incoming.append((now+30,dest,raw))
    def run(self,start,end,mission=False,duplicate=False):
        gcs=m.MAVLink(None,srcSystem=255,srcComponent=190)
        hb=bytes(m.MAVLink_heartbeat_message(6,8,0,0,3,3).pack(gcs))
        for now in range(start,end,10):
            payload=encode(1,3,b'INFO') if mission and now==start else encode(1,1,hb) if mission and now%300==0 else b''
            self.step(now,payload,duplicate)

def test_node3_and_200_discover_ordered_return_path_and_transport_only_current_commands(binaries):
    net=Network(binaries,[('BASE','NODE_3'),('NODE_3','NODE_200'),('NODE_200','ROVER_001')])
    try:
        net.run(0,4000)
        assert net.states['BASE'][:4]==[2,3,200,1]
        assert net.states['ROVER_001'][4]==0 # Health discovery cannot write FC UART.
        net.run(4000,7000,mission=True,duplicate=True)
        assert net.states['ROVER_001'][4]>0 and net.states['ROVER_001'][5]==0
        commands=[p for _,role,p in net.trace if role=='BASE' and p[3]==3]
        assert commands and all(p[7]==2 and p[12:14]==bytes([3,200]) for p in commands)
    finally:net.close()

def test_route_failure_then_later_node_can_recover_without_reflashing_existing_roles(binaries):
    net=Network(binaries,[('BASE','NODE_3'),('NODE_3','ROVER_001')])
    try:
        net.run(0,3500);assert net.states['BASE'][:4]==[1,3,0,1]
        net.edges={frozenset(('BASE','NODE_1')),frozenset(('NODE_1','ROVER_001'))}
        net.run(3500,15000)
        assert net.states['BASE'][:4]==[1,1,0,1]
        assert net.states['ROVER_001'][4]==0 and net.states['ROVER_001'][5]==0
    finally:net.close()

def test_no_route_discovery_is_rate_limited_and_never_fabricates_fc_or_control(binaries):
    net=Network(binaries,[])
    try:
        net.run(0,16000)
        queries=[t for t,role,p in net.trace if role=='BASE']
        assert 2<=len(queries)<=4 and all(b-a>=5000 for a,b in zip(queries,queries[1:]))
        assert net.states['BASE'][3]==0 and net.states['ROVER_001'][4:6]==[0,0]
    finally:net.close()

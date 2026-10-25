"""Read-only FC inspection through actual MAVLink and addressed USB queues."""
from dataclasses import replace
from collections import Counter
from copy import copy
import time
import pytest
from PySide6.QtWidgets import QAbstractItemView
from pymavlink.dialects.v20 import common as m
from pctelerc.fleet_transport import FleetHub
from pctelerc.mission_service import MissionService
from pctelerc.mission_plan import Plan,Point,parse_text
from pctelerc.mission_protocol.usb_gateway import Decoder,encode
from pctelerc.mission_protocol.client import from_message
from pctelerc.fleet_window import FleetWindow
from test_fleet_station import Serial,Peer,services,wait,CAPS


class ReadPeer(Peer):
    def __init__(self,rover):
        super().__init__(rover)
        self.read_mode=False;self.read_parser=m.MAVLink(None)
        self.requests=Counter();self.sent_types=[]
        self.drop=False;self.silent=False;self.change_count=False
    def write(self,data):
        for _,kind,raw in Decoder().feed(data):
            if kind!=1:continue
            msg=self.read_parser.parse_char(raw);name=msg.get_type()
            if not self.read_mode:continue
            self.sent_types.append(name)
            if name=='MISSION_REQUEST_LIST':
                self.requests['count']+=1
                if self.silent or (self.drop and self.requests['count']==1):return len(data)
                count=self.count+(1 if self.change_count and self.requests['count']>1 else 0)
                self.send(m.MAVLink_mission_count_message(255,190,count,0));return len(data)
            if name=='MISSION_REQUEST_INT':
                self.requests[msg.seq]+=1
                if self.drop and msg.seq==1 and self.requests[1]==1:return len(data)
                # A valid-looking foreign source and a duplicate previous row
                # cannot replace the selected rover's requested sequence.
                if msg.seq>0:
                    previous=copy(self.items[msg.seq-1])
                    previous.target_system=255;previous.target_component=190
                    self.send(previous)
                    self.incoming.extend(encode(self.rover,1,previous.pack(m.MAVLink(None,srcSystem=20,srcComponent=1))))
        return super().write(data)


class ReadSerial(Serial):
    caps=CAPS
    def write(self,data):
        for rover,kind,raw in Decoder().feed(data):
            if kind==4 and raw==b'OPEN':self.peers.setdefault(rover,ReadPeer(rover))
        return super().write(data)


@pytest.fixture
def fleet(qt_application,monkeypatch):
    import pctelerc.mission_readback as readback
    monkeypatch.setattr(readback,'TIMEOUT',.12)
    monkeypatch.setattr(readback,'HOP_TIMEOUT',0)
    hub=FleetHub('COM9',ReadSerial);sv=services(hub,(1,2))
    yield hub,sv
    hub.close()
    for service in sv.values():service.close()


def upload(hub,sv):
    items=parse_text(Plan([Point(13.6,123.2),Point(13.6001,123.2001)]).wpl())
    s=sv[1];s.submit('upload',items)
    wait(sv.values(),lambda:bool(s.verified_digest) and not hub.operation.locked())
    return items


def test_loss_duplicates_foreign_packets_and_live_auto_inspect_are_read_only(fleet):
    hub,sv=fleet;items=upload(hub,sv);s=sv[1];peer=hub.port.peers[1]
    peer.armed=True;peer.mode=10
    wait(sv.values(),lambda:s.snapshot.armed and s.snapshot.mode=='AUTO')
    peer.read_mode=True;peer.drop=True;results=[]
    s.events.stored_mission.connect(results.append)
    other_hb=sv[2].snapshot.last_heartbeat
    s.submit('inspect',[])
    wait(sv.values(),lambda:bool(results) and not hub.operation.locked())
    result=results[0]
    assert result['rover']==1 and result['generation']==s.generation
    assert len(result['rows'])==len(items) and all(row['seq']==i for i,row in enumerate(result['rows']))
    assert peer.requests['count']>=3 and peer.requests[1]==2
    assert set(peer.sent_types)<={'HEARTBEAT','MISSION_REQUEST_LIST','MISSION_REQUEST_INT','MISSION_ACK'}
    assert not peer.commands and not hub.port.peers[2].commands
    assert peer.armed and peer.mode==10 and sv[2].snapshot.last_heartbeat>other_hb
    assert not s.verified_digest and s.phase=='FC mission retrieved · monitor only'


@pytest.mark.parametrize('count',[0,1])
def test_empty_and_home_only_storage_is_reported_without_replacement(fleet,count):
    hub,sv=fleet;peer=hub.port.peers[1]
    if count:
        upload(hub,sv)
        peer.count=1;peer.items={0:peer.items[0]}
    peer.read_mode=True;results=[];sv[1].events.stored_mission.connect(results.append)
    sv[1].submit('inspect',[])
    wait(sv.values(),lambda:bool(results) and not hub.operation.locked())
    assert len(results[0]['rows'])==count and peer.count==count
    assert not peer.commands and 'MISSION_COUNT' not in peer.sent_types
    assert not sv[1].verified_digest


def test_incomplete_inspection_does_not_show_partial_data_or_stop_healthy_auto(fleet):
    hub,sv=fleet;upload(hub,sv);s=sv[1];peer=hub.port.peers[1]
    peer.armed=True;peer.mode=10;peer.read_mode=True;peer.silent=True
    results=[];s.events.stored_mission.connect(results.append)
    s.submit('inspect',[])
    wait(sv.values(),lambda:s.phase=='FC read incomplete · monitor only' and not hub.operation.locked())
    assert not results and not s.verified_digest and s.running and peer.armed and peer.mode==10
    assert peer.requests['count']==5 and not peer.commands


def test_mission_count_change_rejects_snapshot(fleet):
    hub,sv=fleet;upload(hub,sv);s=sv[1];peer=hub.port.peers[1]
    peer.read_mode=True;peer.change_count=True;results=[];s.events.stored_mission.connect(results.append)
    s.submit('inspect',[])
    wait(sv.values(),lambda:s.phase=='FC read incomplete · monitor only' and not hub.operation.locked())
    assert not results and not s.verified_digest and not peer.commands


def test_hold_interrupts_read_and_never_replays_start(fleet):
    hub,sv=fleet;upload(hub,sv);s=sv[1];peer=hub.port.peers[1]
    peer.read_mode=True;peer.silent=True;results=[];s.events.stored_mission.connect(results.append)
    s.submit('inspect',[]);wait(sv.values(),lambda:peer.requests['count']>=1)
    s.hold();wait(sv.values(),lambda:s.phase=='HOLD confirmed')
    assert not results and not s.verified_digest and 300 not in peer.commands
    assert peer.commands==[176] and not hub.port.peers[2].commands


def test_inspection_cannot_overlap_another_rover_transaction(fleet):
    hub,sv=fleet;s=sv[1];peer=hub.port.peers[1]
    peer.read_mode=True;peer.silent=True;s.submit('inspect',[])
    wait(sv.values(),lambda:hub.operation.locked())
    with pytest.raises(RuntimeError,match='Another rover'):sv[2].submit('inspect',[])
    s.hold();wait(sv.values(),lambda:s.phase=='HOLD confirmed')


def test_viewer_is_modeless_read_only_and_rejects_stale_identity(tmp_path,qt_application,monkeypatch):
    w=FleetWindow(draft_root=tmp_path/'plans');w.map.set_online(False)
    p=w.panels[1];p._add(13.6,123.2);before=p._draft_text()
    p.connected=True;p.service.generation=7
    payload=dict(rover=1,generation=7,rows=[],read_at=time.time())
    monkeypatch.setattr(MissionService,'running',property(lambda _:True))
    try:
        p._show_stored_mission(dict(payload,generation=6));assert getattr(p,'_fc_viewer',None) is None
        p._show_stored_mission(dict(payload,rover=2));assert getattr(p,'_fc_viewer',None) is None
        p._show_stored_mission(payload);qt_application.processEvents()
        viewer=p._fc_viewer
        assert viewer is not None and not viewer.isModal() and viewer.table.rowCount()==0
        assert viewer.table.editTriggers()==QAbstractItemView.EditTrigger.NoEditTriggers
        assert p._draft_text()==before and not p.digest
        w.select_rover(2);assert p._fc_viewer is None
        p._show_stored_mission(payload);assert p._fc_viewer is None
    finally:
        monkeypatch.setattr(MissionService,'running',property(lambda _:False));w.close()


def test_load_button_submits_inspection_and_clears_ui_verification(tmp_path,qt_application,monkeypatch):
    w=FleetWindow(draft_root=tmp_path/'plans');w.map.set_online(False)
    p=w.panels[1];p._add(13.6,123.2);before=p._draft_text();p.connected=True
    p._last_snapshot=replace(p.service.snapshot,running=True,last_heartbeat=time.monotonic())
    p.digest='previous';calls=[]
    monkeypatch.setattr(MissionService,'running',property(lambda _:True))
    monkeypatch.setattr(p.service,'submit',lambda action,items:calls.append((action,items)))
    try:
        p._controls();assert p.inspect_btn.isEnabled()
        p.inspect_btn.click()
        assert calls==[('inspect',[])] and p.busy and not p.digest and p._draft_text()==before
    finally:
        monkeypatch.setattr(MissionService,'running',property(lambda _:False));w.close()

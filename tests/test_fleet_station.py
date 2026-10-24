"""Shared serial owner, real MAVLink worker transactions and passive fleet map."""
from dataclasses import replace
import threading,time
import pytest
from PySide6.QtWidgets import QApplication,QPushButton
from pymavlink.dialects.v20 import common as m
from pctelerc.mission_protocol.usb_gateway import Decoder,encode
from pctelerc.fleet_transport import FleetHub,fleet_capabilities
from pctelerc.fleet_map import FleetMap
from pctelerc.fleet_window import FleetWindow
from pctelerc.mission_service import MissionService
from pctelerc.mission_plan import Plan,Point,parse_text
from pctelerc.mavlink import MavlinkSnapshot
from pctelerc.core import LinkState
from test_mission_session import NativePeer

CAPS=b'TF3;fw=0.5.0;relays=2;mask=0;rovers=20;arm=1;budget=2000'

class Peer(NativePeer):
 def __init__(self,rover):
  super().__init__(rover);self.parameters.update(FS_GCS_TIMEOUT=7,ARMING_CHECK=1,ARMING_REQUIRE=1)
  self.inspector=m.MAVLink(None);self.arm_acks=True;self.arm_values=[];self.latitude=136000000+rover*1000
 def write(self,data):
  for _,kind,raw in Decoder().feed(data):
   if kind==1:
    msg=self.inspector.parse_char(raw)
    if msg.get_type()=='COMMAND_LONG' and msg.command==400:
     assert msg.target_system==self.rover and msg.target_component==1
     self.arm_values.append((msg.param1,msg.param2));self.commands.append(400);self.armed=msg.param1==1
     if self.arm_acks:self.send(m.MAVLink_command_ack_message(400,0,0,0,255,190))
     return len(data)
  return super().write(data)
 def read(self,n):
  now=time.monotonic()
  if self.active and now-self.last_beat>.25:
   self.last_beat=now
   self.send(m.MAVLink_heartbeat_message(10,3,129 if self.armed else 1,self.mode,3,3))
   self.send(m.MAVLink_gps_raw_int_message(int(now*1e6),3,self.latitude,1232000000,0,100,100,0,0,10))
   self.send(m.MAVLink_global_position_int_message(int(now*1000)&0xffffffff,self.latitude,1232000000,0,0,0,0,0,0))
  data=bytes(self.incoming[:n]);del self.incoming[:n];return data

class Serial:
 caps=CAPS
 def __init__(self,**kwargs):
  self.rx=bytearray();self.is_open=False;self.out_waiting=0;self.dtr=False;self.rts=True;self.port=None
  self.peers={};self.subscribed=set();self.tx=[];self.decoder=Decoder();self.lock=threading.RLock()
 def open(self):self.is_open=True
 def close(self):self.is_open=False
 @property
 def in_waiting(self):return len(self.rx)
 def reset_input_buffer(self):self.rx.clear()
 def reset_output_buffer(self):pass
 def write(self,data):
  with self.lock:
   self.tx.append(bytes(data))
   for rover,kind,raw in self.decoder.feed(data):
    if kind==3:self.rx.extend(encode(rover,3,self.caps))
    elif kind==4:
     if raw==b'OPEN':
      self.peers.setdefault(rover,Peer(rover));self.subscribed.add(rover);self.rx.extend(encode(rover,4,b'OPENED'))
     else:self.subscribed.discard(rover)
    else:
     assert rover in self.subscribed;self.peers[rover].write(encode(rover,kind,raw))
  return len(data)
 def read(self,n):
  with self.lock:
   for rover in self.subscribed:self.rx.extend(self.peers[rover].read(512))
   data=bytes(self.rx[:n]);del self.rx[:n];return data


def wait(services,predicate,timeout=10):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  for s in services:s.pulse()
  QApplication.processEvents()
  if predicate():return
  time.sleep(.005)
 raise AssertionError('Fleet condition timed out')


def services(hub,ids):
 result={i:MissionService(lambda _,rover:hub.channel(rover),fleet_actions=True,operation_gate=hub.operation) for i in ids}
 for i,s in result.items():s.connect('COM9',i)
 wait(result.values(),lambda:all(s._confirmed for s in result.values()))
 return result


def test_shared_port_three_workers_and_disconnect_isolates_one_rover(qt_application):
 hub=FleetHub('COM9',Serial);sv=services(hub,(1,2,20))
 try:
  assert len(hub.channels)==3
  assert {s.snapshot.vehicle_system for s in sv.values()}=={1,2,20}
  assert not any(p.commands for p in hub.port.peers.values())
  sv[1].close();n=hub.port.peers[1].heartbeats;other=hub.port.peers[2].heartbeats
  wait(sv.values(),lambda:hub.port.peers[2].heartbeats>other,2)
  assert hub.port.is_open and hub.port.peers[1].heartbeats==n and sv[2].running
 finally:
  hub.close()
  for s in sv.values():s.close()


def test_fleet_upload_arm_start_priority_disarm_and_other_rover_monitoring(qt_application):
 hub=FleetHub('COM9',Serial);sv=services(hub,(1,2));s=sv[1]
 items=parse_text(Plan([Point(13.6,123.2)]).wpl())
 try:
  s.submit('upload',items);wait(sv.values(),lambda:bool(s.verified_digest))
  s.submit('arm',items);wait(sv.values(),lambda:s.phase=='Armed · not started')
  assert hub.port.peers[1].arm_values==[(1,0)] and not hub.port.peers[2].commands
  s.submit('start',items);wait(sv.values(),lambda:s.phase=='AUTO · running')
  s.request_disarm();wait(sv.values(),lambda:s.phase=='Disarmed · HOLD')
  assert hub.port.peers[1].arm_values==[(1,0),(0,0)]
  assert hub.port.peers[1].commands.count(300)==1 and not hub.port.peers[2].commands
  assert not s.verified_digest and sv[2].running and sv[2].snapshot.last_heartbeat>time.monotonic()-1
 finally:
  hub.close()
  for s in sv.values():s.close()


def test_lost_arm_ack_is_unknown_and_never_retried(qt_application,monkeypatch):
 import pctelerc.mission_service as module
 monkeypatch.setattr(module,'ARM_ACK_TIMEOUT',.8)
 hub=FleetHub('COM9',Serial);sv=services(hub,(1,2));s=sv[1]
 items=parse_text(Plan([Point(13.6,123.2)]).wpl())
 try:
  s.submit('upload',items);wait(sv.values(),lambda:bool(s.verified_digest))
  hub.port.peers[1].arm_acks=False;s.submit('arm',items)
  wait(sv.values(),lambda:not s.running)
  assert hub.port.peers[1].arm_values==[(1,0)] and not s.verified_digest
  assert 300 not in hub.port.peers[1].commands and sv[2].running
 finally:
  hub.close()
  for s in sv.values():s.close()


def test_virtual_channel_cannot_send_to_another_rover(qt_application):
 hub=FleetHub('COM9',Serial);link=hub.channel(1)
 try:
  with pytest.raises(ValueError,match='Cross-rover'):link.port.write(encode(2,1,b'x'))
  assert 2 not in hub.port.peers
 finally:link.close();hub.close()


def test_old_base_fails_before_any_subscription_or_command():
 class Old(Serial):caps=b'TM2;fw=0.2.0;relays=2;mask=0;unified=0.4.0'
 with pytest.raises(RuntimeError,match='Fleet BASE'):FleetHub('COM9',Old)


def test_map_keeps_identity_and_marks_last_position_stale(qt_application):
 w=FleetMap();w.set_online(False);now=time.monotonic()
 s=MavlinkSnapshot(running=True,state=LinkState.CONNECTED,vehicle_system=1,vehicle_component=1,
  last_heartbeat=now,gps_fix=3,latitude=13.6,longitude=123.2,position_timestamp=now)
 w.observe(1,s);w.observe(2,replace(s,vehicle_system=2,latitude=13.7))
 assert w.labels()=={1:'Rover 1',2:'Rover 2'}
 w.observe(1,replace(s,vehicle_system=2,latitude=0))
 assert w.positions[1][0]==13.6
 w.observe(1,replace(s,state=LinkState.STALE,running=False,latitude=0))
 assert w.positions[1][0]==13.6 and 'stale' in w.labels()[1] and 'stale' not in w.labels()[2]
 w.shutdown()


def test_map_only_roster_buttons_and_selection_never_acquire_authority(qt_application,tmp_path):
 w=FleetWindow(hub_factory=lambda _:pytest.fail('Selection must not open USB'),draft_root=tmp_path/'plans')
 w.map.set_online(False);w.show();qt_application.processEvents()
 try:
  assert not hasattr(w,'camera_view') and set(w.panels)=={1,2,3}
  for card in w.cards.values():
   assert [card[k].text() for k in ('connect','arm','start','disarm')]==['Connect','Arm','Mission start','Disarm']
   assert all(not card[k].isEnabled() for k in ('arm','start','disarm'))
  w.add_location(13.6,123.2);w.select_rover(2);w.add_location(13.7,123.3)
  assert len(w.panels[1].plan.points)==1 and w.panels[1].plan.points[0].latitude==13.6
  assert w.panels[2].plan.points[0].latitude==13.7
  w.add_rover(20);assert 20 in w.cards and not any(p.service.running for p in w.panels.values())
  from PySide6.QtCore import Qt
  from PySide6.QtTest import QTest
  QTest.keyClick(w.panels[20],Qt.Key.Key_Escape)
  assert not getattr(w.panels[20],'_shutdown_complete',False)
 finally:w.close()

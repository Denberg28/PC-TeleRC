import copy
import threading
import time
from types import SimpleNamespace

import pytest
from pymavlink.dialects.v20 import common as mav
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest

from pctelerc.mission_plan import Plan, Point, Function, parse_text
from pctelerc.mission_protocol.client import Client, compare, fingerprint
from pctelerc.mission_protocol.usb_gateway import Decoder, encode
from pctelerc.mission_service import MissionService, Cancelled
from pctelerc.mission_transport import MissionUSB
from pctelerc.mission_widget import MissionDialog


def route():
    return Plan([Point(13.6,123.2),Point(13.6001,123.2001)])


def test_wpl_ordered_points_speed_and_roundtrip():
    p=route();items=parse_text(p.wpl())
    assert [x['command'] for x in items] == [16,178,16,16]
    assert items[1]['params']==[1,.5,-1,0]
    assert items[2]['x']==136000000
    compare(items,copy.deepcopy(items))
    changed=copy.deepcopy(items);changed[2]['y']+=1
    with pytest.raises(RuntimeError):compare(items,changed)
    assert fingerprint(items,1)!=fingerprint(items,2)


def test_function_events_are_ordered_and_balanced():
    p=route();p.functions[0]=Function(9);p.points[0].actions=[(0,True)]
    with pytest.raises(ValueError,match='final OFF'):p.wpl()
    p.points[1].actions=[(0,False)]
    items=parse_text(p.wpl())
    assert [x['command'] for x in items]==[16,178,183,16,183,16,183,183]
    assert [x['params'][1] for x in items if x['command']==183]==[1100,1900,1100,1100]
    p.functions[0]=Function(5)
    with pytest.raises(ValueError,match='dedicated'):p.wpl()


def test_invalid_duplicate_outputs_coordinates_and_capacity():
    p=route();p.points[0].latitude=float('nan')
    with pytest.raises(ValueError):p.wpl()
    p=route();p.functions=[Function(9),Function(9),Function()]
    p.points[0].actions=[(0,False),(1,False)]
    with pytest.raises(ValueError,match='unique'):p.wpl()
    p=route();p.points*=31
    with pytest.raises(ValueError):p.wpl()


def test_usb_crc_noise_and_foreign_rover():
    raw=b'12345678';packet=encode(20,1,raw);decoder=Decoder();result=[]
    for b in b'noise'+packet:result+=decoder.feed(bytes([b]))
    assert result==[(20,1,raw)]
    bad=bytearray(packet);bad[-1]^=1
    assert Decoder().feed(bad)==[]
    decoder.feed(b'x'*100000);assert len(decoder.buf)<=1


class Port:
    def __init__(self):self.writes=[];self.data=b'';self.out_waiting=0;self.open=True
    @property
    def in_waiting(self):return len(self.data)
    def write(self,data):self.writes.append(data);return len(data)
    def read(self,n):d,self.data=self.data[:n],self.data[n:];return d
    def reset_output_buffer(self):pass
    def close(self):self.open=False


def usb():
    link=MissionUSB.__new__(MissionUSB);link.port=Port();link.rover=2
    link.check=lambda:None;link.gate=threading.RLock();link.status=lambda s:None;link.decoder=Decoder()
    from collections import deque
    link.messages=deque(maxlen=64);link.mav=mav.MAVLink(link,srcSystem=255,srcComponent=190)
    return link


def test_native_mission_envelope_and_partial_send_fail_closed():
    link=usb();link.mav.heartbeat_send(6,8,0,0,4)
    frames=Decoder().feed(link.port.writes[-1]);assert frames[0][:2]==(2,1)
    assert frames[0][2][0]==0xfd
    link.port.write=lambda d:len(d)-1
    with pytest.raises(OSError,match='Partial'):link.mav.heartbeat_send(6,8,0,0,4)


def test_foreign_envelope_and_inner_source_are_filtered():
    link=usb();sender=mav.MAVLink(None,srcSystem=2,srcComponent=1)
    raw=mav.MAVLink_heartbeat_message(10,3,1,4,3,3).pack(sender)
    link.port.data=encode(1,1,raw)+encode(2,1,raw)
    msg=link.recv_match();assert msg.get_srcSystem()==2;assert link.recv_match() is None
    c=Client('',2,link=link)
    foreign=mav.MAVLink(None,srcSystem=3,srcComponent=1)
    link.port.data=encode(2,1,mav.MAVLink_heartbeat_message(10,3,1,4,3,3).pack(foreign))
    assert c.recv(['HEARTBEAT'],.02) is None
    assert c.hb is None


def test_hold_or_close_prevents_late_usb_send():
    service=MissionService();link=usb();link.gate=service._gate;link.check=service._check
    service.hold()
    with pytest.raises(Cancelled):link.mav.command_long_send(2,1,300,0,0,0,0,0,0,0,0)
    assert link.port.writes==[]
    service.hold_event.clear();service.ui_at=time.monotonic()-3
    with pytest.raises(Cancelled):link.mav.heartbeat_send(6,8,0,0,4)
    assert link.port.writes==[]


def test_client_start_is_one_shot_even_after_unknown():
    link=usb();c=Client('',2,link=link);c.start_attempted=True
    with pytest.raises(RuntimeError,match='already attempted'):c.start_once()
    assert link.port.writes==[]


def test_auxiliary_preflight_never_writes_parameters():
    p=route();p.functions[0]=Function(9);p.points[0].actions=[(0,False)];items=parse_text(p.wpl())
    service=MissionService();asked=[]
    def param(name):asked.append(name);return {'SERVO9_FUNCTION':0,'SERVO9_MIN':1000,'SERVO9_MAX':2000}[name]
    c=SimpleNamespace(parameter=param)
    with pytest.raises(RuntimeError,match='explicit'):service._auxiliary(c,items,False)
    assert asked==[]
    service._auxiliary(c,items,True)
    assert asked==['SERVO9_FUNCTION','SERVO9_MIN','SERVO9_MAX']
    c.parameter=lambda name:73 if name.endswith('FUNCTION') else 1000
    with pytest.raises(RuntimeError,match='must be 0'):service._auxiliary(c,items,True)


def test_no_auto_reconnect_after_open_failure():
    attempts=[]
    def fail(port,rover):attempts.append((port,rover));raise OSError('unplugged')
    service=MissionService(fail);service.connect('COM9',3);service.thread.join(1)
    assert attempts==[('COM9',3)] and not service.running
    assert service.verified_digest==''
    with pytest.raises(RuntimeError,match='wait 5'):service.connect('COM9',4)


def test_map_click_only_edits_and_function_tool_resets(qt_application):
    calls=[];d=MissionDialog(lambda:calls.append('connect'));d.map.set_online(False);d.show()
    d.map._center=(13.6,123.2);qt_application.processEvents()
    QTest.mouseClick(d.map,Qt.MouseButton.LeftButton,pos=QPoint(d.map.width()//2,d.map.height()//2))
    assert len(d.plan.points)==1 and calls==[] and not d.service.running
    d.mode.setCurrentIndex(1);d._add(13.6001,123.2001)
    assert d.plan.points[-1].actions==[(0,True)] and d.mode.currentIndex()==0
    d.close()


def test_main_manual_paths_locked_during_mission(monkeypatch):
    from pctelerc.ui import MainWindow
    w=MainWindow(start_services=False);w._open_mission();d=w._mission_dialog
    monkeypatch.setattr(type(d.service),'running',property(lambda self:True))
    monkeypatch.setattr(w.mav,'start',lambda:pytest.fail('manual link started'))
    monkeypatch.setattr(w.mav,'enable_control',lambda:pytest.fail('manual control enabled'))
    w._apply_and_reconnect();w._toggle_control();w._vehicle_command(lambda:pytest.fail('ARM sent'))
    d.service.thread=None
    monkeypatch.setattr(type(d.service),'running',property(lambda self:False));w.close()


def test_start_ack_loss_transmits_once_and_latches_unknown(monkeypatch):
    import pctelerc.mission_protocol.client as mod
    calls=[];clock=[0.]
    link=SimpleNamespace(mav=SimpleNamespace(command_long_send=lambda *a:calls.append(a)))
    c=Client('',2,link=link);c.heartbeat=lambda **kwargs:None
    def receive(*args):clock[0]+=2;return None
    c.recv=receive
    monkeypatch.setattr(mod,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    with pytest.raises(RuntimeError,match='UNKNOWN'):c.start_once()
    assert len(calls)==1 and calls[0][2]==300 and c.start_attempted
    with pytest.raises(RuntimeError,match='already attempted'):c.start_once()
    assert len(calls)==1


def test_ui_confirmation_cancel_sends_nothing(qt_application,monkeypatch):
    from PySide6.QtWidgets import QDialog
    d=MissionDialog(lambda:True);d.plan=route();d.connected=True
    monkeypatch.setattr(type(d.service),'running',property(lambda self:True))
    monkeypatch.setattr(QDialog,'exec',lambda self:QDialog.DialogCode.Rejected)
    monkeypatch.setattr(d.service,'submit',lambda *a:pytest.fail('cancelled plan submitted'))
    d._submit('upload')
    monkeypatch.setattr(type(d.service),'running',property(lambda self:False));d.close()


def test_escape_cannot_hide_a_live_mission_session(qt_application,monkeypatch):
    calls=[];d=MissionDialog(lambda:True)
    monkeypatch.setattr(d.service,'close',lambda:calls.append('closed') or True)
    d.show();QTest.keyClick(d,Qt.Key.Key_Escape);qt_application.processEvents()
    assert calls==['closed'] and not d.isVisible() and not d.timer.isActive()


def test_disconnect_closes_mission_before_manual_reconnect(monkeypatch):
    from pctelerc.ui import MainWindow
    w=MainWindow(start_services=False);w._open_mission();d=w._mission_dialog;calls=[]
    monkeypatch.setattr(type(d.service),'running',property(lambda self:True))
    monkeypatch.setattr(d.service,'close',lambda:calls.append('mission') or True)
    monkeypatch.setattr(w.mav,'stop',lambda:calls.append('manual') or True)
    assert w._disconnect_link() and calls==['mission','manual']
    monkeypatch.setattr(type(d.service),'running',property(lambda self:False));w.close()

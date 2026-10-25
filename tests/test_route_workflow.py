"""Exercise actual popup-to-file and addressed mission/movement workflows."""
from dataclasses import replace
import json
import time
from pathlib import Path
from shiboken6 import isValid
import pytest
from PySide6.QtCore import Qt,QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QFileDialog,QDialogButtonBox
from pctelerc.fleet_window import FleetWindow
from pctelerc.fleet_map import FleetMap
from pctelerc.mission_widget import MissionDialog
from pctelerc.mission_plan import parse_text
from pctelerc.route_draft import decode
from pctelerc.route_popups import ArrivalHoldDialog
from pctelerc.mavlink import MavlinkSnapshot
from pctelerc.core import LinkState


@pytest.fixture
def window(tmp_path,qt_application):
    w=FleetWindow(hub_factory=lambda _:pytest.fail('Planning/file operation acquired USB'),draft_root=tmp_path/'plans')
    w.map.set_online(False);w.show();qt_application.processEvents()
    yield w
    w.close()


def menu_action(w,name,lat=13.6534,lon=123.1805,index=-1):
    w.map.show_route_menu(lat,lon,index)
    menu=w.map._route_menu
    action=next(a for a in menu.actions() if a.data()==name)
    assert action.isEnabled()
    action.trigger()
    if isValid(menu):menu.close()


def accept_hold():
    dialog=QApplication.activeModalWidget()
    assert isinstance(dialog,ArrivalHoldDialog)
    dialog.seconds.setValue(7)
    button=dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)
    QTest.mouseClick(button,Qt.MouseButton.LeftButton)


def test_actual_popup_route_exports_generated_file_and_reimports_editably(window,tmp_path,monkeypatch):
    w=window;p=w.panels[1]
    menu_action(w,'home')
    menu_action(w,'go',13.6535,123.1806)
    menu_action(w,'go',13.6536,123.1807)
    QTimer.singleShot(0,accept_hold)
    menu_action(w,'hold',13.6537,123.1808)
    menu_action(w,'rth')
    assert [p.kind for p in p.plan.points]==['go','go','hold','rth']
    assert [p.hold_seconds for p in p.plan.points]==[5,5,7,5]
    before=p._text();path=tmp_path/'mission.telerc.json'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *_:(str(path),'TeleRC plan (*.telerc.json)'))
    p.export_btn.click();assert path.is_file() and path.stat().st_size>0
    assert 'Saved mission.telerc.json' in p.status.text() and str(tmp_path) in p.status.text()
    w.select_rover(2);q=w.panels[2]
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *_:(str(path),''))
    q.import_btn.click()
    assert q.imported is None and q._text()==before and w.map.route_editable
    assert q.plan.home==p.plan.home and q.plan.points[2].hold_seconds==7
    assert 'Imported mission.telerc.json' in q.status.text()
    q._history_step(-1);assert not q.plan.points
    q._history_step(1);assert q._text()==before
    assert w.hub is None and not any(p.service.running for p in w.panels.values())


def test_existing_rc4_rc5_zero_duration_draft_recovers_without_losing_coordinates(window,tmp_path):
    p=window.panels[1];menu_action(window,'home');menu_action(window,'go');menu_action(window,'rth')
    expected=p._text();data=json.loads(p._draft_text())
    data['points'][0][4]=0
    data['points'][1][4]=0
    path=tmp_path/'legacy.json';path.write_text(json.dumps(data))
    q=MissionDialog(lambda:True,draft_path=path)
    assert q._text()==expected and len(q.plan.points)==2 and q.plan.home==p.plan.home
    assert all(p.hold_seconds==5 for p in q.plan.points)
    q._shutdown()


@pytest.mark.parametrize('seconds',[0,1,11,True])
def test_active_hold_duration_is_not_repaired_silently(seconds):
    data={'version':1,'points':[[13.6,123.2,[],'hold',seconds]]}
    with pytest.raises(ValueError):decode(json.dumps(data))


@pytest.mark.parametrize('name,filter,expected,native',[
    ('route','TeleRC plan (*.telerc.json)','route.telerc.json',True),
    ('route.v1','TeleRC plan (*.telerc.json)','route.v1.telerc.json',True),
    ('route','Waypoints (*.waypoints)','route.waypoints',False),
    ('route.waypoints','','route.waypoints',False),
    ('route.txt','','route.txt',False),
    ('route.JSON','','route.JSON',True),
])
def test_export_format_filename_and_next_import_location(window,tmp_path,monkeypatch,name,filter,expected,native):
    p=window.panels[1];menu_action(window,'go')
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *_:(str(tmp_path/name),filter))
    p._export();path=tmp_path/expected
    assert path.exists() and p._last_route_file==str(path)
    if native:assert len(decode(path.read_text())['points'])==1
    else:assert parse_text(path.read_text())
    seen=[]
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *args:(seen.append(args[2]) or ('','')))
    p._import();assert seen==[str(path)]


def test_export_failure_is_visible_and_does_not_destroy_existing_file(window,tmp_path,monkeypatch):
    import tempfile
    p=window.panels[1];menu_action(window,'go')
    target=tmp_path/'existing.telerc.json';target.write_text('keep this file')
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *_:(str(target),''))
    def fail(**_):raise OSError('Write access denied')
    monkeypatch.setattr(tempfile,'NamedTemporaryFile',fail)
    p._export()
    assert target.read_text()=='keep this file'
    assert p.status.text()=='Export failed: Write access denied'


def test_hold_popup_is_compact_and_cancel_does_not_edit(window,qt_application):
    p=window.panels[1];before=p._draft_text()
    def cancel():
        dialog=QApplication.activeModalWidget()
        assert isinstance(dialog,ArrivalHoldDialog)
        assert dialog.width()==320 and dialog.height()<280
        assert dialog.seconds.minimum()==2 and dialog.seconds.maximum()==10
        for child in dialog.findChildren(QDialogButtonBox):
            assert dialog.rect().contains(child.geometry())
        QTest.keyClick(dialog,Qt.Key.Key_Escape)
    QTimer.singleShot(0,cancel);menu_action(window,'hold')
    assert p._draft_text()==before


@pytest.mark.parametrize('change',[{'latitude':float('nan')},{'latitude':0,'longitude':0},
    {'gps_timestamp':-100},{'gps_fix':1},{'running':False}])
def test_invalid_or_stale_gps_does_not_show_fresh_movement(qt_application,change):
    w=FleetMap();w.set_online(False);now=time.monotonic()
    original=MavlinkSnapshot(running=True,state=LinkState.CONNECTED,vehicle_system=1,
        gps_fix=3,latitude=13.6,longitude=123.2,position_timestamp=now,last_heartbeat=now,gps_timestamp=now,heading=90,speed=.5)
    w.observe(1,original);before=w.positions[1]
    w.observe(1,replace(original,position_timestamp=now+.01,**change))
    assert w.positions[1]==before and not w.fresh(1) and 'stale' in w.labels()[1]
    w.shutdown()


def test_popup_plan_upload_arm_start_movement_hold_is_addressed(qt_application,tmp_path):
    from test_fleet_station import Serial,services,wait
    from pctelerc.fleet_transport import FleetHub
    w=FleetWindow(draft_root=tmp_path/'plans');w.map.set_online(False)
    hub=FleetHub('COM9',Serial);sv=services(hub,(1,2));s=sv[1]
    s.events.snapshot.connect(lambda snap:w.map.observe(1,snap))
    sv[2].events.snapshot.connect(lambda snap:w.map.observe(2,snap))
    try:
        menu_action(w,'home');menu_action(w,'go',13.6001,123.2001);menu_action(w,'rth')
        p=w.panels[1];items=parse_text(p._text())
        assert not any(peer.commands for peer in hub.port.peers.values())
        s.submit('upload',items);wait(sv.values(),lambda:bool(s.verified_digest) and not hub.operation.locked())
        s.submit('arm',items);wait(sv.values(),lambda:s.phase=='Armed · not started' and not hub.operation.locked())
        s.submit('start',items);wait(sv.values(),lambda:s.phase=='AUTO · running' and not hub.operation.locked())
        wait(sv.values(),lambda:1 in w.map.positions and 2 in w.map.positions)
        before=w.map.positions[1][:2];other=w.map.positions[2][:2]
        hub.port.peers[1].latitude+=1000
        wait(sv.values(),lambda:w.map.positions[1][:2]!=before)
        assert w.map.positions[2][:2]==other and not hub.port.peers[2].commands
        assert hub.port.peers[1].commands.count(300)==1
        s.hold();wait(sv.values(),lambda:s.phase=='HOLD confirmed')
        assert not s.verified_digest and not hub.port.peers[2].commands
    finally:
        hub.close()
        for service in sv.values():service.close()
        w.close()

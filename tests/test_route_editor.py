"""Real map gestures, route persistence, and command-free map actions."""
import json
import pytest
from PySide6.QtCore import Qt, QPointF
from PySide6.QtTest import QTest
from pctelerc.fleet_window import FleetWindow
from pctelerc.mission_plan import Plan, Point, parse_text
from pctelerc.mission_widget import MissionDialog
from pctelerc.mission_service import MissionService
from test_map_drag import press, move, release


@pytest.fixture
def window(qt_application,tmp_path):
    w=FleetWindow(hub_factory=lambda _:pytest.fail('Map editing opened USB'),draft_root=tmp_path/'plans')
    w.map.set_online(False);w.resize(1500,860);w.show();qt_application.processEvents()
    w.map._center=(13.6,123.2);w.map._zoom=18
    yield w
    w.close()


def choose(window,name):
    menu=window.map._route_menu
    action=next(a for a in menu.actions() if a.data()==name)
    assert action.isEnabled()
    action.trigger()
    menu.close()


def test_map_click_menu_actions_home_and_return_are_offline(window,monkeypatch,qt_application):
    w=window;m=w.map;p=w.panels[1]
    press(m,(m.width()/2,m.height()/2));release(m,(m.width()/2,m.height()/2))
    assert not p.plan.points and m._route_menu is not None
    assert {a.data() for a in m._route_menu.actions()} >= {'go','hold','rth','home'}
    assert not next(a for a in m._route_menu.actions() if a.data()=='rth').isEnabled()
    choose(w,'home');assert p.plan.home==pytest.approx((13.6,123.2))
    m.show_route_menu(13.6001,123.2001);choose(w,'go')
    monkeypatch.setattr('pctelerc.route_editor.choose_hold',lambda *_:(7,True))
    m.show_route_menu(13.6002,123.2002);choose(w,'hold')
    m.show_route_menu(13.6003,123.2003);choose(w,'rth')
    assert [p.kind for p in p.plan.points]==['go','hold','rth']
    items=parse_text(p._text())
    assert any(i['command']==93 and i['params']==[7,-1,-1,-1] for i in items)
    assert (items[-1]['x'],items[-1]['y'])==(136000000,1232000000)
    assert p.plan.points[-1].latitude==p.plan.home[0]
    assert m.planned_home==p.plan.home and not m.positions and not m.snapshots
    qt_application.processEvents();assert not m.grab().isNull()
    assert not w.hub and not any(p.service.running for p in w.panels.values())


def test_drag_waypoint_preserves_other_points_actions_and_view(window,qt_application):
    w=window;p=w.panels[1];m=w.map
    w.add_location(13.6,123.1997);w.add_location(13.6002,123.2003)
    p.plan.points[0].actions=[(0,False)]
    p.digest='previous-verification';before=m._center;old=p.plan.points[1].longitude
    start=m.project(m.points[0]);end=start+QPointF(42,26)
    press(m,(start.x(),start.y()));move(m,(end.x(),end.y()))
    assert p.plan.points[0].longitude==123.1997 and m._route_preview is not None
    w.tick();assert m._route_preview is not None
    release(m,(end.x(),end.y()))
    actual=m.project((p.plan.points[0].latitude,p.plan.points[0].longitude))
    assert (actual.x(),actual.y())==pytest.approx((end.x(),end.y()),abs=1e-6)
    assert p.plan.points[0].actions==[(0,False)] and p.plan.points[1].longitude==old
    assert m._center==before and not p.digest and len(p.plan.points)==2
    assert m._route_menu is None and w.hub is None


def test_drag_line_inserts_one_point_in_order(window):
    w=window;p=w.panels[1];m=w.map
    w.add_location(13.6,123.1995);w.add_location(13.6004,123.2005)
    original=list(m.points);start=(m.project(original[0])+m.project(original[1]))/2;end=start+QPointF(20,30)
    press(m,(start.x(),start.y()));move(m,(end.x(),end.y()));release(m,(end.x(),end.y()))
    assert len(p.plan.points)==3 and m.points[0]==original[0] and m.points[2]==original[1]
    assert m.points[1]==pytest.approx(m.route_location(end))
    assert len(parse_text(p._text()))==7 and m._route_menu is None


@pytest.mark.parametrize('cancel',['escape','lost-button','outside','rover-switch','running'])
def test_cancelled_drag_does_not_commit_or_add(window,monkeypatch,cancel):
    w=window;p=w.panels[1];m=w.map
    w.add_location(13.6,123.2);before=list(m.points)
    start=m.project(before[0]);end=start+QPointF(25,30)
    press(m,(start.x(),start.y()));move(m,(end.x(),end.y()))
    if cancel=='escape':QTest.keyClick(m,Qt.Key.Key_Escape)
    elif cancel=='lost-button':
        from test_map_drag import mouse
        from PySide6.QtCore import QEvent
        mouse(m,QEvent.Type.MouseMove,(end.x(),end.y()),buttons=Qt.MouseButton.NoButton)
    elif cancel=='rover-switch':w.select_rover(2)
    elif cancel=='running':
        monkeypatch.setattr(MissionService,'running',property(lambda _:True));p._controls()
        monkeypatch.setattr(MissionService,'running',property(lambda _:False))
    release(m,(-50,-50) if cancel=='outside' else (end.x(),end.y()))
    assert [(p.latitude,p.longitude) for p in p.plan.points]==before
    assert not w.panels[2].plan.points and m._route_preview is None


def test_old_popup_cannot_retarget_rover_or_new_draft(window):
    m=window.map
    m.show_route_menu(13.6,123.2)
    action=next(a for a in m._route_menu.actions() if a.data()=='go')
    window.select_rover(2);action.trigger()
    assert not window.panels[1].plan.points and not window.panels[2].plan.points
    m.show_route_menu(13.6,123.2)
    action=next(a for a in m._route_menu.actions() if a.data()=='go')
    window.panels[2].map_action('home',13.7,123.3);action.trigger()
    assert not window.panels[2].plan.points


def test_hold_dialog_rechecks_rover_and_session(window,monkeypatch):
    m=window.map
    def choose_and_switch(*_):
        window.select_rover(2)
        return 5,True
    monkeypatch.setattr('pctelerc.route_editor.choose_hold',choose_and_switch)
    m.show_route_menu(13.6,123.2);choose(window,'hold')
    assert not any(p.plan.points for p in window.panels.values())


def test_home_return_hold_draft_roundtrip_and_legacy_restore(tmp_path):
    path=tmp_path/'route.json';p=MissionDialog(lambda:True,draft_path=path)
    p.map_action('home',13.6,123.2);p.map_action('hold',13.61,123.21,seconds=9)
    p.map_action('rth',13.62,123.22);expected=p._text();assert p._save_draft();p._shutdown()
    q=MissionDialog(lambda:True,draft_path=path)
    assert q._text()==expected and q.plan.home==(13.6,123.2)
    assert [p.kind for p in q.plan.points]==['hold','rth'];q._shutdown()
    data=json.loads(path.read_text());data['points']=[p[:3] for p in data['points']];data.pop('home')
    path.write_text(json.dumps(data));r=MissionDialog(lambda:True,draft_path=path)
    assert r.plan.home is None and all(p.kind=='go' for p in r.plan.points);r._shutdown()


def test_return_stays_last_tracks_home_and_cannot_be_dragged(window):
    p=window.panels[1];m=window.map
    p.map_action('home',13.6,123.2);p.map_action('rth',13.61,123.21)
    p.map_action('go',13.6002,123.2002)
    assert [p.kind for p in p.plan.points]==['go','rth']
    p.map_action('home',13.6003,123.2003);assert m.points[-1]==p.plan.home
    start=m.project(m.points[-1]);end=start+QPointF(30,20);before=p._text()
    press(m,(start.x(),start.y()));move(m,(end.x(),end.y()));release(m,(end.x(),end.y()))
    assert p._text()==before
    p.rows.setCurrentRow(1);p._move(-1);assert p._text()==before


@pytest.mark.parametrize('seconds',[1,11,True,2.5])
def test_invalid_hold_rejected_by_plan_and_editor(seconds,tmp_path):
    plan=Plan([Point(13.6,123.2,kind='hold',hold_seconds=seconds)])
    with pytest.raises(ValueError,match='Hold'):plan.wpl()
    p=MissionDialog(lambda:True,draft_path=tmp_path/'plan.json')
    p.map_action('hold',13.6,123.2,seconds=seconds);assert not p.plan.points;p._shutdown()


def test_imported_routes_and_running_sessions_stay_immutable(window,monkeypatch):
    p=window.panels[1];p._add(13.6,123.2);before=p._text()
    p.imported=before;p._controls();assert not window.map.route_editable
    p.map_action('home',13.7,123.3);p.move_map_point(0,13.7,123.3)
    assert p.plan.home is None and p._text()==before
    p.imported=None
    monkeypatch.setattr(MissionService,'running',property(lambda _:True));p._controls()
    p.map_action('go',13.7,123.3);assert p._text()==before
    monkeypatch.setattr(MissionService,'running',property(lambda _:False))

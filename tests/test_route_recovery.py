"""Recover offline drafts without acquiring USB or restoring command authority."""
import json
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog
from pctelerc.fleet_window import FleetWindow
from pctelerc.mission_widget import MissionDialog
from pctelerc.mission_service import MissionService
from pctelerc.route_draft import decode


@pytest.fixture
def window(tmp_path, qt_application):
    w = FleetWindow(hub_factory=lambda _:pytest.fail('Draft recovery opened USB'), draft_root=tmp_path/'plans')
    w.map.set_online(False);w.show();qt_application.processEvents()
    yield w
    w.close()


def test_editable_plan_roundtrip_home_hold_return_outputs_and_speed(window, tmp_path, monkeypatch):
    p = window.panels[1]
    p.map_action('home',13.6,123.2)
    p.map_action('hold',13.61,123.21,seconds=8)
    p.map_action('rth',13.6,123.2)
    p.functions[0][0].setValue(9);p.speed.setValue(0.8)
    original = p._draft_text();wpl = p._text()
    path = tmp_path/'route.telerc.json'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *_:(str(path),''))
    p._export()
    window.select_rover(2);q=window.panels[2]
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *_:(str(path),''))
    q._import()
    assert q._draft_text()==original and q._text()==wpl
    assert q.imported is None and window.map.route_editable
    assert q.plan.home==(13.6,123.2) and q.plan.points[-1].kind=='rth'
    assert not q.digest and window.hub is None
    q.move_map_point(0,13.611,123.211)
    assert q.plan.points[0].latitude==13.611
    assert q._save_draft()
    restored=MissionDialog(lambda:True,draft_path=q._draft_path)
    assert restored._draft_text()==q._draft_text()
    restored._shutdown()


def test_incomplete_plan_exports_and_remains_editable(window,tmp_path,monkeypatch):
    p=window.panels[1];p.mode.setCurrentIndex(1);p._add(13.6,123.2)
    assert not p._plan_valid
    path=tmp_path/'incomplete'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *_:(str(path),'TeleRC plan (*.telerc.json)'))
    p._export()
    assert decode(path.with_suffix('.telerc.json').read_text())['points'][0][2]==[[0,True]]


def test_undo_redo_clear_restores_exact_draft_and_invalidates_verification(window):
    p=window.panels[1]
    p.map_action('home',13.6,123.2);p.map_action('hold',13.61,123.21,seconds=9)
    p.map_action('rth',13.6,123.2);p.speed.setValue(0.7)
    before=p._draft_text();view=window.map._center
    p._clear();p.digest='old';p.undo_btn.click()
    assert p._draft_text()==before and not p.digest and window.map._center==view
    p.redo_btn.click();assert not p.plan.points and p.plan.home is None
    p.undo_btn.click();p.move_map_point(0,13.62,123.22)
    assert not p.redo_btn.isEnabled() and window.hub is None


def test_history_is_per_rover_and_shortcut_uses_selected_rover(window, qt_application):
    p,q=window.panels[1],window.panels[2]
    p._add(13.6,123.2);window.select_rover(2);q._add(13.7,123.3)
    window.map.setFocus();window.activateWindow();qt_application.processEvents()
    QTest.keyClick(window.map,Qt.Key.Key_Z,Qt.KeyboardModifier.ControlModifier)
    assert len(p.plan.points)==1 and not q.plan.points
    QTest.keyClick(window.map,Qt.Key.Key_Y,Qt.KeyboardModifier.ControlModifier)
    assert len(q.plan.points)==1 and not p.service.running and window.hub is None


def test_history_locked_while_connected_or_busy(window,monkeypatch):
    p=window.panels[1];p._add(13.6,123.2);before=p._draft_text()
    p.busy=True;p._controls();p._history_step(-1)
    assert p._draft_text()==before and not p.undo_btn.isEnabled()
    p.busy=False
    monkeypatch.setattr(MissionService,'running',property(lambda _:True));p._controls()
    p._history_step(-1);assert p._draft_text()==before and not p.undo_btn.isEnabled()
    monkeypatch.setattr(MissionService,'running',property(lambda _:False))


def test_import_wpl_and_clear_can_be_undone(window,tmp_path,monkeypatch):
    p=window.panels[1];p._add(13.6,123.2);before=p._draft_text()
    path=tmp_path/'route.waypoints';path.write_text(p._text())
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *_:(str(path),''))
    p._import();assert p.imported is not None
    p._history_step(-1);assert p._draft_text()==before
    p._history_step(1);assert p.imported is not None
    p._clear();p._history_step(-1);assert p.imported is not None


def test_history_bounded_and_noop_preserves_redo(window):
    p=window.panels[1];p._add(13.6,123.2)
    for i in range(65):p.move_map_point(0,13.6+i/10000,123.2)
    assert len(p._history)==51
    p._history_step(-1);assert p.redo_btn.isEnabled()
    p._invalidate();assert p.redo_btn.isEnabled()


def test_refresh_preserves_list_selection_scroll_and_map_view(window,qt_application):
    p=window.panels[1]
    for i in range(40):p._add(13.6+i/10000,123.2)
    qt_application.processEvents();p.rows.setCurrentRow(28)
    p.rows.verticalScrollBar().setValue(24)
    before=p.rows.verticalScrollBar().value();center=window.map._center
    p.map_action('hold',13.6028,123.2,index=28,seconds=8)
    assert p.rows.currentRow()==28 and p.rows.verticalScrollBar().value()==before
    assert window.map._center==center


@pytest.mark.parametrize('broken', [[],42,{'version':True},{'version':1,'points':42},
    {'version':1,'points':[[13.6,123.2,42]]},
    {'version':1,'points':[[13.6,123.2,[0]]]},
    {'version':1,'functions':[[9,1100,1900],[0,1100,1900],42]},
    {'version':1,'speed':True}, {'version':1,'wpl':42},
    {'version':1,'home':{'a':1}}, {'version':1,'points':[[13.6,123.2,[[0,True],[0,False]]]]}])
def test_malformed_import_is_atomic_and_startup_survives(window,tmp_path,monkeypatch,broken):
    p=window.panels[1];p._add(13.6,123.2);before=p._draft_text()
    path=tmp_path/'broken.telerc.json';path.write_text(json.dumps(broken))
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *_:(str(path),''))
    p._import();assert p._draft_text()==before
    q=MissionDialog(lambda:True,draft_path=path)
    assert not q.plan.points and q.imported is None;q._shutdown()


def test_recovery_never_restores_cutoff_consent_or_verification(window):
    p=window.panels[1];p._add(13.6,123.2);p.aux.setChecked(True)
    p._clear();p.digest='stale-verification';p._history_step(-1)
    assert not p.aux.isChecked() and not p.digest
    p._history_step(1);assert not p.aux.isChecked()


def test_import_cancels_if_picker_changes_rover_or_draft(window,tmp_path,monkeypatch):
    p=window.panels[1];p._add(13.6,123.2)
    path=tmp_path/'route.telerc.json';path.write_text(p._draft_text())
    def pick(*_):
        p._add(13.7,123.3)
        return str(path),''
    monkeypatch.setattr(QFileDialog,'getOpenFileName',pick);p._import()
    assert len(p.plan.points)==2
    before=p._draft_text()
    def select(*_):
        window.select_rover(2)
        return str(path),''
    monkeypatch.setattr(QFileDialog,'getOpenFileName',select);p._import()
    assert p._draft_text()==before and not window.panels[2].plan.points

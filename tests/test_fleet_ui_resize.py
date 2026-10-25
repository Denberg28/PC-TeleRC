"""Visible resize coverage, roster lifecycle and offline route round trips."""
import math
import time

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QFileDialog

from pctelerc import fleet_window as ui
from pctelerc.config import AppSettings
from pctelerc.core import LinkState
from pctelerc.fleet_map import FleetMap
from pctelerc.mavlink import MavlinkSnapshot
from pctelerc.mission_plan import parse_text
from pctelerc.rover_map import world_pixel


@pytest.fixture
def window(qt_application, tmp_path, monkeypatch):
    monkeypatch.setattr(ui, 'load_settings', lambda: AppSettings(map_online=False))
    monkeypatch.setattr(ui, 'save_settings', lambda *_: None)
    w = ui.FleetWindow(hub_factory=lambda *_: pytest.fail('Display action opened USB'), draft_root=tmp_path/'plans')
    w.show();qt_application.processEvents()
    yield w
    w.close()


def test_resizing_keeps_cached_terrain_without_refetch_or_fake_fixes(qt_application, tmp_path, monkeypatch):
    w = FleetMap();w._cache_dir = tmp_path/'cache';w.set_online(False)
    w._center = (13.62, 123.19);w._zoom = 5
    tile = QImage(256, 256, QImage.Format.Format_RGB32);tile.fill(0xff2468ac)
    monkeypatch.setattr(w, '_request_tile', lambda *_: pytest.fail('Resize started network'))
    try:
        for width,height in ((2560,1600),(600,420),(1920,1080),(800,520)):
            w.resize(width,height)
            cx,cy = world_pixel(*w._center,w._zoom)
            for x in range(math.floor((cx-width/2)/256),math.floor((cx+width/2)/256)+1):
                for y in range(math.floor((cy-height/2)/256),math.floor((cy+height/2)/256)+1):
                    if 0 <= y < 32:w._remember((5,x%32,y),tile)
            before = w._center;w.show();qt_application.processEvents()
            for _ in range(2):
                frame = w.grab().toImage()
                for x,y in ((width//2,height//2),(10,50),(width-20,50),(10,height-30),(width-20,height-30)):
                    assert frame.pixelColor(x,y).name() == '#2468ac'
            assert w._center == before and not w.positions and not w._pending
            assert w.testAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
    finally:w.shutdown();w.close()


def test_idle_fleet_tick_does_not_repaint_map(window, monkeypatch):
    calls=[];monkeypatch.setattr(window.map, 'update', lambda: calls.append(True))
    for _ in range(20):window.tick()
    assert not calls and window.hub is None


def test_add_remove_restore_draft_and_ignore_retired_service(window):
    assert not hasattr(window,'add_id')
    window.select_rover(2);window.add_location(13.6,123.2)
    owner=window.panels[2].service
    assert window.remove_rover(2)
    assert 2 not in window.cards and window.selected in window.panels
    window.add_button.click()
    assert window.selected==2 and window.panels[2].plan.points[0].latitude==13.6
    now=time.monotonic()
    s=MavlinkSnapshot(vehicle_system=2,running=True,state=LinkState.CONNECTED,
        gps_fix=3,latitude=13.6,longitude=123.2,position_timestamp=now,last_heartbeat=now)
    window.observe_rover(2,owner,s)
    assert 2 not in window.map.positions and window.hub is None


def test_removal_keeps_last_rover_and_blocks_busy_or_unsaved_draft(window,monkeypatch):
    p=window.panels[1];p.busy=True
    assert not window.remove_rover(1)
    p.busy=False;monkeypatch.setattr(p,'_save_draft',lambda:False)
    assert not window.remove_rover(1)
    assert window.remove_rover(2) and window.remove_rover(3)
    assert not window.remove_rover(1) and 1 in window.panels


@pytest.mark.parametrize('width,height',[(1080,660),(1280,680),(1366,720),(1600,900)])
def test_route_actions_fit_and_expansion_scrolls_without_horizontal_clipping(window,qt_application,width,height):
    window.resize(width,height);qt_application.processEvents()
    p=window.panels[window.selected]
    for button in (p.import_btn,p.export_btn,p.upload_btn,window.add_button,window.remove_button):
        assert button.isVisibleTo(window)
        origin=button.mapTo(window,button.rect().topLeft())
        assert window.rect().contains(origin) and origin.x()+button.width()<=window.width()
    p.advanced_toggle.setChecked(True);qt_application.processEvents()
    details = dict(viewport=p.editor_scroll.viewport().width(),content=p.editor.width(),
        minimum=p.editor.minimumSizeHint().width(),native_minimum=p.editor.minimumWidth())
    assert p.editor_scroll.horizontalScrollBar().maximum()==0, details
    for field in (p.mode,p.lat,p.lon,p.speed,*[field for row in p.functions for field in row]):
        origin=field.mapTo(p.editor,field.rect().topLeft())
        assert origin.x()>=0 and origin.x()+field.width()<=p.editor_scroll.viewport().width(), (field,details)
    assert window.roster.horizontalScrollBar().maximum()==0
    for card in window.cards.values():
        for name in ('connect','arm','start','disarm','hold','select'):
            button=card[name];origin=button.mapTo(window.roster.widget(),button.rect().topLeft())
            assert origin.x()>=0 and origin.x()+button.width()<=window.roster.viewport().width(), name
    assert p.import_btn.isVisibleTo(window) and p.export_btn.isVisibleTo(window)
    assert not window.split.opaqueResize() and window.hub is None


def test_route_import_export_targets_selected_offline_draft(window,tmp_path,monkeypatch):
    window.add_location(13.6,123.2);window.add_location(13.601,123.201)
    path=tmp_path/'planned.waypoints'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *_:(str(path),''))
    window.panels[1].export_btn.click();expected=parse_text(path.read_text())
    window.select_rover(2)
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *_:(str(path),''))
    p=window.panels[2];p.import_btn.click()
    assert parse_text(p._text())==expected
    assert window.map.points==[(13.6,123.2),(13.601,123.201)]
    assert window.map._center==(13.6,123.2)
    assert len(window.panels[1].plan.points)==2 and not p.digest
    assert window.hub is None and not any(p.service.running for p in window.panels.values())
    original=p._text();path.write_bytes(b'\xff\xfe');p.import_btn.click()
    assert p._text()==original


def test_import_rechecks_session_after_file_picker(window,tmp_path,monkeypatch):
    p=window.panels[1];window.add_location(13.6,123.2)
    path=tmp_path/'route.waypoints';path.write_text(p._text());original=p.imported
    from pctelerc.mission_service import MissionService
    running={'value':False}
    monkeypatch.setattr(MissionService,'running',property(lambda _:running['value']))
    def pick(*_):
        running['value']=True
        return str(path),''
    monkeypatch.setattr(QFileDialog,'getOpenFileName',pick);p._import()
    assert p.imported is original
    running['value']=False

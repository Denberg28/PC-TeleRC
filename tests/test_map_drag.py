"""Real multi-event map gestures, geographic placement and terrain continuity."""
from dataclasses import replace
import math
import time

import pytest
from PySide6.QtCore import QEvent,QPointF,Qt
from PySide6.QtGui import QColor,QImage,QMouseEvent,QPainter
from PySide6.QtWidgets import QApplication

from pctelerc.fleet_map import FleetMap
from pctelerc.mission_widget import MissionMap
from pctelerc.rover_map import RoverMap,world_pixel,world_location
from pctelerc.mavlink import MavlinkSnapshot
from pctelerc.core import LinkState


def mouse(widget,kind,point,button=Qt.MouseButton.NoButton,buttons=Qt.MouseButton.LeftButton):
    p=QPointF(*point)
    QApplication.sendEvent(widget,QMouseEvent(kind,p,p,button,buttons,Qt.KeyboardModifier.NoModifier))


def press(widget,point):
    mouse(widget,QEvent.Type.MouseButtonPress,point,Qt.MouseButton.LeftButton)


def move(widget,point):
    mouse(widget,QEvent.Type.MouseMove,point)


def release(widget,point):
    mouse(widget,QEvent.Type.MouseButtonRelease,point,Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton)


@pytest.mark.parametrize('zoom',[0,5,17,22])
@pytest.mark.parametrize('point',[(0,0),(13.62,123.19),(-12.4,-50.4),(85,179.99),(-85,-179.99)])
def test_geographic_projection_round_trip(point,zoom):
    assert world_location(*world_pixel(*point,zoom),zoom)==pytest.approx(point,abs=1e-7)


def test_offset_click_matches_the_visible_world_quadrant(qt_application):
    w=MissionMap();w.set_online(False);w.resize(800,600);w._zoom=0;w._center=(0,0)
    clicks=[];w.location.connect(lambda *point:clicks.append(point))
    try:
        press(w,(464,332));release(w,(464,332))
        assert len(clicks)==1
        assert clicks[0]==pytest.approx((-40.9798980696,90),abs=1e-7)
    finally:w.shutdown()


@pytest.mark.parametrize('longitude,dx',[(-179.9999,150),(179.9999,-150)])
def test_pan_crosses_the_dateline_without_a_half_world_jump(qt_application,longitude,dx):
    w=FleetMap();w.set_online(False);w.resize(800,600);w._center=(0,longitude);w._zoom=17
    try:
        press(w,(300,200));move(w,(300+dx,200));release(w,(300+dx,200))
        expected=(longitude-dx/(256*2**17)*360+180)%360-180
        assert w._center==pytest.approx((0,expected),abs=1e-7)
    finally:w.shutdown()


@pytest.mark.parametrize('kind',[QEvent.Type.UngrabMouse,QEvent.Type.WindowDeactivate,QEvent.Type.Hide])
def test_interrupted_drag_never_places_a_waypoint(qt_application,kind):
    w=MissionMap();w.set_online(False);w.resize(800,600)
    clicks=[];w.location.connect(lambda *point:clicks.append(point))
    try:
        press(w,(300,200));QApplication.sendEvent(w,QEvent(kind));before=w._center
        move(w,(350,250));release(w,(350,250))
        assert w._center==before and not clicks and w._drag is None
    finally:w.shutdown()


@pytest.mark.parametrize('kind',[RoverMap,MissionMap,FleetMap])
def test_drag_moves_by_pointer_delta_without_a_half_world_jump(qt_application,kind):
    w=kind();w.set_online(False);w.resize(800,600);w._zoom=17;w._center=(13.62,123.19)
    origin=world_pixel(*w._center,w._zoom)
    clicks=[]
    if isinstance(w,MissionMap):w.location.connect(lambda *point:clicks.append(point))
    try:
        press(w,(300,200))
        for dx,dy in [(10,4),(20,8),(40,16),(80,32)]:
            move(w,(300+dx,200+dy))
            x,y=world_pixel(*w._center,w._zoom)
            assert x==pytest.approx(origin[0]-dx,abs=1e-6)
            assert y==pytest.approx(origin[1]-dy,abs=1e-6)
        release(w,(380,232))
        assert not clicks
    finally:w.shutdown()


@pytest.mark.parametrize('center',[(13.62,123.19),(-12.4,-50.4),(0,0),(70,179.9),(-70,-179.9)])
def test_center_click_places_waypoint_at_the_displayed_longitude(qt_application,center):
    w=MissionMap();w.set_online(False);w.resize(800,600);w._center=center
    clicks=[];w.location.connect(lambda *point:clicks.append(point))
    try:
        press(w,(400,300));release(w,(400,300))
        assert len(clicks)==1
        assert clicks[0]==pytest.approx(center,abs=1e-7)
    finally:w.shutdown()


def test_release_only_drag_is_not_a_waypoint_click(qt_application):
    w=MissionMap();w.set_online(False);w.resize(800,600);before=w._center
    clicks=[];w.location.connect(lambda *point:clicks.append(point))
    try:
        press(w,(100,100));release(w,(300,150))
        assert w._center!=before and not clicks
    finally:w.shutdown()


def test_jitter_does_not_pan_or_disable_follow(qt_application):
    w=FleetMap();w.set_online(False);w.resize(800,600);before=w._center
    clicks=[];w.location.connect(lambda *point:clicks.append(point))
    try:
        w.follow_rover=1;press(w,(400,300));move(w,(401,301))
        assert w._center==before and w.follow_rover==1
        release(w,(401,301));assert len(clicks)==1
    finally:w.shutdown()


def test_pan_and_manual_zoom_remain_selected_during_fresh_telemetry(qt_application):
    w=FleetMap();w.set_online(False);w.resize(800,600)
    now=time.monotonic()-.1
    s=MavlinkSnapshot(running=True,state=LinkState.CONNECTED,vehicle_system=1,
        gps_fix=3,latitude=13.62,longitude=123.19,last_heartbeat=now,position_timestamp=now)
    try:
        w.observe(1,s);w.follow_rover=1
        press(w,(300,200));move(w,(340,220));view=w._center
        w.observe(1,replace(s,latitude=13.63,position_timestamp=now+.01))
        assert w._center==view and w.follow_rover is None and not w.auto_fit
        release(w,(340,220))
        w.fit_fleet();w.zoom(-1);view,zoom=w._center,w._zoom
        w.observe(1,replace(s,latitude=13.64,position_timestamp=now+.02))
        assert w._center==view and w._zoom==zoom and not w.auto_fit
    finally:w.shutdown()


def test_lost_button_state_cancels_pan_without_placing_a_waypoint(qt_application):
    w=MissionMap();w.set_online(False);w.resize(800,600);before=w._center
    clicks=[];w.location.connect(lambda *point:clicks.append(point))
    try:
        press(w,(300,200))
        mouse(w,QEvent.Type.MouseMove,(350,250),buttons=Qt.MouseButton.NoButton)
        release(w,(350,250))
        assert w._center==before and not clicks and w._drag is None
    finally:w.shutdown()


def test_pan_starts_from_latest_follow_view_instead_of_an_old_press_view(qt_application):
    w=FleetMap();w.set_online(False);w.resize(800,600)
    now=time.monotonic()-.1
    s=MavlinkSnapshot(running=True,state=LinkState.CONNECTED,vehicle_system=1,gps_fix=3,
        latitude=13.62,longitude=123.19,last_heartbeat=now,position_timestamp=now)
    try:
        w.observe(1,s);w.follow_rover=1;press(w,(300,200))
        w.observe(1,replace(s,latitude=13.63,position_timestamp=now+.02))
        expected=world_pixel(*w._center,w._zoom)
        move(w,(320,210));actual=world_pixel(*w._center,w._zoom)
        assert actual==pytest.approx((expected[0]-20,expected[1]-10),abs=1e-6)
        release(w,(320,210))
    finally:w.shutdown()


def test_dragged_terrain_moves_with_the_pointer_without_blank_frames(qt_application,monkeypatch):
    w=FleetMap();w.set_online(False);w.resize(800,600);w._zoom=10;w._center=(13.62,123.19)
    tiles={}
    def tile(key):
        if key not in tiles:
            z,x,y=key;image=QImage(256,256,QImage.Format.Format_RGB32)
            image.fill(QColor(20+x%200,30+y%190,160))
            p=QPainter(image)
            for start in range(0,256,32):p.fillRect(start,0,8,256,QColor(240,210,70))
            p.end();tiles[key]=image
        return tiles[key]
    monkeypatch.setattr(w,'_tile',tile)
    try:
        w.show();qt_application.processEvents();before=w.grab().toImage()
        press(w,(300,250))
        for dx,dy in [(8,4),(16,8),(32,16),(64,32)]:
            move(w,(300+dx,250+dy));qt_application.processEvents();frame=w.grab().toImage()
            scale=frame.devicePixelRatio()
            for x,y in [(80,100),(500,140),(200,400)]:
                assert frame.pixelColor(round((x+dx)*scale),round((y+dy)*scale))==before.pixelColor(round(x*scale),round(y*scale))
        release(w,(364,282))
        assert not w.positions and not w._pending
    finally:w.shutdown();w.close()

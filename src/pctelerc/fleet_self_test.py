"""Frozen map-only fleet verification; no USB, controller or radio is opened."""
from dataclasses import replace
from contextlib import closing
from pathlib import Path
import json,sqlite3,tempfile,time,math,os
from PySide6.QtWidgets import QApplication, QFileDialog, QDialogButtonBox, QDialog
from PySide6.QtCore import QBuffer,QIODevice,Qt,QEvent,QPointF,QTimer
from PySide6.QtGui import QImage,QMouseEvent,QIcon
from .rover_map import world_pixel,world_location

from .fleet_contract import FROZEN_CHECKS as CHECKS


def run(report_path):
 from . import fleet_window as ui
 from . import __version__
 from .config import AppSettings
 from .mavlink import MavlinkSnapshot
 from .core import LinkState
 import sys
 app=QApplication.instance() or QApplication([]);app.setStyleSheet(ui.STYLE)
 old_load,old_save=ui.load_settings,ui.save_settings
 ui.load_settings=lambda:AppSettings(map_online=False)
 ui.save_settings=lambda *_:None
 checks={}
 with tempfile.TemporaryDirectory() as folder:
  folder=Path(folder)
  old_data=os.environ.get('LOCALAPPDATA')
  os.environ['LOCALAPPDATA']=str(folder/'operator-data')
  def forbidden(_):raise RuntimeError('Self-test must never acquire USB')
  window=ui.FleetWindow(hub_factory=forbidden,draft_root=folder/'plans')
  try:
   window.show();app.processEvents()
   checks['fleet_map_central']=window.map.width()>500 and window.map.height()>400
   checks['no_camera_controls']=not hasattr(window,'camera_view') and not hasattr(window,'camera_start_btn')
   checks['no_video_runtime']='pctelerc.camera' not in sys.modules and 'PySide6.QtMultimedia' not in sys.modules
   checks['initial_no_authority']=window.hub is None and not any(p.service.running for p in window.panels.values())
   checks['per_rover_controls']=all(set(('connect','arm','start','disarm')).issubset(card) for card in window.cards.values())
   checks['logo']=not window.windowIcon().isNull()
   assets=Path(ui.__file__).parent/'assets'
   checks['compact_dark_theme']=window.centralWidget().grab().toImage().pixelColor(0,0).name()=='#0d131c'
   checks['rover_icon_resolutions']={16,24,32,48,64,128,256}.issubset({s.width() for s in QIcon(str(assets/'telerc.ico')).availableSizes()})
   checks['theme_assets_decode']=all(not QImage(str(assets/name)).isNull() for name in ('telerc.png','telerc.ico','check.svg','chevron.svg','chevron-up.svg'))
   panel=window.panels[1];draft=panel._draft_text();digest=panel.digest
   for toggle in (panel.details_toggle,panel.coordinate_toggle,panel.advanced_toggle,panel.help_toggle):
    toggle.click();app.processEvents();toggle.click();app.processEvents()
   checks['optional_panels_no_authority']=draft==panel._draft_text() and digest==panel.digest and window.hub is None and not any(p.service.running for p in window.panels.values()) and panel.hold_btn.isVisibleTo(window)
   image=QImage(256,256,QImage.Format.Format_RGB32);image.fill(0xff2468ac)
   buf=QBuffer();buf.open(QIODevice.OpenModeFlag.WriteOnly);image.save(buf,'PNG')
   path=folder/'map.mbtiles'
   with closing(sqlite3.connect(path)) as db, db:
    db.execute('CREATE TABLE metadata (name TEXT, value TEXT)')
    db.executemany('INSERT INTO metadata VALUES (?,?)',[('format','png'),('center','123.2,13.6,1')])
    db.execute('CREATE TABLE tiles (zoom_level INTEGER,tile_column INTEGER,tile_row INTEGER,tile_data BLOB)')
    db.execute('INSERT INTO tiles VALUES(1,1,1,?)',(bytes(buf.data()),))
   window.map.set_offline_map(str(path));decoded=window.map._tile((1,1,0))
   checks['offline_map_decode']=decoded is not None and decoded.pixelColor(0,0).name()=='#2468ac'
   checks['offline_no_fake_gps']=not window.map.positions and not window.map.snapshots
   checks['offline_no_network']=not window.map._pending and not window.map._online
   window.add_location(13.6,123.2);window.select_rover(2);window.add_location(13.7,123.3)
   checks['isolated_plans']=window.panels[1].plan.points[0].latitude==13.6 and window.panels[2].plan.points[0].latitude==13.7
   checks['map_edit_offline']=not any(p.service.running for p in window.panels.values())
   # Some Windows clocks coalesce consecutive reads. Give the next simulated
   # GPS sample a distinct source time without weakening duplicate rejection.
   now=time.monotonic()-.1
   for rover in (1,2,3):
    s=MavlinkSnapshot(running=True,state=LinkState.CONNECTED,vehicle_system=rover,vehicle_component=1,
     gps_fix=3,latitude=13.6+rover*.001,longitude=123.2,last_heartbeat=now,position_timestamp=now)
    window.map.observe(rover,s)
   checks['map_labels']=window.map.labels()=={1:'Rover 1',2:'Rover 2',3:'Rover 3'}
   s=window.map.snapshots[1];window.map.observe(1,replace(s,vehicle_system=2,latitude=0))
   checks['identity_isolated']=math.isclose(window.map.positions[1][0],13.601)
   window.map.observe(1,replace(s,latitude=13.605,position_timestamp=time.monotonic()))
   checks['live_position_update']=window.map.positions[1][0]==13.605 and math.isclose(window.map.positions[2][0],13.602)
   window.map.observe(1,replace(s,running=False,state=LinkState.STALE,latitude=0))
   checks['stale_position_retained']=window.map.positions[1][0]==13.605 and 'stale' in window.map.labels()[1]
   window.tick()
   checks['stale_controls_disabled']=all(not b.isEnabled() for card in window.cards.values() for k,b in card.items() if k in ('arm','start','disarm'))
   window.select_rover(3);checks['selection_no_authority']=window.hub is None and not any(p.service.running for p in window.panels.values())
   window.resize(1366,720);app.processEvents()
   panel=window.panels[3]
   checks['resize_opaque_map']=window.map.testAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent) and not window.split.opaqueResize()
   checks['route_file_controls_visible']=all(b.isVisibleTo(window) and window.rect().contains(b.mapTo(window,b.rect().bottomRight())) for b in (panel.import_btn,panel.export_btn))
   panel.coordinate_toggle.setChecked(True);panel.advanced_toggle.setChecked(True);app.processEvents()
   checks['compact_layout_no_horizontal_scroll']=panel.editor_scroll.horizontalScrollBar().maximum()==0 and window.roster.horizontalScrollBar().maximum()==0
   panel.coordinate_toggle.setChecked(False);panel.advanced_toggle.setChecked(False)
   window.add_next_rover();added=window.selected
   checks['roster_add_remove']=added==4 and not hasattr(window,'add_id') and window.remove_rover(added) and set(window.panels)=={1,2,3} and window.hub is None
   # Display refresh must not continually dirty the terrain at the 10Hz
   # heartbeat/UI lease rate. The independent one-second map timer ages labels.
   original_update=window.map.update;calls=[]
   window.map.update=lambda:calls.append(True)
   for _ in range(10):window.tick()
   window.map.update=original_update
   checks['idle_map_no_repaint']=not calls
   m=window.map;m._center=(13.62,123.19);m._zoom=17;m.follow_rover=1
   expected=world_pixel(*m._center,m._zoom)
   checks['projection_round_trip']=all(math.isclose(a,b,abs_tol=1e-8) for a,b in zip(world_location(*expected,m._zoom),m._center))
   def mouse(kind,point,button=Qt.MouseButton.NoButton,buttons=Qt.MouseButton.LeftButton):
    p=QPointF(*point)
    app.sendEvent(m,QMouseEvent(kind,p,p,button,buttons,Qt.KeyboardModifier.NoModifier))
   def count():return sum(len(panel.plan.points) for panel in window.panels.values())
   before=count();pan_ok=True
   start=(m.width()/2,m.height()/2)
   mouse(QEvent.Type.MouseButtonPress,start,Qt.MouseButton.LeftButton)
   for dx,dy in ((10,4),(20,8),(40,16)):
    mouse(QEvent.Type.MouseMove,(start[0]+dx,start[1]+dy))
    actual=world_pixel(*m._center,m._zoom)
    pan_ok &= math.isclose(actual[0],expected[0]-dx,abs_tol=1e-6) and math.isclose(actual[1],expected[1]-dy,abs_tol=1e-6)
   mouse(QEvent.Type.MouseButtonRelease,(start[0]+40,start[1]+16),Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton)
   checks['drag_pan_continuity']=bool(pan_ok)
   checks['drag_no_route_edit']=count()==before and window.hub is None
   view=m._center;now=time.monotonic()
   m.observe(1,replace(m.snapshots[1],running=True,state=LinkState.CONNECTED,last_heartbeat=now,
    position_timestamp=now,latitude=13.63,longitude=123.19,gps_fix=3))
   checks['manual_view_survives_telemetry']=m._center==view and m.follow_rover is None and not m.auto_fit
   before=count();m._center=(13.62,123.19)
   mouse(QEvent.Type.MouseButtonPress,start,Qt.MouseButton.LeftButton)
   mouse(QEvent.Type.MouseButtonRelease,start,Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton)
   menu=m._route_menu
   checks['map_action_popup']=menu is not None and {'go','hold','rth','home'}.issubset({a.data() for a in menu.actions()}) and count()==before
   next(a for a in menu.actions() if a.data()=='go').trigger();menu.close()
   point=window.panels[window.selected].plan.points[-1]
   checks['click_location_correct']=count()==before+1 and math.isclose(point.latitude,13.62,abs_tol=1e-7) and math.isclose(point.longitude,123.19,abs_tol=1e-7)
   before=count();view=m._center
   mouse(QEvent.Type.MouseButtonPress,start,Qt.MouseButton.LeftButton)
   app.sendEvent(m,QEvent(QEvent.Type.WindowDeactivate))
   mouse(QEvent.Type.MouseButtonRelease,(start[0]+100,start[1]+50),Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton)
   checks['drag_interrupt_no_edit']=count()==before and m._center==view and m._drag is None
   panel=window.panels[window.selected];panel._clear()
   m._center=(13.62,123.19);m._zoom=18
   panel.map_action('home',13.62,123.19)
   panel.map_action('go',13.62,123.1895)
   panel.map_action('hold',13.6204,123.1905,seconds=7)
   panel.map_action('rth',13.621,123.191)
   from .mission_plan import parse_text
   items=parse_text(panel._text())
   checks['planned_home_return']=m.planned_home==(13.62,123.19) and panel.plan.points[-1].kind=='rth' and m.points[-1]==m.planned_home
   checks['planned_hold_roundtrip']=any(i['command']==93 and i['params']==[7,-1,-1,-1] for i in items)
   point=m.project(m.points[0]);end=point+QPointF(25,20);view=m._center
   mouse(QEvent.Type.MouseButtonPress,(point.x(),point.y()),Qt.MouseButton.LeftButton)
   mouse(QEvent.Type.MouseMove,(end.x(),end.y()))
   mouse(QEvent.Type.MouseButtonRelease,(end.x(),end.y()),Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton)
   actual=m.project(m.points[0])
   checks['waypoint_drag']=abs(actual.x()-end.x())<1e-5 and abs(actual.y()-end.y())<1e-5 and len(panel.plan.points)==3 and m._center==view
   middle=(m.project(m.points[0])+m.project(m.points[1]))/2;end=middle+QPointF(0,25)
   mouse(QEvent.Type.MouseButtonPress,(middle.x(),middle.y()),Qt.MouseButton.LeftButton)
   mouse(QEvent.Type.MouseMove,(end.x(),end.y()))
   mouse(QEvent.Type.MouseButtonRelease,(end.x(),end.y()),Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton)
   actual=m.project(m.points[1])
   checks['route_line_drag_insert']=len(panel.plan.points)==4 and abs(actual.x()-end.x())<1e-5 and abs(actual.y()-end.y())<1e-5
   point=m.project(m.points[0]);saved=list(m.points)
   mouse(QEvent.Type.MouseButtonPress,(point.x(),point.y()),Qt.MouseButton.LeftButton)
   mouse(QEvent.Type.MouseMove,(point.x()+30,point.y()+30))
   window.select_rover(1)
   mouse(QEvent.Type.MouseButtonRelease,(point.x()+30,point.y()+30),Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton)
   checks['route_gesture_rover_isolated']=panel.map.points==saved and m._route_preview is None and window.hub is None
   checks['route_actions_no_authority']=window.hub is None and not any(p.service.running for p in window.panels.values())
   panel=window.panels[window.selected];panel._clear()
   panel.map_action('home',13.62,123.19)
   panel.map_action('hold',13.6204,123.1905,seconds=8)
   panel.map_action('rth',13.62,123.19)
   saved=panel._draft_text();view=m._center
   panel._clear();panel._history_step(-1)
   undo_ok=panel._draft_text()==saved and m._center==view and not panel.digest
   panel._history_step(1)
   checks['draft_undo_redo']=undo_ok and not panel.plan.points and panel.plan.home is None
   panel._history_step(-1)
   window.select_rover(2);other=window.panels[2];other._clear()
   other._add(13.7,123.3);other._history_step(-1)
   checks['draft_history_rover_isolated']=not other.plan.points and panel._draft_text()==saved
   window.select_rover(1)
   path=folder/'roundtrip.telerc.json'
   old_open,old_save_file=QFileDialog.getOpenFileName,QFileDialog.getSaveFileName
   try:
    QFileDialog.getSaveFileName=lambda *_:(str(path),'')
    QFileDialog.getOpenFileName=lambda *_:(str(path),'')
    panel._export();window.select_rover(2);other._import()
    checks['native_plan_roundtrip']=other._draft_text()==saved and other._text()==panel._text()
    other.move_map_point(0,13.6206,123.1906)
    checks['native_plan_editable']=other.imported is None and m.route_editable and other.plan.points[0].latitude==13.6206
   finally:
    QFileDialog.getOpenFileName,QFileDialog.getSaveFileName=old_open,old_save_file
   checks['draft_recovery_no_authority']=window.hub is None and not any(p.service.running for p in window.panels.values()) and not any(p.digest for p in window.panels.values())
   window.select_rover(1);panel=window.panels[1];panel._clear()
   def choose(name,lat=13.62,lon=123.19):
    m.show_route_menu(lat,lon)
    popup=m._route_menu
    next(a for a in popup.actions() if a.data()==name).trigger()
    from shiboken6 import isValid
    if isValid(popup):popup.close()
   choose('home');choose('go',13.6201,123.1901)
   hold_checks=[]
   def hold_dialog():
    from .route_popups import ArrivalHoldDialog
    dialog=app.activeModalWidget()
    hold_checks.append(isinstance(dialog,ArrivalHoldDialog) and dialog.width()==320 and dialog.height()<280)
    if isinstance(dialog,ArrivalHoldDialog):
     dialog.seconds.setValue(7)
     dialog.accept()
    elif dialog is not None:dialog.reject()
   QTimer.singleShot(0,hold_dialog);choose('hold',13.6202,123.1902);choose('rth')
   checks['compact_arrival_hold']=hold_checks==[True] and panel.plan.points[1].hold_seconds==7
   expected=panel._text();path=folder/'popup-route.telerc.json'
   old_open,old_save_file=QFileDialog.getOpenFileName,QFileDialog.getSaveFileName
   try:
    QFileDialog.getSaveFileName=lambda *_:(str(path),'TeleRC plan (*.telerc.json)')
    QFileDialog.getOpenFileName=lambda *_:(str(path),'')
    panel._export();window.select_rover(2);other=window.panels[2];other._import()
    checks['popup_route_file_roundtrip']=path.is_file() and other.imported is None and other._text()==expected and 'Saved' in panel.status.text()
    legacy=json.loads(path.read_text());legacy['points'][0][4]=0
    path.write_text(json.dumps(legacy));other._import()
    checks['legacy_menu_draft_recovery']=other._text()==expected and other.plan.points[0].hold_seconds==5
   finally:
    QFileDialog.getOpenFileName,QFileDialog.getSaveFileName=old_open,old_save_file
   retained=m.positions[1]
   sample=m.snapshots[1];now=time.monotonic()
   m.observe(1,replace(sample,running=True,state=LinkState.CONNECTED,last_heartbeat=now,position_timestamp=now,
    gps_timestamp=now,latitude=0,longitude=0))
   checks['invalid_gps_stays_stale']=m.positions[1]==retained and not m.fresh(1) and 'stale' in m.labels()[1]
   from .stored_mission_view import StoredMissionView
   from PySide6.QtWidgets import QAbstractItemView
   panel=window.panels[window.selected]
   checks['fc_load_control_visible']=panel.inspect_btn.isVisibleTo(window) and window.rect().contains(panel.inspect_btn.mapTo(window,panel.inspect_btn.rect().bottomRight())) and not panel.inspect_btn.isEnabled()
   draft=panel._draft_text();digest=panel.digest
   snapshot=dict(rover=window.selected,generation=panel.service.generation,rows=parse_text(panel._text()),read_at=time.time())
   viewer=StoredMissionView(snapshot,window);viewer.show();app.processEvents()
   checks['fc_view_read_only_modeless']=not viewer.isModal() and app.activeModalWidget() is None and viewer.table.editTriggers()==QAbstractItemView.EditTrigger.NoEditTriggers
   checks['fc_snapshot_no_draft_mutation']=draft==panel._draft_text() and digest==panel.digest and window.hub is None
   viewer.close();app.processEvents()
   panel._show_stored_mission(dict(snapshot,generation=-1))
   checks['fc_stale_result_ignored']=getattr(panel,'_fc_viewer',None) is None and not panel.service.running



  except Exception as exc:checks['error']=type(exc).__name__+': '+str(exc)
  finally:
   window.close();app.processEvents()
   checks['close_cleans_sessions']=not any(p.service.running or p.timer.isActive() for p in window.panels.values())
   ui.load_settings,ui.save_settings=old_load,old_save
   if old_data is None:os.environ.pop('LOCALAPPDATA',None)
   else:os.environ['LOCALAPPDATA']=old_data
 result=dict(version=__version__,passed=CHECKS.issubset(checks) and all(v is True for v in checks.values()),checks=checks)
 Path(report_path).write_text(json.dumps(result,indent=2))
 return 0 if result['passed'] else 1

"""Frozen map-only fleet verification; no USB, controller or radio is opened."""
from dataclasses import replace
from pathlib import Path
import json,sqlite3,tempfile,time,math
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QBuffer,QIODevice
from PySide6.QtGui import QImage

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
   image=QImage(256,256,QImage.Format.Format_RGB32);image.fill(0xff2468ac)
   buf=QBuffer();buf.open(QIODevice.OpenModeFlag.WriteOnly);image.save(buf,'PNG')
   path=folder/'map.mbtiles'
   with sqlite3.connect(path) as db:
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
   now=time.monotonic()
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
  except Exception as exc:checks['error']=type(exc).__name__+': '+str(exc)
  finally:
   window.close();app.processEvents()
   checks['close_cleans_sessions']=not any(p.service.running or p.timer.isActive() for p in window.panels.values())
   ui.load_settings,ui.save_settings=old_load,old_save
 result=dict(version=__version__,passed=CHECKS.issubset(checks) and all(v is True for v in checks.values()),checks=checks)
 Path(report_path).write_text(json.dumps(result,indent=2))
 return 0 if result['passed'] else 1

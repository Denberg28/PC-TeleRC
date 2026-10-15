import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from dataclasses import replace
from pathlib import Path
import sqlite3
import time

import pytest
from PySide6.QtCore import QBuffer, QIODevice, QPoint, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from pctelerc.config import AppSettings, load_settings, save_settings
from pctelerc.core import LinkState
from pctelerc.mavlink import MavlinkSnapshot
from pctelerc.offline_maps import OfflineMap
from pctelerc.rover_map import RoverMap
import pctelerc.ui as ui


def make_map(path, *, scheme='tms', fmt='png'):
    image=QImage(256,256,QImage.Format.Format_RGB32); image.fill(0xff2468ac)
    buffer=QBuffer(); buffer.open(QIODevice.OpenModeFlag.WriteOnly); assert image.save(buffer,'PNG')
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE metadata (name TEXT, value TEXT)')
        db.executemany('INSERT INTO metadata VALUES (?,?)', [('format',fmt),('name','Field map'),('center','0,0,1'),('attribution','Test tiles'),('scheme',scheme)])
        db.execute('CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB, PRIMARY KEY(zoom_level,tile_column,tile_row))')
        db.execute('INSERT INTO tiles VALUES (1,1,?,?)',(0 if scheme=='tms' else 1,bytes(buffer.data())))
    return path


@pytest.mark.parametrize('scheme',['tms','xyz'])
def test_raster_mbtiles_row_orientation_and_readonly(tmp_path,scheme):
    path=make_map(tmp_path/'field.mbtiles',scheme=scheme)
    original=path.read_bytes()
    source=OfflineMap(path)
    assert source.center == (0,0,1)
    assert source.tile(1,1,1).pixelColor(0,0).name() == '#2468ac'
    assert source.tile(1,1,0).isNull()
    with pytest.raises(sqlite3.OperationalError):
        source._db.execute('DELETE FROM tiles')
    source.close()
    assert path.read_bytes() == original


def test_vector_corrupt_and_missing_files_leave_previous_map_usable(tmp_path):
    app=QApplication.instance() or QApplication([])
    widget=RoverMap(cache_dir=tmp_path/'cache'); widget.set_online(False)
    try:
        widget.set_offline_map(make_map(tmp_path/'good.mbtiles'))
        for path in (make_map(tmp_path/'vector.mbtiles',fmt='pbf'),tmp_path/'missing.mbtiles'):
            with pytest.raises((ValueError,OSError)):
                widget.set_offline_map(path)
            assert widget._tile((1,1,1)).pixelColor(0,0).name() == '#2468ac'
        broken=tmp_path/'broken.mbtiles'; broken.write_text('invalid SQLite')
        with pytest.raises(ValueError): widget.set_offline_map(broken)
    finally:
        widget.shutdown()


def test_expired_cache_works_offline_after_restart_without_network(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    cache=tmp_path/'cache'; cache.mkdir()
    tile=cache/'17-1-2.png'
    image=QImage(256,256,QImage.Format.Format_RGB32); image.fill(0xff2468ac); image.save(str(tile))
    os.utime(tile,(1,1))
    widget=RoverMap(cache_dir=cache); widget.set_online(False)
    monkeypatch.setattr(widget,'_request_tile',lambda *_: pytest.fail('Offline mode requested network'))
    try:
        assert widget._tile((17,1,2)).pixelColor(0,0).name() == '#2468ac'
        assert widget._tile((17,4,5)) is None
        widget._center=(13.62,123.19); widget._zoom=16
    finally: widget.shutdown()
    reopened=RoverMap(cache_dir=cache); reopened.set_online(False)
    try:
        assert reopened._center == (13.62,123.19)
        assert reopened._last_position is None
        assert reopened._zoom == 16
    finally: reopened.shutdown()


def test_map_browsing_does_not_fabricate_rover_and_locate_restores_follow(tmp_path):
    app=QApplication.instance() or QApplication([])
    widget=RoverMap(cache_dir=tmp_path/'cache'); widget.set_online(False)
    try:
        widget.set_offline_map(make_map(tmp_path/'map.mbtiles'))
        assert widget._last_position is None and not widget._track
        widget.show(); app.processEvents()
        QTest.mousePress(widget,Qt.MouseButton.LeftButton,pos=QPoint(100,75))
        QTest.mouseMove(widget,QPoint(130,85))
        QTest.mouseRelease(widget,Qt.MouseButton.LeftButton,pos=QPoint(130,85))
        assert widget._center != (0,0) and not widget._follow
        snap=MavlinkSnapshot(state=LinkState.CONNECTED,gps_fix=3,latitude=13.62,longitude=123.19,position_timestamp=time.monotonic())
        browse_center=widget._center; widget.set_snapshot(snap)
        assert widget._center == browse_center
        widget.locate_rover(); assert widget._center == (13.62,123.19)
        widget.set_snapshot(replace(snap,gps_fix=1,latitude=0,longitude=0,position_timestamp=time.monotonic()+1))
        assert widget._last_position == (13.62,123.19)
    finally: widget.shutdown(); widget.close()


def test_map_controls_persist_and_leave_radio_state_unchanged(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    settings_file=tmp_path/'settings.json'
    monkeypatch.setattr(ui,'load_settings',lambda:AppSettings(map_online=False))
    monkeypatch.setattr(ui,'save_settings',lambda settings:save_settings(settings,settings_file))
    window=ui.MainWindow(start_services=False); window.show(); app.processEvents()
    try:
        original=window.mav.snapshot()
        window.map_minimize_btn.click(); app.processEvents()
        assert not window.map_panel.isVisible() and window.map_restore_btn.isVisible()
        assert window.map_restore_btn.x()==0 and window.map_restore_btn.y()>0
        assert load_settings(settings_file).map_minimized
        window.map_restore_btn.click(); app.processEvents()
        assert window.map_panel.isVisible() and not window.map_restore_btn.isVisible()
        assert window._load_offline_map(str(make_map(tmp_path/'map.mbtiles')))
        assert not window.map_online.isChecked()
        assert window._settings_from_widgets().map_file.endswith('map.mbtiles')
        assert window.mav.snapshot() == original
        assert load_settings(settings_file).map_file.endswith('map.mbtiles')
    finally: window.close(); app.processEvents()

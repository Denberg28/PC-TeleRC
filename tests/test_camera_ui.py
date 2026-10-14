import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")

from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import time

import pytest
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from pctelerc.camera import CameraView, MjpegBuffer, stored_camera_url, validate_camera_url
from pctelerc.config import AppSettings
from pctelerc.core import LinkState
from pctelerc.mavlink import MavlinkSnapshot
from pctelerc.rover_map import RoverMap, position_fresh, world_pixel
from pctelerc.self_test import run
import pctelerc.ui as ui


@pytest.fixture
def window(monkeypatch):
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(ui,"load_settings",lambda:AppSettings(map_online=False))
    monkeypatch.setattr(ui,"save_settings",lambda *a,**k:None)
    w=ui.MainWindow(start_services=False)
    w.show(); app.processEvents()
    yield w
    w.close(); app.processEvents()


def test_real_http_video_decodes_and_frozen_self_test_contract(tmp_path):
    report=tmp_path/'report.json'
    assert run(report) == 0, report.read_text()


def test_mjpeg_parser_split_headers_latest_frame_and_memory_limit():
    buffer=MjpegBuffer()
    assert buffer.feed(b'HTTP multipart headers\r\n\xff') is None
    assert buffer.feed(b'\xd8frame\xff') is None
    assert buffer.feed(b'\xd9--boundary\xff\xd8new\xff\xd9') == b'\xff\xd8new\xff\xd9'
    assert buffer.feed(b'\xff\xd8'+b'x'*(buffer.MAX_BYTES+1)) is None
    assert len(buffer.buffer) <= buffer.MAX_BYTES
    assert buffer.feed(b'junk'*10000) is None
    assert len(buffer.buffer) <= 1


@pytest.mark.parametrize('url',['file:///etc/passwd','javascript:alert(1)','http://','rtsp://camera:bad/stream','http://bad host/'])
def test_invalid_camera_urls_rejected(url):
    with pytest.raises(ValueError):
        validate_camera_url(url)


def test_camera_credentials_and_tokens_not_persisted():
    assert stored_camera_url('rtsp://user:secret@192.168.1.2:8554/live?token=secret#private') == 'rtsp://192.168.1.2:8554/live'
    assert stored_camera_url('https://[::1]:8080/live') == 'https://[::1]:8080/live'
    with pytest.raises(ValueError):
        validate_camera_url('rtsp://camera/live',mjpeg=True)


def test_camera_failure_and_stale_frame_do_not_touch_control(window, monkeypatch):
    window.mav._snapshot=MavlinkSnapshot(control_enabled=True,running=True)
    window.mav._control_enabled=True
    original=window.mav.snapshot()
    assert not window.camera_view.start('usb',device_id='missing')
    assert window.mav.snapshot() == original
    view=window.camera_view
    view._active=True; view._last_frame=time.monotonic()-2
    view._check_age()
    assert 'stale' in view._status.lower()
    assert window.mav.snapshot() == original
    view._accept_image(QImage(16,16,QImage.Format.Format_RGB32),view._generation-1)
    assert view._image.isNull()
    view._accept_image(QImage(16,16,QImage.Format.Format_RGB32),view._generation)
    assert view._status == 'Live camera'
    view.stop()
    assert window.mav.snapshot() == original


def test_actual_http_mjpeg_stream(window):
    image=QImage(64,48,QImage.Format.Format_RGB32);image.fill(0xff00aa)
    buf=QBuffer();buf.open(QIODevice.OpenModeFlag.WriteOnly);assert image.save(buf,'JPEG')
    jpeg=bytes(buf.data())
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            self.send_response(200);self.send_header('Content-Type','multipart/x-mixed-replace; boundary=frame');self.end_headers()
            try:
                for _ in range(30):
                    self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'+jpeg+b'\r\n');self.wfile.flush();time.sleep(.03)
            except (BrokenPipeError,ConnectionResetError):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        assert window.camera_view.start('mjpeg',url=f'http://127.0.0.1:{server.server_port}/stream')
        deadline=time.monotonic()+5
        while time.monotonic()<deadline and window.camera_view._last_frame is None:
            QApplication.processEvents();time.sleep(.01)
        assert not window.camera_view._image.isNull()
        assert not window.mav.snapshot().control_enabled
    finally:
        window.camera_view.stop();server.shutdown();server.server_close()


def test_percentage_changes_keep_manual_apply_and_disable_control(window):
    window.mav._snapshot=MavlinkSnapshot(control_enabled=True)
    window.mav._control_enabled=True
    window.steering_sensitivity.slider.setValue(35)
    assert window.steering_sensitivity.label.text() == '35%'
    assert not window.mav.snapshot().control_enabled
    assert window._settings_dirty
    assert window.settings.steering_sensitivity == 1
    window._apply_settings()
    assert window.settings.steering_sensitivity == .35
    assert not window.mav.snapshot().control_enabled
    assert window.deadzone.label.text() == '4%'
    assert window.expo.label.text() == '15%'
    window.deadzone.setValue(12)
    window.expo.setValue(40)
    assert window._settings_from_widgets().deadzone == .12
    assert window._settings_from_widgets().expo == .4


@pytest.mark.parametrize('width,height',[(1180,720),(900,580)])
def test_compact_camera_map_layout_with_drawer(window,width,height):
    window.resize(width,height);QApplication.processEvents()
    assert window.width() <= width
    assert not window.settings_panel.isVisible()
    assert window.camera_view.width() > window.map_panel.width()
    assert window.map_panel.x() == 0 and window.map_panel.y() > 0
    assert window.map_panel.geometry().bottom() <= window.camera_surface.height()
    window.settings_btn.setChecked(True);QApplication.processEvents()
    assert window.camera_view.width() >= 480
    assert window.camera_view.isVisible() and window.map_panel.isVisible()


def test_gps_freshness_and_projection_without_network(window):
    assert world_pixel(0,0,1) == (256,256)
    now=time.monotonic()
    snap=MavlinkSnapshot(state=LinkState.CONNECTED,gps_fix=3,latitude=13.62,longitude=123.19,position_timestamp=now)
    assert position_fresh(snap,now)
    assert not position_fresh(snap,now+5.1)
    assert not position_fresh(replace(snap,gps_fix=2),now)
    window.rover_map.set_snapshot(snap)
    assert window.rover_map._center == (13.62,123.19)
    assert len(window.rover_map._track) == 1
    window.rover_map.set_snapshot(replace(snap,gps_fix=1,latitude=0,longitude=0,position_timestamp=now+1))
    assert window.rover_map._center == (13.62,123.19)
    assert not window.rover_map._pending
    assert len(window.rover_map._track) == 1

"""UI-only checks for the FPV overlay, map loading and green application icon."""
import time
from dataclasses import replace

import pytest
from PySide6.QtCore import QBuffer, QIODevice, QPoint, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from pctelerc import ui
from pctelerc.config import AppSettings
from pctelerc.core import LinkState
from pctelerc.mavlink import MavlinkSnapshot
from pctelerc.rover_map import RoverMap


@pytest.fixture
def window(monkeypatch):
    monkeypatch.setattr(ui, "load_settings", lambda: AppSettings(map_online=False))
    monkeypatch.setattr(ui, "save_settings", lambda *_: None)
    window = ui.MainWindow(start_services=False)
    window.timer.stop()
    window.show()
    QApplication.processEvents()
    yield window
    window.close()


@pytest.mark.parametrize("size", [(1180, 720), (900, 580)])
def test_overlay_stays_in_primary_view_across_swap_and_minimize(window, size):
    window.resize(*size)
    QApplication.processEvents()
    before = window.mav.snapshot()
    for primary_map, minimized in [(False, False), (True, False), (False, True)]:
        surface = window.camera_surface
        surface.primary_map = primary_map
        surface.minimized = minimized
        surface.arrange()
        QApplication.processEvents()
        hud = window.telemetry_overlay
        assert hud.parent() is surface and hud.isVisible()
        assert surface.rect().contains(hud.geometry())
        assert surface.width() - hud.geometry().right() == 13
        assert hud.y() == 12
        assert hud.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        assert hud.focusPolicy() == Qt.FocusPolicy.NoFocus
        assert "background:transparent" in hud.styleSheet()
        assert surface.height() >= size[1] - 230
        assert not surface.map_panel.isVisible() if minimized else surface.map_panel.isVisible()
        assert window.map_restore_btn.text() == "Map"
    assert window.mav.snapshot() == before


def test_overlay_fresh_and_stale_readings_do_not_change_radio(window):
    now = time.monotonic()
    fresh = MavlinkSnapshot(state=LinkState.CONNECTED, running=True, gps_fix=3,
        latitude=13.62, longitude=123.19, position_timestamp=now, satellites=14,
        speed=2.4, voltage=11.8, battery_remaining=74, battery_timestamp=now,
        last_heartbeat=now, mode="MANUAL")
    window.mav._snapshot = fresh
    window._refresh()
    assert window.hud_values["speed"].text() == "2.4 m/s"
    assert window.hud_values["battery"].text() == "11.8 V · 74%"
    assert window.hud_values["gps"].text() == "3D · 14 sats"
    stale = replace(fresh, position_timestamp=now-6, battery_timestamp=now-6)
    window.mav._snapshot = stale
    window._refresh()
    assert window.hud_values["speed"].text() == "—"
    assert window.hud_values["battery"].text() == "—"
    assert window.hud_values["gps"].text() == "No fresh fix"
    assert window.mav.snapshot() == stale


def test_hud_click_reaches_camera_and_status_follows_camera_inset(window):
    surface = window.camera_surface
    hud = window.telemetry_overlay
    point = hud.mapTo(surface, QPoint(10, 10))
    assert surface.childAt(point) is window.camera_view
    QTest.mouseClick(window.camera_view, Qt.MouseButton.LeftButton,
                     pos=window.camera_view.mapFrom(surface, point))
    assert QApplication.focusWidget() is window.camera_view
    surface.primary_map = True
    surface.arrange()
    assert window.camera_status.y() == window.camera_view.y() + 12


@pytest.mark.parametrize("size", [(1180, 720), (900, 580)])
def test_selector_names_and_balanced_spacing(window, size):
    window.resize(*size)
    QApplication.processEvents()
    assert window.width() == size[0]
    assert window.link_mode.itemText(window.link_mode.findData("telerc_udp")) == "WIFI"
    assert window.link_mode.itemText(window.link_mode.findData("lora_usb")) == "LORA"
    assert [window.input_source.itemText(i) for i in range(window.input_source.count())] == ["Steering Wheel", "Keyboard"]
    assert window.link_mode.width() == window.input_source.width() == 168
    assert window.link_mode.mapTo(window, QPoint()).y() == window.input_source.mapTo(window, QPoint()).y()
    assert window.link_mode.height() == window.input_source.height() == 32
    buttons = (window.quick_connect_btn, window.quick_disconnect_btn, window.mission_btn, window.swap_view_btn)
    assert len({(b.width(), b.height()) for b in buttons}) == 1
    groups = [widget.parentWidget() for widget in
              (window.steering_sensitivity, window.throttle_sensitivity, window.throttle_limit)]
    assert max(g.width() for g in groups) - min(g.width() for g in groups) <= 1
    assert len({g.y() for g in groups}) == 1


def test_map_starts_loading_without_inventing_a_rover_fix(tmp_path, monkeypatch):
    widget = RoverMap(cache_dir=tmp_path / "cache")
    requests = []
    # Keep the existing four-request bound while recording the initial load order.
    def request(key, path):
        requests.append(key)
        widget._failed[key] = time.monotonic() + 30
    monkeypatch.setattr(widget, "_request_tile", request)
    try:
        widget.resize(600, 400)
        widget.show()
        QApplication.processEvents()
        assert requests and widget._center == RoverMap.DEFAULT_CENTER
        assert widget._last_position is None and widget._home is None
        assert not widget._track and widget._snapshot is None
        from pctelerc.rover_map import world_pixel
        cx, cy = world_pixel(*widget._center, widget._zoom)
        distances = [(x*256+128-cx)**2 + (y*256+128-cy)**2 for _, x, y in requests]
        assert distances == sorted(distances)
    finally:
        widget.shutdown()
        widget.close()


def test_zoom_keeps_cached_coverage_visible_while_detail_loads(tmp_path):
    widget = RoverMap(cache_dir=tmp_path / "cache")
    widget.set_online(False)
    try:
        image = QImage(256, 256, QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.green)
        widget._remember((16, 10, 20), image)
        tile = widget._fallback_tile((17, 21, 41))
        assert tile.size() == image.size()
        assert tile.pixelColor(128, 128) == image.pixelColor(128, 128)
        assert widget._last_position is None and not widget._pending
    finally:
        widget.shutdown()


def test_http_map_load_finishes_and_keeps_conditional_cache_metadata(tmp_path, monkeypatch):
    """Exercise the actual Qt reply/header API, with no external map requests."""
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    image = QImage(256, 256, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.darkGreen)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    body = bytes(buffer.data())
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("ETag", '"map-ui"')
            self.end_headers()
            self.wfile.write(body)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(RoverMap, "TILE_URL", f"http://127.0.0.1:{server.server_port}/{{z}}/{{x}}/{{y}}.png")
    widget = RoverMap(cache_dir=tmp_path / "cache")
    widget.resize(600, 400)
    try:
        widget.show()
        deadline = time.monotonic() + 5
        maximum_pending = 0
        while time.monotonic() < deadline:
            QApplication.processEvents()
            maximum_pending = max(maximum_pending, len(widget._pending))
            if len(widget._tiles) >= 6 and not widget._pending:
                break
            time.sleep(.005)
        assert len(widget._tiles) >= 6 and not widget._pending and not widget._failed
        rendered = widget.grab().toImage()
        for x in (30, 200, 400, 570):
            for y in (60, 180, 320):
                assert rendered.pixelColor(x, y) == image.pixelColor(0, 0)
        assert maximum_pending <= 4
        metadata = list((tmp_path / "cache").glob("*.json"))
        assert metadata and json.loads(metadata[0].read_text())["ETag"] == '"map-ui"'
        assert widget._last_position is None and not widget._track
    finally:
        widget.shutdown()
        widget.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def test_application_and_header_use_green_power_icon(window):
    from pathlib import Path
    assets = Path(ui.__file__).parent / "assets"
    assert not window.windowIcon().isNull()
    assert not window.brand_logo.pixmap().isNull()
    for name in ("telerc.png", "telerc.ico"):
        image = QImage(str(assets / name))
        assert not image.isNull()
        greens = sum(color.green() > color.red()*1.5 and color.green() > color.blue()*1.5
                     for color in (image.pixelColor(x, y) for x in range(image.width()) for y in range(image.height())))
        assert greens > image.width() * image.height() * .02

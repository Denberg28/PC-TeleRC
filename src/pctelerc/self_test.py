"""Frozen-package UI/media verification: no wheel or radio services start."""
from __future__ import annotations

from contextlib import closing

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import sqlite3
import tempfile
import time

from PySide6.QtWidgets import QApplication


def run(report_path):
    from . import ui
    from .config import AppSettings
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(ui.STYLE)
    saved_load, saved_save, saved_map, saved_mission = ui.load_settings, ui.save_settings, ui.RoverMap, ui.MissionDialog
    map_cache = tempfile.TemporaryDirectory()
    ui.RoverMap = partial(saved_map, cache_dir=Path(map_cache.name) / "cache")
    ui.MissionDialog = partial(saved_mission, draft_path=Path(map_cache.name)/"mission-draft.json")
    ui.load_settings = lambda: AppSettings(map_online=False)
    ui.save_settings = lambda *_args, **_kwargs: None
    window = ui.MainWindow(start_services=False)
    server = None
    checks = {}
    try:
        window.show()
        app.processEvents()
        checks["camera_layout"] = window.camera_view.width() > window.map_panel.width()
        checks["lower_left_map"] = window.map_panel.x() == 0 and window.map_panel.y() > 0
        checks["logo"] = not window.windowIcon().isNull() and not window.brand_logo.pixmap().isNull()
        from PySide6.QtCore import Qt
        checks["fpv_overlay"] = (window.telemetry_overlay.parent() is window.camera_surface
            and window.telemetry_overlay.isVisible()
            and window.telemetry_overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents))
        checks["connection_control_labels"] = (window.link_mode.itemText(0) == "WIFI"
            and window.link_mode.itemText(1) == "LORA"
            and window.input_source.itemText(0) == "Steering Wheel"
            and window.input_source.itemText(1) == "Keyboard")
        checks["balanced_selectors"] = window.link_mode.size() == window.input_source.size()
        checks["control_disabled"] = not window.mav.snapshot().control_enabled and not window.mav.snapshot().running
        checks["sliders"] = window.steering_sensitivity.label.text() == "100%" and window.throttle_limit.label.text() == "25%"
        window.map_minimize_btn.click(); app.processEvents()
        checks["map_minimize"] = not window.map_panel.isVisible() and window.map_restore_btn.isVisible()
        checks["map_restore_anchor"] = window.map_restore_btn.x() == 0 and window.map_restore_btn.y() > 0
        window.map_restore_btn.click(); app.processEvents()
        checks["map_restore"] = window.map_panel.isVisible() and not window.map_restore_btn.isVisible()
        generation = window.camera_view._generation
        window._swap_views()
        from PySide6.QtTest import QTest
        QTest.qWait(200)
        checks["map_swap"] = window.map_panel.width() == window.camera_surface.width()
        window._set_map_minimized(True)
        window._set_map_minimized(False)
        checks["swap_no_media_restart"] = window.camera_view._generation == generation
        window.link_mode.setCurrentIndex(window.link_mode.findData("elrs_backpack"))
        from dataclasses import replace
        window._connected_settings = replace(window.settings, link_mode="elrs_backpack")
        window._refresh()
        checks["backpack_commands_locked"] = all(not b.isEnabled() for b in
            (window.arm_btn, window.disarm_btn, window.control_btn))
        from PySide6.QtCore import QBuffer, QIODevice
        from PySide6.QtGui import QImage
        tile = QImage(256,256,QImage.Format.Format_RGB32); tile.fill(0xff2468ac)
        encoded = QBuffer(); encoded.open(QIODevice.OpenModeFlag.WriteOnly); tile.save(encoded,'PNG')
        with tempfile.TemporaryDirectory() as folder:
            offline = Path(folder) / 'self-test.mbtiles'
            with closing(sqlite3.connect(offline)) as db, db:
                db.execute('CREATE TABLE metadata (name TEXT, value TEXT)')
                db.executemany('INSERT INTO metadata VALUES (?,?)',[('format','png'),('center','0,0,1'),('name','Diagnostic tiles')])
                db.execute('CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB)')
                db.execute('INSERT INTO tiles VALUES (1,1,0,?)',(bytes(encoded.data()),))
            checks["offline_map_load"] = window._load_offline_map(str(offline), persist=False)
            image = window.rover_map._tile((1,1,1))
            checks["offline_tile_decode"] = image is not None and image.pixelColor(0,0).name() == '#2468ac'
            checks["offline_no_network"] = not window.rover_map._online and not window.rover_map._pending
            checks["offline_no_fake_gps"] = window.rover_map._last_position is None and not window.rover_map._track
            window._load_offline_map('', persist=False)
        window._open_mission()
        mission = window._mission_dialog
        mission.map.set_online(False)
        mission._add(13.6, 123.2)
        mission._add(13.6001, 123.2001)
        from .mission_plan import parse_text
        checks["mission_plan_codec"] = len(parse_text(mission._text())) == 6
        checks["mission_planning_no_authority"] = (not mission.service.running and
            not mission.start_btn.isEnabled() and not window.mav.snapshot().running)
        from .firmware_profiles import mission_capabilities
        caps, profile = mission_capabilities(b"TM2;fw=0.2.0;relays=2;mask=0;unified=0.4.0")
        mission._capabilities(dict(caps, profile=profile))
        checks["firmware_baseline_identity"] = "Scalable LoRa 0.4.0" in mission.firmware_label.text() and not mission.start_btn.isEnabled()
        mission.reject(); app.processEvents()
        checks["mission_close_cleans_session"] = window._mission_dialog is None and not mission.timer.isActive()
        fixture = Path(__file__).parent / "assets" / "test-pattern.mp4"
        if not fixture.exists():
            fixture = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "test-pattern.mp4"
        checks["video_fixture"] = fixture.is_file()
        class Handler(SimpleHTTPRequestHandler):
            def log_message(self, *_args):
                pass
        server = ThreadingHTTPServer(("127.0.0.1",0), partial(Handler,directory=str(fixture.parent)))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        checks["camera_start"] = window.camera_view.start("network",url=f"http://127.0.0.1:{server.server_port}/{fixture.name}")
        deadline = time.monotonic()+15
        while time.monotonic() < deadline and window.camera_view._last_frame is None:
            app.processEvents()
            time.sleep(.01)
        checks["actual_video_decode"] = window.camera_view._last_frame is not None and not window.camera_view._image.isNull()
        checks["media_no_control_side_effect"] = not window.mav.snapshot().control_enabled and not window.mav.snapshot().running
        window.camera_view.stop()
        checks["camera_stop"] = not window.camera_view._active and window.camera_view._image.isNull()
    except Exception as exc:
        checks["error"] = type(exc).__name__
    finally:
        window.close()
        app.processEvents()
        if server is not None:
            server.shutdown(); server.server_close()
        ui.load_settings, ui.save_settings, ui.RoverMap, ui.MissionDialog = saved_load, saved_save, saved_map, saved_mission
        map_cache.cleanup()
    from . import __version__
    result = {"version": __version__, "passed":bool(checks) and all(value is True for value in checks.values()),"checks":checks}
    Path(report_path).write_text(json.dumps(result,indent=2),encoding="utf-8")
    return 0 if result["passed"] else 1



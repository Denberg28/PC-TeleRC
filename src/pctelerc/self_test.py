"""Frozen-package UI/media verification: no wheel or radio services start."""
from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time

from PySide6.QtWidgets import QApplication


def run(report_path):
    from . import ui
    from .config import AppSettings
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(ui.STYLE)
    saved_load, saved_save = ui.load_settings, ui.save_settings
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
        checks["control_disabled"] = not window.mav.snapshot().control_enabled and not window.mav.snapshot().running
        checks["sliders"] = window.steering_sensitivity.label.text() == "100%" and window.throttle_limit.label.text() == "25%"
        fixture = Path(__file__).parent / "assets" / "test-pattern.mp4"
        if not fixture.exists():
            fixture = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "test-pattern.mp4"
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
        ui.load_settings, ui.save_settings = saved_load, saved_save
    result = {"passed":bool(checks) and all(value is True for value in checks.values()),"checks":checks}
    Path(report_path).write_text(json.dumps(result,indent=2),encoding="utf-8")
    return 0 if result["passed"] else 1

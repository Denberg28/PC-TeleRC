import time
from dataclasses import replace

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from pctelerc.camera import CameraView
from pctelerc.config import AppSettings, load_settings, save_settings
from pctelerc.core import LinkState
from pctelerc.mavlink import MavlinkService, MavlinkSnapshot
from test_display_telemetry import message
from test_camera_ui import window


def test_swap_and_collapse_preserve_media_session_and_control(window):
    view = window.camera_view
    generation = view._generation
    snap = MavlinkSnapshot(running=True, control_enabled=True)
    window.mav._snapshot = snap
    window.mav._control_enabled = True
    window._swap_views()
    QTest.qWait(200)
    assert window.map_panel.width() == window.camera_surface.width()
    assert view.width() < window.map_panel.width()
    assert view._generation == generation and window.mav.snapshot() == snap
    window._set_map_minimized(True)
    assert not window.map_panel.isVisible() and window.map_restore_btn.isVisible()
    assert view.width() == window.camera_surface.width()
    window._set_map_minimized(False)
    assert window.map_panel.isVisible() and not window.settings.map_primary
    assert window.mav.snapshot() == snap


def test_backpack_ui_locks_commands_and_hides_unused_serial_fields(window):
    window.settings_btn.setChecked(True)
    window.link_mode.setCurrentIndex(window.link_mode.findData('elrs_backpack'))
    assert window.backpack_host.isVisible()
    assert not window.elrs_port.isVisible() and not window.lora_port.isVisible()
    assert window._settings_from_widgets().backpack_target_port == 14555
    window._connected_settings = AppSettings(link_mode='elrs_backpack')
    window.mav._snapshot = MavlinkSnapshot(running=True, state=LinkState.CONNECTED, armed=True)
    window._refresh()
    assert all(not b.isEnabled() for b in (window.arm_btn, window.disarm_btn, window.control_btn))
    assert 'HANDSET' in window.authority_label.text().upper()


def test_camera_retry_keeps_identity_backs_off_and_stop_cancels(qt_application):
    view = CameraView()
    try:
        assert not view.start('usb', device_id='missing-exact-device')
        source = view._requested_source
        assert source == ('usb', 'missing-exact-device', '')
        for _ in range(4):
            view._retry_at = time.monotonic() - .01
            view._check_age()
            assert view._requested_source == source and view._retry_at is not None
        assert view._retry_delay == 8
        old_token = view._generation
        view.stop()
        view._error(old_token)
        view._check_age()
        assert view._retry_at is None and view._requested_source is None
        assert not view._active
    finally:
        view.shutdown(); view.deleteLater()


def test_stale_fix_cannot_be_renewed_by_global_position():
    service = MavlinkService()
    service._snapshot = MavlinkSnapshot(vehicle_system=1, vehicle_component=1)
    service._handle_message(message('GPS_RAW_INT', fix_type=3, lat=136200000, lon=1231900000), 100)
    service._handle_message(message('GLOBAL_POSITION_INT', lat=136200100, lon=1231900100, vx=300, vy=400, hdg=0), 106)
    assert service.snapshot().position_timestamp == 100
    assert service.snapshot().gps_timestamp == 100


def test_new_preferences_roundtrip_without_changing_radio_defaults(tmp_path):
    settings = AppSettings(map_primary=True, camera_auto_reconnect=False, link_mode='elrs_backpack', backpack_host='10.0.0.9')
    path = tmp_path/'settings.json'
    save_settings(settings, path)
    assert load_settings(path) == settings
    assert AppSettings().target_port == 14550

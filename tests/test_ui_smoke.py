import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import pctelerc.ui as ui
from pctelerc.config import AppSettings


def test_main_window_constructs_with_symmetric_columns_and_modeless_diagnostics(monkeypatch):
    app = QApplication.instance() or QApplication([])

    monkeypatch.setattr(ui, "load_settings", lambda: AppSettings())
    monkeypatch.setattr(ui, "save_settings", lambda *args, **kwargs: None)
    monkeypatch.setattr(ui.WheelService, "start", lambda self: None)
    monkeypatch.setattr(ui.WheelService, "stop", lambda self: None)
    monkeypatch.setattr(ui.MavlinkService, "start", lambda self: None)
    monkeypatch.setattr(ui.MavlinkService, "stop", lambda self: None)

    window = ui.MainWindow()
    try:
        assert [window.main_grid.columnStretch(i) for i in range(3)] == [1, 1, 1]
        assert all(window.main_grid.columnMinimumWidth(i) == 330 for i in range(3))

        window._open_diagnostics()
        app.processEvents()
        assert window._diagnostics_window is not None
        assert not window._diagnostics_window.isModal()
        assert window._diagnostics_window.isVisible()
    finally:
        if window._diagnostics_window is not None:
            window._diagnostics_window.close()
        window.close()
        app.processEvents()


def test_sensitivity_slider_requires_apply_and_preserves_drive_settings(monkeypatch):
    from dataclasses import replace
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QSlider

    app = QApplication.instance() or QApplication([])
    saved = []
    monkeypatch.setattr(ui, "load_settings", lambda: AppSettings(steering_sensitivity=.75))
    monkeypatch.setattr(ui, "save_settings", lambda settings: saved.append(replace(settings)))
    for service in (ui.WheelService, ui.MavlinkService):
        monkeypatch.setattr(service, "start", lambda self: None)
        monkeypatch.setattr(service, "stop", lambda self: None)

    window = ui.MainWindow()
    try:
        assert isinstance(window.steering_sensitivity, QSlider)
        assert window.steering_sensitivity.orientation() == Qt.Orientation.Horizontal
        assert window.steering_sensitivity.minimum() == 25
        assert window.steering_sensitivity.maximum() == 100
        assert window.steering_sensitivity.value() == 75
        assert window.sensitivity_label.text() == "Steering sensitivity: 75%"
        snapshot = replace(window.mav.snapshot(), control_enabled=True)
        monkeypatch.setattr(window.mav, "snapshot", lambda: snapshot)
        disabled = []
        monkeypatch.setattr(window.mav, "disable_control", lambda: disabled.append(True))
        window.steering_sensitivity.setValue(50)
        assert disabled
        assert window._settings_dirty
        assert window.settings.steering_sensitivity == .75
        assert window.sensitivity_label.text() == "Steering sensitivity: 50%"
        window._apply_settings()
        assert saved[-1].steering_sensitivity == .5
        assert saved[-1].throttle_limit == .25
        assert saved[-1].throttle_channel == 2
        assert not window._settings_dirty
    finally:
        window.close()
        app.processEvents()


def review_window(monkeypatch):
    monkeypatch.setattr(ui, 'load_settings', lambda: AppSettings())
    monkeypatch.setattr(ui, 'save_settings', lambda *args: None)
    for service in (ui.WheelService, ui.MavlinkService):
        monkeypatch.setattr(service, 'start', lambda self: True)
        monkeypatch.setattr(service, 'stop', lambda self: True)
    return ui.MainWindow()


def test_network_pending_blocks_arm_and_control_until_reconnect(monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = review_window(monkeypatch)
    try:
        window.target_host.setText('192.168.4.1')
        assert window._apply_settings()
        assert window._network_dirty
        assert window.mav._settings.target_host == ''  # pending target never changes live route
        called = []
        monkeypatch.setattr(window.mav, 'enable_control', lambda: (called.append(True), 'enabled'))
        window._toggle_control()
        window._vehicle_command(lambda: (called.append(True), 'armed'))
        assert called == []
        window._apply_and_reconnect()
        assert window.mav._settings.target_host == '192.168.4.1'
        assert not window._network_dirty
    finally:
        window.close()
        app.processEvents()


def test_failed_settings_save_keeps_pending_state_and_existing_configuration(monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = review_window(monkeypatch)
    try:
        window.steering_sensitivity.setValue(50)
        def fail(*args):
            raise OSError('disk full')
        monkeypatch.setattr(ui, 'save_settings', fail)
        assert not window._apply_settings()
        assert window._settings_dirty
        assert window.settings.steering_sensitivity == 1
        assert 'disk full' in window.message.text()
    finally:
        window.close()
        app.processEvents()


def test_disconnect_stops_transport_without_arming_or_enabling(monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = review_window(monkeypatch)
    try:
        stopped = []
        monkeypatch.setattr(window.mav, 'stop', lambda: (stopped.append(True) or True))
        monkeypatch.setattr(window.mav, 'arm', lambda: (_ for _ in ()).throw(AssertionError('auto arm')))
        monkeypatch.setattr(window.mav, 'enable_control', lambda: (_ for _ in ()).throw(AssertionError('auto enable')))
        window.disconnect_btn.click()
        assert stopped == [True]
        window._refresh()
        assert 'Disconnected' in window.link_label.text()
        assert not window.arm_btn.isEnabled() and not window.control_btn.isEnabled()
    finally:
        window.close()
        app.processEvents()


def test_independent_drive_and_steering_sliders_save_and_elrs_route_stays_pending(monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = review_window(monkeypatch)
    try:
        window.steering_sensitivity.setValue(75)
        window.drive_sensitivity.setValue(40)
        assert window._apply_settings()
        assert window.settings.steering_sensitivity == .75
        assert window.settings.drive_sensitivity == .4
        assert window.settings.throttle_limit == .25
        assert window.drive_sensitivity_label.text() == 'Drive sensitivity: 40%'
        window.link_mode.setCurrentIndex(window.link_mode.findData('elrs_serial'))
        window.serial_port.setText('COM5')
        assert window._apply_settings()
        assert window._network_dirty
        assert window.mav._settings.link_mode == 'telerc_udp'
        window._apply_and_reconnect()
        assert window.mav._settings.link_mode == 'elrs_serial'
        assert window.mav._settings.serial_port == 'COM5'
    finally:
        window.close()
        app.processEvents()

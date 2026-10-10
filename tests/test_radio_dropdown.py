import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from pymavlink.dialects.v10 import ardupilotmega as mavlink1

import pctelerc.ui as ui
from pctelerc.config import AppSettings, load_settings, save_settings
from pctelerc.core import ControlFrame, LinkState
from pctelerc.mavlink import MavlinkService, MavlinkSnapshot
from test_elrs_serial import FakeSerial, wait_until
from test_lora import LoRaSerial, ACTIVE


@pytest.fixture
def window(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(ui, "load_settings", lambda: AppSettings())
    monkeypatch.setattr(ui, "save_settings", lambda *args, **kwargs: None)
    monkeypatch.setattr(ui.WheelService, "start", lambda self: None)
    monkeypatch.setattr(ui.WheelService, "stop", lambda self: None)
    monkeypatch.setattr(ui.MavlinkService, "start", lambda self: True)
    monkeypatch.setattr(ui.MavlinkService, "stop", lambda self: True)
    result = ui.MainWindow()
    result.timer.stop()
    result.show()
    app.processEvents()
    yield result
    result.close()
    app.processEvents()


def test_dropdown_shows_only_selected_radio_fields_and_retains_ports(window):
    assert window.link_mode.count() == 3
    assert window.bind_host.isVisible()
    assert not window.lora_port.isVisible()
    window.link_mode.setCurrentIndex(1)
    assert not window.bind_host.isVisible()
    assert window.lora_port.isVisible() and window.lora_setup_btn.isVisible()
    window.lora_port.setCurrentText("COM7")
    window.link_mode.setCurrentIndex(2)
    assert window.elrs_port.isVisible() and not window.lora_setup_btn.isVisible()
    window.elrs_port.setCurrentText("COM5")
    window.link_mode.setCurrentIndex(1)
    assert window.lora_port.currentText() == "COM7"
    settings = window._settings_from_widgets()
    assert settings.lora_port == "COM7" and settings.elrs_port == "COM5"


def test_radio_edit_disables_control_but_apply_does_not_redirect_live_link(window):
    window.mav._snapshot = MavlinkSnapshot(control_enabled=True)
    window.mav._control_enabled = True
    window.link_mode.setCurrentIndex(1)
    window.lora_port.setCurrentText("COM7")
    assert not window.mav.snapshot().control_enabled
    window._apply_settings()
    assert window.settings.link_mode == "lora_usb"
    assert window.mav._settings.link_mode == "telerc_udp"
    assert window._network_dirty
    window._refresh()
    assert not window.control_btn.isEnabled()


def test_reconnect_closes_old_profile_before_configuring_new_and_disconnect_cancels_timer(window, monkeypatch):
    calls = []
    monkeypatch.setattr(window.mav, "stop", lambda: calls.append(("stop", window.mav._settings.link_mode)) or True)
    monkeypatch.setattr(window.mav, "start", lambda: calls.append(("start", window.mav._settings.link_mode)) or True)
    scheduled = []
    monkeypatch.setattr(QTimer, "singleShot", lambda delay, callback: scheduled.append(callback))
    window.link_mode.setCurrentIndex(1)
    window.lora_port.setCurrentText("COM7")
    window._apply_and_reconnect()
    assert calls == [("stop", "telerc_udp")]
    assert window.mav._settings.link_mode == "lora_usb"
    window._disconnect_link()
    scheduled[0]()
    assert all(action != "start" for action, _ in calls)
    window._apply_and_reconnect()
    scheduled[-1]()
    assert calls[-1] == ("start", "lora_usb")
    assert not window.mav.snapshot().control_enabled


def test_old_settings_default_to_wifi_and_radio_ports_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"settings_version":2,"steering_channel":1,"throttle_channel":2}')
    assert load_settings(path).link_mode == "telerc_udp"
    settings = AppSettings(link_mode="lora_usb", lora_port="COM7", elrs_port="COM5")
    save_settings(settings, path)
    assert load_settings(path) == settings
    assert AppSettings(link_mode="unknown").validate().link_mode == "telerc_udp"


def test_elrs_usb_removal_stops_worker_and_requires_manual_reconnect(monkeypatch):
    import serial
    ports = []
    def factory(**kwargs):
        port = FakeSerial(**kwargs)
        ports.append(port)
        return port
    monkeypatch.setattr(serial, "Serial", factory)
    service = MavlinkService()
    service.configure(AppSettings(link_mode="elrs_serial", elrs_port="COM5"))
    service.start()
    try:
        assert wait_until(lambda: service.snapshot().running)
        encoder = mavlink1.MAVLink(None, srcSystem=42, srcComponent=1)
        ports[0].rx.extend(encoder.heartbeat_encode(10, 3, 0, 0, 4).pack(encoder))
        assert wait_until(lambda: service.snapshot().state == LinkState.CONNECTED)
        service.set_control_frame(ControlFrame(0, 0, time.monotonic()), 3)
        assert service.enable_control()[0]
        ports[0].is_open = False
        assert wait_until(lambda: not service.snapshot().running)
        assert not service.snapshot().control_enabled
        assert len(ports) == 1
    finally:
        service.stop()


def test_sx1276_base_is_rejected_and_open_port_is_closed(monkeypatch):
    import serial
    ports = []
    def factory(**kwargs):
        port = LoRaSerial(**kwargs)
        port.board_reply = ACTIVE.replace(b"1262", b"1276")
        ports.append(port)
        return port
    monkeypatch.setattr(serial, "Serial", factory)
    service = MavlinkService()
    service.configure(AppSettings(link_mode="lora_usb", lora_port="COM7"))
    service.start()
    try:
        assert wait_until(lambda: "SX1262" in service.snapshot().error)
        assert wait_until(lambda: not ports[0].is_open)
        assert not service.snapshot().control_enabled
    finally:
        service.stop()


def test_lora_initial_failsafe_only_sends_neutral_and_later_failsafe_latches_off():
    service = MavlinkService()
    service.configure(AppSettings(link_mode="lora_usb"))
    encoder = mavlink1.MAVLink(None, srcSystem=1, srcComponent=1)
    def heartbeat(mode):
        service._handle_message(mavlink1.MAVLink(None).parse_char(encoder.heartbeat_encode(10, 0, 0, mode, 4).pack(encoder)), time.monotonic())
    heartbeat(0)
    service.set_control_frame(ControlFrame(.04, 0, time.monotonic()), 3)
    assert service.enable_control()[0]
    sent = []
    service._send_override = lambda steer, drive: sent.append((steer, drive)) or True
    service._control_tick(time.monotonic())
    assert sent == [(1500, 1500)]
    heartbeat(1)
    service.set_control_frame(ControlFrame(.4, .8, time.monotonic()), 3)
    service._control_tick(time.monotonic())
    assert sent[-1] == (1700, 1600)
    heartbeat(0)
    service._control_tick(time.monotonic())
    assert not service.snapshot().control_enabled
    assert service.snapshot().failsafe_latched


def test_lora_autopilot_heartbeat_cannot_claim_direct_mode():
    service = MavlinkService()
    service.configure(AppSettings(link_mode="lora_usb"))
    encoder = mavlink1.MAVLink(None, srcSystem=1, srcComponent=1)
    service._handle_message(mavlink1.MAVLink(None).parse_char(encoder.heartbeat_encode(10, 3, 0, 1, 4).pack(encoder)), time.monotonic())
    service.set_control_frame(ControlFrame(0, 0, time.monotonic()), 3)
    assert not service.enable_control()[0]

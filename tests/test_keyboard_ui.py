import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from dataclasses import replace

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import pctelerc.ui as ui
from pctelerc.config import AppSettings
from pctelerc.core import LinkState
from pctelerc.mavlink import MavlinkSnapshot


@pytest.fixture
def window(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(ui, "load_settings", lambda: AppSettings(input_source="keyboard"))
    monkeypatch.setattr(ui, "save_settings", lambda *a, **k: None)
    for service in (ui.WheelService, ui.MavlinkService):
        monkeypatch.setattr(service, "start", lambda self: None)
        monkeypatch.setattr(service, "stop", lambda self: None)
    win = ui.MainWindow()
    win.show()
    win.activateWindow()
    win.keyboard_pad.setFocus()
    app.processEvents()
    win._sample_keyboard()
    assert win.keyboard.snapshot().connected
    yield win
    win.close()
    app.processEvents()


def ready(win, monkeypatch):
    win.mav._snapshot = MavlinkSnapshot(running=True, state=LinkState.CONNECTED,
                                      vehicle_system=1, vehicle_component=1)
    monkeypatch.setattr(win.mav, "_send_neutral_then_release", lambda: True)
    win._refresh()
    QTest.mouseClick(win.control_btn, Qt.MouseButton.LeftButton)
    assert win.mav.snapshot().control_enabled


def test_arrows_wasd_space_and_no_button_activation(window, monkeypatch):
    ready(window, monkeypatch)
    QTest.keyPress(window.keyboard_pad, Qt.Key.Key_Up)
    QTest.keyPress(window.keyboard_pad, Qt.Key.Key_A)
    assert (window.keyboard.snapshot().steering, window.keyboard.snapshot().throttle) == (-1, 1)
    QTest.keyPress(window.keyboard_pad, Qt.Key.Key_Space)
    assert window.keyboard.snapshot().throttle == 0
    assert window.mav.snapshot().control_enabled
    QTest.keyRelease(window.keyboard_pad, Qt.Key.Key_Space)
    assert window.keyboard.snapshot().throttle == 0
    QTest.keyRelease(window.keyboard_pad, Qt.Key.Key_Up)
    QTest.keyRelease(window.keyboard_pad, Qt.Key.Key_A)
    QTest.keyPress(window.keyboard_pad, Qt.Key.Key_W)
    assert window.keyboard.snapshot().throttle == 1
    window._refresh()
    QTest.mouseClick(window.control_btn, Qt.MouseButton.LeftButton)
    assert not window.mav.snapshot().control_enabled


@pytest.mark.parametrize("key,expected", [
    (Qt.Key.Key_W, (0, 1)), (Qt.Key.Key_Up, (0, 1)),
    (Qt.Key.Key_S, (0, -1)), (Qt.Key.Key_Down, (0, -1)),
    (Qt.Key.Key_A, (-1, 0)), (Qt.Key.Key_Left, (-1, 0)),
    (Qt.Key.Key_D, (1, 0)), (Qt.Key.Key_Right, (1, 0)),
])
def test_keyboard_choice_supports_each_wasd_and_arrow_direction(window, key, expected):
    assert window.input_source.currentText() == "Keyboard"
    QTest.keyPress(window.camera_view, key)
    snapshot = window.keyboard.snapshot()
    assert (snapshot.steering, snapshot.throttle) == expected
    QTest.keyRelease(window.camera_view, key)
    snapshot = window.keyboard.snapshot()
    assert (snapshot.steering, snapshot.throttle) == (0, 0)
    assert not window.mav.snapshot().control_enabled


@pytest.mark.parametrize("event_type", [QEvent.Type.WindowDeactivate, QEvent.Type.FocusOut])
def test_focus_loss_disables_and_never_auto_enables(window, monkeypatch, event_type):
    ready(window, monkeypatch)
    QTest.keyPress(window.keyboard_pad, Qt.Key.Key_W)
    watched = window if event_type == QEvent.Type.WindowDeactivate else window.keyboard_pad
    QApplication.sendEvent(watched, QEvent(event_type))
    assert not window.mav.snapshot().control_enabled
    assert window.keyboard.snapshot().frame is None
    window._sample_keyboard()
    assert not window.mav.snapshot().control_enabled
    assert window.keyboard.snapshot().throttle == 0


def test_editable_fields_do_not_drive_and_stop_existing_control(window, monkeypatch):
    ready(window, monkeypatch)
    QTest.keyPress(window.keyboard_pad, Qt.Key.Key_W)
    window.target_host.setFocus()
    QApplication.processEvents()
    assert not window.mav.snapshot().control_enabled
    QTest.keyClicks(window.target_host, "wasd")
    assert window.target_host.text().endswith("wasd")
    assert window.keyboard.snapshot().frame is None


def test_repeated_space_and_w_do_not_resume_drive(window):
    QTest.keyPress(window.keyboard_pad, Qt.Key.Key_W)
    QTest.keyPress(window.keyboard_pad, Qt.Key.Key_Space)
    for kind, key in [(QEvent.Type.KeyRelease, Qt.Key.Key_Space),
                      (QEvent.Type.KeyPress, Qt.Key.Key_W)]:
        QApplication.sendEvent(window.keyboard_pad, QKeyEvent(kind, key,
            Qt.KeyboardModifier.NoModifier, "", True))
    assert window.keyboard.snapshot().throttle == 0


def test_source_edit_disables_and_keyboard_requires_no_joystick(window, monkeypatch):
    ready(window, monkeypatch)
    assert not window.wheel.snapshot().connected
    window.input_source.setCurrentIndex(window.input_source.findData("wheel"))
    assert not window.mav.snapshot().control_enabled
    assert window._settings_dirty

import copy
import threading
import time
from types import SimpleNamespace

import pytest
from pymavlink.dialects.v20 import common as mav
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest

from pctelerc.mission_plan import Plan, Point, Function, parse_text
from pctelerc.mission_protocol.client import Client, compare, fingerprint
from pctelerc.mission_protocol.usb_gateway import Decoder, encode
from pctelerc.mission_service import MissionService, Cancelled
from pctelerc.mission_transport import MissionUSB
from pctelerc.mission_widget import MissionDialog


def route():
    return Plan([Point(13.6, 123.2), Point(13.6001, 123.2001)])


def test_wpl_ordered_points_speed_and_roundtrip():
    p = route()
    items = parse_text(p.wpl())
    assert [x["command"] for x in items] == [16, 112, 178, 93, 16, 16]
    assert items[2]["params"] == [1, 0.5, -1, 0]
    assert items[4]["x"] == 136000000
    compare(items, copy.deepcopy(items))
    changed = copy.deepcopy(items)
    changed[2]["y"] += 1
    with pytest.raises(RuntimeError):
        compare(items, changed)
    assert fingerprint(items, 1) != fingerprint(items, 2)


def test_function_events_are_ordered_and_balanced():
    p = route()
    p.functions[0] = Function(9)
    p.points[0].actions = [(0, True)]
    with pytest.raises(ValueError, match="final OFF"):
        p.wpl()
    p.points[1].actions = [(0, False)]
    items = parse_text(p.wpl())
    assert [x["command"] for x in items] == [
        16,
        112,
        178,
        183,
        93,
        16,
        112,
        183,
        93,
        16,
        112,
        183,
        93,
        112,
        183,
        93,
    ]
    assert [x["params"][1] for x in items if x["command"] == 183] == [
        1100,
        1900,
        1100,
        1100,
    ]
    p.functions[0] = Function(5)
    with pytest.raises(ValueError, match="dedicated"):
        p.wpl()


def test_invalid_duplicate_outputs_coordinates_and_capacity():
    p = route()
    p.points[0].latitude = float("nan")
    with pytest.raises(ValueError):
        p.wpl()
    p = route()
    p.functions = [Function(9), Function(9), Function()]
    p.points[0].actions = [(0, False), (1, False)]
    with pytest.raises(ValueError, match="unique"):
        p.wpl()
    p = route()
    p.points *= 31
    with pytest.raises(ValueError):
        p.wpl()


def test_usb_crc_noise_and_foreign_rover():
    raw = b"12345678"
    packet = encode(20, 1, raw)
    decoder = Decoder()
    result = []
    for b in b"noise" + packet:
        result += decoder.feed(bytes([b]))
    assert result == [(20, 1, raw)]
    bad = bytearray(packet)
    bad[-1] ^= 1
    assert Decoder().feed(bad) == []
    decoder.feed(b"x" * 100000)
    assert len(decoder.buf) <= 1


class Port:
    def __init__(self):
        self.writes = []
        self.data = b""
        self.out_waiting = 0
        self.open = True

    @property
    def in_waiting(self):
        return len(self.data)

    def write(self, data):
        self.writes.append(data)
        return len(data)

    def read(self, n):
        d, self.data = self.data[:n], self.data[n:]
        return d

    def reset_output_buffer(self):
        pass

    def close(self):
        self.open = False


def usb():
    link = MissionUSB.__new__(MissionUSB)
    link.port = Port()
    link.rover = 2
    link.check = lambda: None
    link.gate = threading.RLock()
    link.status = lambda s: None
    link.decoder = Decoder()
    from collections import deque

    link.messages = deque(maxlen=64)
    link.mav = mav.MAVLink(link, srcSystem=255, srcComponent=190)
    return link


def test_native_mission_envelope_and_partial_send_fail_closed():
    link = usb()
    link.mav.heartbeat_send(6, 8, 0, 0, 4)
    frames = Decoder().feed(link.port.writes[-1])
    assert frames[0][:2] == (2, 1)
    assert frames[0][2][0] == 0xFD
    link.port.write = lambda d: len(d) - 1
    with pytest.raises(OSError, match="Partial"):
        link.mav.heartbeat_send(6, 8, 0, 0, 4)


def test_foreign_envelope_and_inner_source_are_filtered():
    link = usb()
    sender = mav.MAVLink(None, srcSystem=2, srcComponent=1)
    raw = mav.MAVLink_heartbeat_message(10, 3, 1, 4, 3, 3).pack(sender)
    link.port.data = encode(1, 1, raw) + encode(2, 1, raw)
    msg = link.recv_match()
    assert msg.get_srcSystem() == 2
    assert link.recv_match() is None
    c = Client("", 2, link=link)
    foreign = mav.MAVLink(None, srcSystem=3, srcComponent=1)
    link.port.data = encode(
        2, 1, mav.MAVLink_heartbeat_message(10, 3, 1, 4, 3, 3).pack(foreign)
    )
    assert c.recv(["HEARTBEAT"], 0.02) is None
    assert c.hb is None


def test_hold_or_close_prevents_late_usb_send():
    service = MissionService()
    link = usb()
    link.gate = service._gate
    link.check = service._check
    service.hold()
    with pytest.raises(Cancelled):
        link.mav.command_long_send(2, 1, 300, 0, 0, 0, 0, 0, 0, 0, 0)
    assert link.port.writes == []
    service.hold_event.clear()
    service.ui_at = time.monotonic() - 3
    with pytest.raises(Cancelled):
        link.mav.heartbeat_send(6, 8, 0, 0, 4)
    assert link.port.writes == []


def test_client_start_is_one_shot_even_after_unknown():
    link = usb()
    c = Client("", 2, link=link)
    c.start_attempted = True
    with pytest.raises(RuntimeError, match="already attempted"):
        c.start_once()
    assert link.port.writes == []


def test_auxiliary_preflight_never_writes_parameters():
    p = route()
    p.functions[0] = Function(9)
    p.points[0].actions = [(0, False)]
    items = parse_text(p.wpl())
    service = MissionService()
    asked = []

    def param(name):
        asked.append(name)
        return {"SERVO9_FUNCTION": 0, "SERVO9_MIN": 1000, "SERVO9_MAX": 2000}[name]

    c = SimpleNamespace(parameter=param)
    with pytest.raises(RuntimeError, match="explicit"):
        service._auxiliary(c, items, False)
    assert asked == []
    service._auxiliary(c, items, True)
    assert asked == ["SERVO9_FUNCTION", "SERVO9_MIN", "SERVO9_MAX"]
    c.parameter = lambda name: 73 if name.endswith("FUNCTION") else 1000
    with pytest.raises(RuntimeError, match="must be 0"):
        service._auxiliary(c, items, True)


def test_no_auto_reconnect_after_open_failure():
    attempts = []

    def fail(port, rover):
        attempts.append((port, rover))
        raise OSError("unplugged")

    service = MissionService(fail)
    service.connect("COM9", 3)
    service.thread.join(1)
    assert attempts == [("COM9", 3)] and not service.running
    assert service.verified_digest == ""
    with pytest.raises(RuntimeError, match="wait 5"):
        service.connect("COM9", 4)


def test_map_click_only_edits_and_function_tool_resets(qt_application):
    calls = []
    d = MissionDialog(lambda: calls.append("connect"))
    d.map.set_online(False)
    d.show()
    d.map._center = (13.6, 123.2)
    qt_application.processEvents()
    QTest.mouseClick(
        d.map,
        Qt.MouseButton.LeftButton,
        pos=QPoint(d.map.width() // 2, d.map.height() // 2),
    )
    assert len(d.plan.points) == 1 and calls == [] and not d.service.running
    d.mode.setCurrentIndex(1)
    d._add(13.6001, 123.2001)
    assert d.plan.points[-1].actions == [(0, True)] and d.mode.currentIndex() == 0
    d.close()


def test_main_manual_paths_locked_during_mission(monkeypatch):
    from pctelerc.ui import MainWindow

    w = MainWindow(start_services=False)
    w._open_mission()
    d = w._mission_dialog
    monkeypatch.setattr(type(d.service), "running", property(lambda self: True))
    monkeypatch.setattr(w.mav, "start", lambda: pytest.fail("manual link started"))
    monkeypatch.setattr(
        w.mav, "enable_control", lambda: pytest.fail("manual control enabled")
    )
    w._apply_and_reconnect()
    w._toggle_control()
    w._vehicle_command(lambda: pytest.fail("ARM sent"))
    d.service.thread = None
    monkeypatch.setattr(type(d.service), "running", property(lambda self: False))
    w.close()


def test_start_ack_loss_transmits_once_and_latches_unknown(monkeypatch):
    import pctelerc.mission_protocol.client as mod

    calls = []
    clock = [0.0]
    link = SimpleNamespace(
        mav=SimpleNamespace(command_long_send=lambda *a: calls.append(a))
    )
    c = Client("", 2, link=link)
    c.heartbeat = lambda **kwargs: None

    def receive(*args):
        clock[0] += 2
        return None

    c.recv = receive
    monkeypatch.setattr(mod, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    with pytest.raises(RuntimeError, match="UNKNOWN"):
        c.start_once()
    assert len(calls) == 1 and calls[0][2] == 300 and c.start_attempted
    with pytest.raises(RuntimeError, match="already attempted"):
        c.start_once()
    assert len(calls) == 1


def test_ui_confirmation_cancel_sends_nothing(qt_application, monkeypatch):
    from PySide6.QtWidgets import QDialog

    d = MissionDialog(lambda: True)
    d.plan = route()
    d.connected = True
    monkeypatch.setattr(type(d.service), "running", property(lambda self: True))
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    monkeypatch.setattr(
        d.service, "submit", lambda *a: pytest.fail("cancelled plan submitted")
    )
    d._submit("upload")
    monkeypatch.setattr(type(d.service), "running", property(lambda self: False))
    d.close()


def test_escape_cannot_hide_a_live_mission_session(qt_application, monkeypatch):
    calls = []
    d = MissionDialog(lambda: True)
    monkeypatch.setattr(d.service, "close", lambda: calls.append("closed") or True)
    d.show()
    QTest.keyClick(d, Qt.Key.Key_Escape)
    qt_application.processEvents()
    assert calls == ["closed"] and not d.isVisible() and not d.timer.isActive()


def test_disconnect_closes_mission_before_manual_reconnect(monkeypatch):
    from pctelerc.ui import MainWindow

    w = MainWindow(start_services=False)
    w._open_mission()
    d = w._mission_dialog
    calls = []
    monkeypatch.setattr(type(d.service), "running", property(lambda self: True))
    monkeypatch.setattr(d.service, "close", lambda: calls.append("mission") or True)
    monkeypatch.setattr(w.mav, "stop", lambda: calls.append("manual") or True)
    assert w._disconnect_link() and calls == ["mission", "manual"]
    monkeypatch.setattr(type(d.service), "running", property(lambda self: False))
    w.close()


def test_legacy_unguarded_servo_plan_is_rejected():
    text = "QGC WPL 110\n0 0 3 16 0 0 0 0 13.6 123.2 0 1\n1 0 3 16 0 0 0 0 13.6 123.2 0 1\n2 0 2 183 9 1900 0 0 0 0 0 1\n"
    with pytest.raises(ValueError, match="settling"):
        parse_text(text)


def test_function_block_runs_with_a_stopped_nav_command():
    p = route()
    p.functions[0] = Function(9)
    p.points[0].actions = [(0, True)]
    p.points[1].actions = [(0, False)]
    items = parse_text(p.wpl())
    # Rover 4.6.3 loads the first CONDITION while searching for the next NAV.
    # The following NAV must be a stopped delay, never the next travel target.
    for i, row in enumerate(items):
        if row["command"] == 183:
            next_nav = next(r for r in items[i + 1 :] if r["command"] in (16, 93))
            assert next_nav["command"] == 93 and next_nav["params"] == [4, -1, -1, -1]
    assert next(r for r in items[1:] if r["command"] in (16, 93))["command"] == 93


def test_connect_without_plan_allows_hold_recovery(monkeypatch):
    prepared = []
    d = MissionDialog(lambda: prepared.append(True) or True)
    d._clear()
    d.port.setCurrentText("COM9")
    calls = []
    monkeypatch.setattr(d.service, "connect", lambda *a: calls.append(a))
    d._connect()
    assert calls == [("COM9", 1)] and prepared == [True]
    assert not d.upload_btn.isEnabled() and not d.start_btn.isEnabled()
    d.close()


def test_collapsed_panels_are_display_only(qt_application, monkeypatch):
    d = MissionDialog(lambda: pytest.fail("display acquired radio"))
    d.show()
    d.plan_toggle.click()
    d.help_toggle.click()
    d.advanced_toggle.click()
    qt_application.processEvents()
    assert (
        not d.editor.isVisible() and d.help_panel.isVisible() and not d.service.running
    )
    d.plan_toggle.click()
    qt_application.processEvents()
    assert d.editor.isVisible()
    d.close()


def test_draft_reload_restores_planning_only(qt_application):
    d = MissionDialog(lambda: True)
    d._clear()
    d._add(13.6, 123.2)
    d.functions[0][0].setValue(9)
    d.aux.setChecked(True)
    d.continue_loss.setChecked(True)
    d.close()
    restored = MissionDialog(lambda: True)
    assert len(restored.plan.points) == 1 and restored.functions[0][0].value() == 9
    assert not restored.aux.isChecked() and not restored.continue_loss.isChecked()
    assert not restored.service.running and not restored.start_btn.isEnabled()
    restored.close()


def test_stale_fc_interrupts_inflight_work():
    from dataclasses import replace

    service = MissionService()
    service.snapshot = replace(service.snapshot, last_heartbeat=time.monotonic() - 6)
    with pytest.raises(RuntimeError, match="Telemetry lost"):
        service._check()


def test_repeated_position_is_not_a_fresh_stationary_sample():
    service = MissionService()
    sender = mav.MAVLink(None, srcSystem=1, srcComponent=1)
    parser = mav.MAVLink(None)

    def position(t):
        return parser.parse_char(
            mav.MAVLink_global_position_int_message(
                t, 136000000, 1232000000, 0, 0, 0, 0, 0, 0
            ).pack(sender)
        )

    service._observe(position(1000), 1)
    old = service.snapshot.position_timestamp
    service._observe(position(1000), 1)
    assert service.snapshot.position_timestamp == old and len(service.stationary) == 1
    with pytest.raises(RuntimeError, match="reboot"):
        service._observe(position(100), 1)


def test_pending_hold_cannot_enqueue_a_start(monkeypatch):
    service = MissionService()
    monkeypatch.setattr(type(service), "running", property(lambda self: True))
    service.hold()
    with pytest.raises(Cancelled):
        service.submit("start", parse_text(route().wpl()))
    assert service.jobs.empty()


def test_gui_and_cli_share_transaction_semantics():
    import ast
    from pathlib import Path

    gui = ast.parse(Path("src/pctelerc/mission_protocol/client.py").read_text())
    cli = ast.parse(Path("firmware/mission/tools/mission_client.py").read_text())
    names = {
        "Client",
        "read_plan",
        "validate_actions",
        "fingerprint",
        "compare",
        "from_message",
    }

    def definitions(tree):
        return {
            node.name: ast.dump(node, include_attributes=False)
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names
        }

    assert definitions(gui) == definitions(cli)


def test_expanded_small_window_keeps_fields_readable(qt_application, tmp_path):
    d = MissionDialog(lambda: True, draft_path=tmp_path / "draft.json")
    d.resize(900, 650)
    d.show()
    d.advanced_toggle.click()
    d.help_toggle.click()
    qt_application.processEvents()
    assert d.lat.height() >= 28 and d.functions[0][0].height() >= 28
    assert d.editor_scroll.verticalScrollBar().maximum() > 0
    assert d.hold_btn.isVisible() and d.hold_btn.geometry().bottom() < d.height()
    d.close()


def test_ardurover_nonposition_readback_frames_are_normalized():
    expected = parse_text(route().wpl())
    actual = copy.deepcopy(expected)
    for row in actual:
        if row["command"] != 16:
            row["frame"] = 0
    compare(expected, actual)
    actual[1]["frame"] = 3
    with pytest.raises(RuntimeError, match="frame mismatch"):
        compare(expected, actual)


def test_legacy_request_still_gets_exact_integer_mission_item():
    link = usb()
    client = Client("", 2, link=link)
    item = next(row for row in parse_text(route().wpl())[1:] if row["command"] == 16)
    client.item_send(item, legacy=True)
    frame = Decoder().feed(link.port.writes[-1])[0][2]
    message = mav.MAVLink(None).parse_char(frame)
    assert (
        message.get_type() == "MISSION_ITEM_INT"
        and message.x == item["x"]
        and message.y == item["y"]
    )


@pytest.mark.parametrize("phase", ["AUTO · running", "AUTO · monitor only"])
@pytest.mark.parametrize("mode,armed", [(0, True), (4, False), (10, False)])
def test_takeover_updates_phase_for_started_and_monitored_missions(phase, mode, armed):
    service = MissionService()
    service.phase = phase
    sender = mav.MAVLink(None, srcSystem=2, srcComponent=1)
    parser = mav.MAVLink(None)
    heartbeat = parser.parse_char(
        mav.MAVLink_heartbeat_message(10, 3, 129 if armed else 1, mode, 3, 3).pack(
            sender
        )
    )
    service._observe(heartbeat, 2)
    assert service.phase == (
        "RC/FC takeover · monitor only" if armed else "Disarmed · monitor only"
    )
    assert service.snapshot.armed == armed

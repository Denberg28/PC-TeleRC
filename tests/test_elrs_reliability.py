"""Fault injection for the ELRS USB session; no RF hardware claims."""
from dataclasses import replace
from types import SimpleNamespace
import threading
import time

import pytest
from pymavlink.dialects.v10 import ardupilotmega as mavlink1

from pctelerc.config import AppSettings
from pctelerc.core import ControlFrame, LinkState
from pctelerc.mavlink import MavlinkService, MavlinkSnapshot
from pctelerc.transport import VehicleSerial
from test_elrs_serial import FakeSerial, wait_until


@pytest.fixture
def ready(monkeypatch):
    import serial
    import pctelerc.mavlink as module
    monkeypatch.setattr(serial, "Serial", FakeSerial)
    clock = SimpleNamespace(now=100.0)
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: clock.now, sleep=lambda _: None))
    service = MavlinkService()
    service.configure(AppSettings(link_mode="elrs_serial", elrs_port="COM5"))
    link = VehicleSerial("COM5")
    service._link = link
    service._control_mav = mavlink1.MAVLink(link, srcSystem=255, srcComponent=190)
    service._snapshot = MavlinkSnapshot(running=True, state=LinkState.CONNECTED,
                                        last_heartbeat=100, vehicle_system=42, vehicle_component=1)
    service.set_control_frame(ControlFrame(0, 0, 100), 3)
    yield service, link, clock
    service.disable_control()
    link.close()


def messages(link):
    decoder = mavlink1.MAVLink(None)
    return [decoder.parse_char(frame) for frame in link.port.tx]


def test_safety_runs_between_rate_limited_drive_writes_and_uses_latest_input(ready):
    service, link, clock = ready
    assert service.enable_control()[0]
    service._control_tick(clock.now)
    clock.now += .05
    service.set_control_frame(ControlFrame(.2, .4, clock.now), 3)
    service._control_tick(clock.now)
    assert len(link.port.tx) == 1
    clock.now += .151
    service.set_control_frame(ControlFrame(.8, .8, clock.now), 3)
    service._control_tick(clock.now)
    assert [message.chan1_raw for message in messages(link)] == [1500, 1900]
    clock.now += .05  # Before the next drive write is due.
    service.set_control_frame(None)
    service._control_tick(clock.now)
    assert service.snapshot().failsafe_latched and not service.snapshot().control_enabled
    assert messages(link)[-1].chan1_raw == 0


def test_fresh_input_after_worker_stall_cannot_resume_drive(ready):
    service, link, clock = ready
    assert service.enable_control()[0]
    clock.now += .5
    service.set_control_frame(ControlFrame(.8, .8, clock.now), 3)
    service._control_tick(clock.now)
    assert service.snapshot().failsafe_latched
    assert "deadline" in service.snapshot().error
    assert all(message.chan1_raw in (0, 1500) for message in messages(link))


def test_stale_or_stopped_link_blocks_enable_and_arm_even_with_cached_connected_state(ready):
    service, _, clock = ready
    clock.now += 4
    service.set_control_frame(ControlFrame(0, 0, clock.now), 3)
    assert not service.enable_control()[0]
    assert not service.arm()[0]
    service._snapshot = replace(service.snapshot(), last_heartbeat=clock.now)
    service._stop.set()
    assert not service.enable_control()[0]
    assert not service.arm()[0]


def test_monitor_only_disable_does_not_write_rc_or_clear_output(ready, monkeypatch):
    service, link, _ = ready
    monkeypatch.setattr(link, "discard_pending_output", lambda: pytest.fail("monitor flushed queue"))
    assert service.disable_control()
    assert service._send_neutral_then_release()
    assert not link.port.tx


def test_disable_clears_local_queue_before_neutral_and_release(ready, monkeypatch):
    service, link, _ = ready
    assert service.enable_control()[0]
    events = []
    reset = link.port.reset_output_buffer
    write = link.port.write
    monkeypatch.setattr(link.port, "reset_output_buffer", lambda: (events.append("clear"), reset())[-1])
    monkeypatch.setattr(link.port, "write", lambda data: (events.append("write"), write(data))[-1])
    link.port.out_waiting = 200
    assert service.disable_control()
    assert events[0] == "clear"
    assert messages(link)[0].chan1_raw == 1500 and messages(link)[-1].chan1_raw == 0
    assert not service._owns_elrs_override


def test_disarm_releases_control_before_disarm_command(ready):
    service, link, _ = ready
    assert service.enable_control()[0]
    assert service.disarm()[0]
    decoded = messages(link)
    assert decoded[-2].chan1_raw == 0
    assert decoded[-1].get_type() == "COMMAND_LONG" and decoded[-1].param1 == 0
    assert not service.snapshot().control_enabled


def test_disable_serializes_with_inflight_drive(ready, monkeypatch):
    service, link, clock = ready
    assert service.enable_control()[0]
    service.set_control_frame(ControlFrame(.5, .5, clock.now), 3)
    started, resume, finished = threading.Event(), threading.Event(), threading.Event()
    original = service._send_override
    def blocked(steer, drive):
        if steer != 1500:
            started.set()
            assert resume.wait(2)
        return original(steer, drive)
    monkeypatch.setattr(service, "_send_override", blocked)
    tick = threading.Thread(target=lambda: service._control_tick(clock.now))
    disable = threading.Thread(target=lambda: (service.disable_control(), finished.set()))
    tick.start()
    assert started.wait(1)
    disable.start()
    assert not finished.wait(.05)
    resume.set()
    tick.join(2)
    disable.join(2)
    assert finished.is_set() and not tick.is_alive() and not disable.is_alive()
    assert messages(link)[-1].chan1_raw == 0
    count = len(link.port.tx)
    service._control_tick(clock.now)
    assert len(link.port.tx) == count


@pytest.mark.parametrize("vehicle,autopilot,system,component", [(6, 8, 42, 1), (10, 8, 42, 1), (2, 3, 42, 1), (10, 3, 255, 1), (10, 3, 42, 190)])
def test_non_rover_heartbeat_cannot_claim_session(ready, vehicle, autopilot, system, component):
    service, _, clock = ready
    service._snapshot = MavlinkSnapshot(running=True)
    encoder = mavlink1.MAVLink(None, srcSystem=system, srcComponent=component)
    msg = mavlink1.MAVLink(None).parse_char(encoder.heartbeat_encode(vehicle, autopilot, 0, 0, 4).pack(encoder))
    service._handle_message(msg, clock.now)
    assert service.snapshot().vehicle_system is None


def test_heartbeat_recovery_retains_fault_until_manual_enable(ready):
    service, link, clock = ready
    assert service.enable_control()[0]
    service.set_control_frame(None)
    service._control_tick(clock.now)
    error = service.snapshot().error
    encoder = mavlink1.MAVLink(None, srcSystem=42, srcComponent=1)
    msg = mavlink1.MAVLink(None).parse_char(encoder.heartbeat_encode(10, 3, 0, 0, 4).pack(encoder))
    service._handle_message(msg, clock.now)
    assert service.snapshot().error == error
    service.set_control_frame(ControlFrame(0, 0, clock.now), 3)
    assert service.enable_control()[0]
    assert not service.snapshot().error


def test_small_persistent_usb_backlog_is_detected(monkeypatch):
    import serial
    import pctelerc.transport as module
    monkeypatch.setattr(serial, "Serial", FakeSerial)
    clock = SimpleNamespace(now=100.)
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: clock.now))
    link = VehicleSerial("COM5")
    try:
        link.port.out_waiting = 17
        link.check_health()
        clock.now += .101
        with pytest.raises(OSError, match="backed up"):
            link.check_health()
        link.discard_pending_output()
        link.check_health()
    finally:
        link.close()


def test_excess_receive_backlog_cannot_refresh_a_stale_heartbeat(ready):
    _, link, _ = ready
    link.port.rx.extend(bytes(8193))
    with pytest.raises(OSError, match="receive backlog"):
        link.recv_msg()
    # Receive congestion must not itself block outgoing emergency packets.
    assert link.write(b'x') == 1


@pytest.mark.parametrize("fault", ["noise", "partial_write", "backlog"])
def test_worker_faults_latch_off_without_automatic_reopen(monkeypatch, fault):
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
        port = ports[0]
        encoder = mavlink1.MAVLink(None, srcSystem=42, srcComponent=1)
        port.rx.extend(encoder.heartbeat_encode(10, 3, 0, 0, 4).pack(encoder))
        assert wait_until(lambda: service.snapshot().state == LinkState.CONNECTED)
        service.set_control_frame(ControlFrame(0, 0, time.monotonic()), 3)
        assert service.enable_control()[0]
        if fault == "noise":
            monkeypatch.setattr(port, "read", lambda count: bytes(4096))
            service.set_control_frame(None)
        elif fault == "partial_write":
            monkeypatch.setattr(port, "write", lambda data: len(data) - 1)
        else:
            port.out_waiting = 65
        assert wait_until(lambda: service.snapshot().failsafe_latched, .5)
        assert not service.snapshot().control_enabled
        if fault != "noise":
            assert wait_until(lambda: not port.is_open)
        assert len(ports) == 1
    finally:
        service.stop()

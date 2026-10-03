from dataclasses import replace
import threading
import time

import pytest
from pymavlink.dialects.v10 import ardupilotmega as mavlink1

from pctelerc.config import AppSettings
from pctelerc.core import ControlFrame, LinkState
from pctelerc.mavlink import MavlinkService, MavlinkSnapshot


class CaptureLink:
    def __init__(self):
        self.frames = []
        self.destination = ('127.0.0.1', 14550)

    def write(self, data):
        self.frames.append(bytes(data))
        return len(data)

    def configure_target(self, host, port):
        self.destination = (host, port)


def ready_service():
    service = MavlinkService()
    service._link = CaptureLink()
    service._control_mav = mavlink1.MAVLink(service._link, srcSystem=255, srcComponent=190)
    service._snapshot = MavlinkSnapshot(running=True, state=LinkState.CONNECTED,
                                        last_heartbeat=time.monotonic(), vehicle_system=1, vehicle_component=1)
    service.set_control_frame(ControlFrame(0, 0, time.monotonic()), 3)
    return service


def decoded(service):
    parser = mavlink1.MAVLink(None)
    return [parser.parse_char(data) for data in service._link.frames]


def test_enable_rechecks_heartbeat_age_and_running():
    service = ready_service()
    service._snapshot = replace(service.snapshot(), last_heartbeat=time.monotonic() - 10)
    assert not service.enable_control()[0]
    service._snapshot = replace(service.snapshot(), running=False, last_heartbeat=time.monotonic())
    assert not service.enable_control()[0]
    assert not service.arm()[0]


@pytest.mark.parametrize('frame', [
    ControlFrame(float('nan'), 0, 0), ControlFrame(0, float('inf'), 0),
    ControlFrame(0, 0, float('inf')), ControlFrame(0, 1.1, 0),
])
def test_bad_controller_frame_latches_control_off(frame):
    service = ready_service()
    assert service.enable_control()[0]
    service.set_control_frame(replace(frame, timestamp=time.monotonic()) if frame.timestamp == 0 else frame, 3)
    service._control_tick(time.monotonic())
    assert not service.snapshot().control_enabled
    assert service.snapshot().failsafe_latched
    assert decoded(service)[-1].chan1_raw == 0
    assert decoded(service)[-1].chan2_raw == 0


def test_controller_loss_recovery_requires_manual_enable():
    service = ready_service()
    assert service.enable_control()[0]
    service.set_control_frame(None)
    service._control_tick(time.monotonic())
    service.set_control_frame(ControlFrame(0, 0, time.monotonic()), 3)
    service._control_tick(time.monotonic())
    assert not service.snapshot().control_enabled
    assert service.snapshot().failsafe_latched
    assert service.enable_control()[0]


def test_socket_send_error_latches_control_off():
    service = ready_service()
    assert service.enable_control()[0]
    def fail(data):
        raise OSError('network unreachable')
    service._link.write = fail
    service._control_tick(time.monotonic())
    assert service.snapshot().failsafe_latched
    assert not service.snapshot().control_enabled


def test_mapping_edit_releases_old_channels_before_using_new_mapping():
    service = ready_service()
    assert service.enable_control()[0]
    service.configure(AppSettings(steering_channel=4, throttle_channel=5))
    messages = decoded(service)
    assert messages[-1].chan1_raw == 0 and messages[-1].chan2_raw == 0
    assert messages[-1].chan4_raw == 65535 and messages[-1].chan5_raw == 65535
    assert not service.snapshot().control_enabled
    assert not service.enable_control()[0]  # old frame was invalidated


def test_network_edit_requires_disconnect_and_preserves_old_target():
    service = ready_service()
    assert service.enable_control()[0]
    with pytest.raises(ValueError, match='Disconnect'):
        service.configure(AppSettings(target_host='192.168.4.1'))
    assert service._settings.target_host == ''
    assert not service.snapshot().control_enabled


def test_disable_cannot_finish_before_an_inflight_drive_command():
    service = ready_service()
    assert service.enable_control()[0]
    service.set_control_frame(ControlFrame(.5, .5, time.monotonic()), 3)
    started = threading.Event()
    resume = threading.Event()
    finished = threading.Event()
    original = service._send_override
    def blocked(steer, throttle):
        if steer != 1500:
            started.set()
            assert resume.wait(2)
        return original(steer, throttle)
    service._send_override = blocked
    tick = threading.Thread(target=lambda: service._control_tick(time.monotonic()))
    disable = threading.Thread(target=lambda: (service.disable_control(), finished.set()))
    tick.start()
    assert started.wait(1)
    disable.start()
    assert not finished.wait(.05)
    resume.set()
    tick.join(2)
    disable.join(2)
    assert not tick.is_alive() and not disable.is_alive()
    assert finished.is_set()
    assert decoded(service)[-1].chan1_raw == 0 and decoded(service)[-1].chan2_raw == 0
    count = len(service._link.frames)
    service._control_tick(time.monotonic())
    assert len(service._link.frames) == count


def test_monitor_only_disable_does_not_interrupt_another_controller():
    service = ready_service()
    service.disable_control()
    service._send_neutral_then_release()
    assert not service._link.frames


def test_worker_delay_cannot_resume_from_fresh_data_after_suspend():
    service = ready_service()
    assert service.enable_control()[0]
    service._last_control_tick = time.monotonic() - 1
    service.set_control_frame(ControlFrame(.4, .8, time.monotonic()), 3)
    service._control_tick(time.monotonic())
    assert service.snapshot().failsafe_latched
    assert not service.snapshot().control_enabled
    assert all(message.chan1_raw in (0, 1500) for message in decoded(service))


def test_disarm_stops_overrides_before_command_and_reports_rejection():
    service = ready_service()
    assert service.enable_control()[0]
    assert service.disarm()[0]
    assert not service.snapshot().control_enabled
    assert decoded(service)[-1].get_type() == 'COMMAND_LONG'
    ack = mavlink1.MAVLink(None, srcSystem=1, srcComponent=1).command_ack_encode(400, 2)
    # Messages constructed directly need a header to identify their sender.
    ack._header.srcSystem = 1
    ack._header.srcComponent = 1
    service._handle_message(ack, time.monotonic())
    assert 'rejected' in service.snapshot().command_status
    assert not service.snapshot().command_pending


def test_arm_confirmation_requires_vehicle_heartbeat():
    service = ready_service()
    assert service.arm()[0]
    assert service.snapshot().command_pending
    encoder = mavlink1.MAVLink(None, srcSystem=1, srcComponent=1)
    heartbeat = encoder.heartbeat_encode(10, 3, 128, 0, 4)
    heartbeat._header.srcSystem = 1
    heartbeat._header.srcComponent = 1
    service._handle_message(heartbeat, time.monotonic())
    assert service.snapshot().armed
    assert service.snapshot().command_status == 'Vehicle confirmed ARMED.'
    assert not service.snapshot().command_pending


def test_tick_uses_current_time_after_reading_a_new_frame():
    service = ready_service()
    assert service.enable_control()[0]
    old_loop_time = time.monotonic() - .05
    service.set_control_frame(ControlFrame(.4, .8, time.monotonic()), 3)
    service._control_tick(old_loop_time)
    assert service.snapshot().control_enabled
    assert decoded(service)[-1].chan1_raw == 1700

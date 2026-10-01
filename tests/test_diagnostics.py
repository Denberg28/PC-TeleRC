from pctelerc.config import AppSettings
from pctelerc.controller import ControllerDevice, ControllerSnapshot
from pctelerc.core import ControlFrame, LinkState
from pctelerc.diagnostics import build_diagnostic_report, build_targeted_status
from pctelerc.mavlink import MavlinkSnapshot


def healthy_report():
    now = 100.0
    settings = AppSettings(wheel_guid="wheel", steering_channel=1, throttle_channel=3)
    wheel = ControllerSnapshot(
        connected=True,
        name="PXN",
        guid="wheel",
        axes=(0.0, 1.0, 1.0),
        steering=0.0,
        throttle=0.0,
        frame=ControlFrame(0.0, 0.0, now),
    )
    devices = [ControllerDevice(0, "PXN", "wheel", 3, 10)]
    mav = MavlinkSnapshot(
        running=True,
        state=LinkState.CONNECTED,
        heartbeat_age=0.1,
        vehicle_system=1,
        vehicle_component=1,
        mode="MANUAL",
        rx_messages=10,
        tx_messages=5,
    )
    return build_diagnostic_report(
        app_version="test",
        settings=settings,
        wheel=wheel,
        devices=devices,
        mav=mav,
        settings_dirty=False,
        network_dirty=False,
        now=now,
    )


def test_healthy_diagnostics_have_no_failures():
    report = healthy_report()
    assert report.failures == 0
    assert "[PASS] Vehicle heartbeat" in report.text
    assert "[PASS] RC channel mapping" in report.text


def test_same_rc_channel_is_failure():
    now = 100.0
    settings = AppSettings(wheel_guid="wheel", steering_channel=2, throttle_channel=2)
    wheel = ControllerSnapshot(
        connected=True, name="PXN", guid="wheel", axes=(0.0, 1.0, 1.0),
        frame=ControlFrame(0.0, 0.0, now),
    )
    mav = MavlinkSnapshot(running=True, state=LinkState.CONNECTED, heartbeat_age=0.1)
    report = build_diagnostic_report(
        app_version="test", settings=settings, wheel=wheel,
        devices=[ControllerDevice(0, "PXN", "wheel", 3, 10)],
        mav=mav, settings_dirty=False, network_dirty=False, now=now,
    )
    assert report.failures >= 1
    assert "Steering and throttle must use different channels" in report.text


def test_missing_selected_controller_is_failure():
    report = build_diagnostic_report(
        app_version="test",
        settings=AppSettings(wheel_guid="missing"),
        wheel=ControllerSnapshot(error="Selected controller is not connected."),
        devices=[ControllerDevice(0, "Other", "other", 4, 8)],
        mav=MavlinkSnapshot(running=True, state=LinkState.CONNECTING),
        settings_dirty=False,
        network_dirty=False,
        now=100.0,
    )
    assert report.failures >= 2
    assert "Saved controller GUID is not currently present" in report.text


def test_targeted_status_is_only_four_operational_checks():
    now = 100.0
    settings = AppSettings(wheel_guid="wheel", steering_channel=1, throttle_channel=3)
    wheel = ControllerSnapshot(
        connected=True, name="PXN", guid="wheel", axes=(0.0, 1.0, 1.0),
        frame=ControlFrame(0.0, 0.0, now),
    )
    devices = [ControllerDevice(0, "PXN", "wheel", 3, 10)]
    mav = MavlinkSnapshot(running=True, state=LinkState.CONNECTED, heartbeat_age=.1)
    status = build_targeted_status(
        settings=settings, wheel=wheel, devices=devices, mav=mav,
        settings_dirty=False, network_dirty=False, now=now,
    )
    assert [status.link.name, status.controller.name, status.mapping.name, status.safety.name] == [
        "Link", "Controller", "Mapping", "Safety"
    ]
    assert status.link.level == "PASS"
    assert status.controller.level == "PASS"
    assert status.mapping.level == "PASS"

def test_targeted_status_flags_only_relevant_faults():
    status = build_targeted_status(
        settings=AppSettings(wheel_guid="missing", steering_channel=2, throttle_channel=2),
        wheel=ControllerSnapshot(error="Selected controller is not connected."),
        devices=[],
        mav=MavlinkSnapshot(running=True, state=LinkState.STALE, heartbeat_age=4.0),
        settings_dirty=True,
        network_dirty=False,
        now=100.0,
    )
    assert status.link.level == "FAIL"
    assert status.controller.level == "FAIL"
    assert status.mapping.level == "FAIL"
    assert status.safety.level == "WARN"

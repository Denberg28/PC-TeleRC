from __future__ import annotations

from dataclasses import dataclass
import platform
import time
from typing import Iterable

from .config import AppSettings
from .controller import ControllerDevice, ControllerSnapshot
from .core import LinkState, control_is_fresh
from .logging_setup import log_path
from .mavlink import MavlinkSnapshot


@dataclass(frozen=True)
class DiagnosticItem:
    level: str
    name: str
    detail: str


@dataclass(frozen=True)
class DiagnosticStatus:
    link: DiagnosticItem
    controller: DiagnosticItem
    mapping: DiagnosticItem
    safety: DiagnosticItem


@dataclass(frozen=True)
class DiagnosticReport:
    items: tuple[DiagnosticItem, ...]
    text: str

    @property
    def failures(self) -> int:
        return sum(item.level == "FAIL" for item in self.items)

    @property
    def warnings(self) -> int:
        return sum(item.level == "WARN" for item in self.items)


def _item(level: str, name: str, detail: str) -> DiagnosticItem:
    return DiagnosticItem(level, name, detail)


def build_targeted_status(
    *,
    settings: AppSettings,
    wheel: ControllerSnapshot,
    devices: Iterable[ControllerDevice],
    mav: MavlinkSnapshot,
    settings_dirty: bool,
    network_dirty: bool,
    now: float | None = None,
) -> DiagnosticStatus:
    now = time.monotonic() if now is None else now
    devices = tuple(devices)

    if not mav.running:
        link = _item("FAIL", "Link", mav.error or "MAVLink worker stopped.")
    elif mav.state == LinkState.CONNECTED:
        age = 0.0 if mav.heartbeat_age is None else mav.heartbeat_age
        link = _item("PASS", "Link", f"Connected • HB {age:.1f}s")
    elif mav.state == LinkState.STALE:
        link = _item("FAIL", "Link", "Heartbeat stale.")
    elif mav.rx_messages > 0:
        link = _item("WARN", "Link", "Traffic seen, no vehicle heartbeat.")
    else:
        link = _item("WARN", "Link", "Waiting for heartbeat.")

    selected = settings.wheel_guid
    match = next((d for d in devices if d.guid == selected), None) if selected else None
    fresh = wheel.connected and control_is_fresh(
        wheel.frame, now=now, stale_after=settings.controller_timeout
    )
    if not devices:
        controller = _item("FAIL", "Controller", "No controller detected.")
    elif selected and match is None:
        controller = _item("FAIL", "Controller", "Selected controller missing.")
    elif not wheel.connected:
        controller = _item("FAIL", "Controller", wheel.error or "No live input.")
    elif not fresh:
        controller = _item("FAIL", "Controller", "Input stale.")
    else:
        controller = _item("PASS", "Controller", f"{wheel.name} • {len(wheel.axes)} axes")

    max_axis = len(wheel.axes) - 1
    mapped = [settings.steer_axis, settings.throttle_axis]
    if settings.pedal_mode == "separate":
        mapped.append(settings.brake_axis)
    invalid = [axis for axis in mapped if axis < 0 or axis > max_axis] if wheel.axes else mapped
    if settings.steering_channel == settings.throttle_channel:
        mapping = _item("FAIL", "Mapping", "Steer/throttle share one RC channel.")
    elif len(set(mapped)) != len(mapped):
        mapping = _item("FAIL", "Mapping", "Steering/pedals share a controller axis.")
    elif invalid:
        mapping = _item("FAIL", "Mapping", "Mapped controller axis unavailable.")
    else:
        mapping = _item(
            "PASS",
            "Mapping",
            f"Steer CH{settings.steering_channel} • Throttle CH{settings.throttle_channel}",
        )

    if settings_dirty:
        safety = _item("WARN", "Safety", "Settings pending apply.")
    elif network_dirty:
        safety = _item("WARN", "Safety", "Network restart required.")
    elif mav.failsafe_latched:
        safety = _item("WARN", "Safety", "Fail-safe latched.")
    elif mav.control_enabled:
        safety = _item("PASS", "Safety", "PC Control ACTIVE.")
    elif wheel.frame is not None and not wheel.frame.neutral:
        safety = _item("WARN", "Safety", "Throttle not neutral.")
    else:
        safety = _item("PASS", "Safety", "Ready / control OFF.")

    return DiagnosticStatus(link, controller, mapping, safety)


def build_diagnostic_report(
    *,
    app_version: str,
    settings: AppSettings,
    wheel: ControllerSnapshot,
    devices: Iterable[ControllerDevice],
    mav: MavlinkSnapshot,
    settings_dirty: bool,
    network_dirty: bool,
    now: float | None = None,
) -> DiagnosticReport:
    status = build_targeted_status(
        settings=settings,
        wheel=wheel,
        devices=devices,
        mav=mav,
        settings_dirty=settings_dirty,
        network_dirty=network_dirty,
        now=now,
    )
    items = [
        status.link,
        status.controller,
        status.mapping,
        status.safety,
        _item("INFO", "Vehicle", f"sys {mav.vehicle_system or '—'} / comp {mav.vehicle_component or '—'} • {mav.mode or '—'}"),
        _item("INFO", "Traffic", f"RX {mav.rx_messages} • TX {mav.tx_messages} • foreign HB {mav.ignored_heartbeats}"),
        _item("INFO", "Endpoint", f"{settings.bind_host}:{settings.listen_port} -> {settings.target_host or 'reply-peer'}:{settings.target_port}"),
        _item("INFO", "Axes", f"steer {settings.steer_axis} • throttle {settings.throttle_axis} • brake {settings.brake_axis} • {settings.pedal_mode}"),
        _item("INFO", "Sensitivity", f"steering {settings.steering_sensitivity * 100:.0f}% • throttle limit {settings.throttle_limit * 100:.0f}%"),
        _item("INFO", "Platform", f"PC TeleRC {app_version} • {platform.system()} {platform.release()}"),
        _item("INFO", "Field log", str(log_path())),
    ]
    if not settings.target_host:
        items.append(_item("WARN", "UDP peer", "Dynamic peer locks to the first accepted rover heartbeat; use a fixed ESP32 IP for field operation."))
    items.append(_item("WARN", "Transport security", "MAVLink 1 is unsigned and unencrypted; peer pinning does not authenticate a device."))
    if mav.error:
        items.append(_item("FAIL", "MAVLink error", mav.error))

    counts = {
        "PASS": sum(i.level == "PASS" for i in items),
        "WARN": sum(i.level == "WARN" for i in items),
        "FAIL": sum(i.level == "FAIL" for i in items),
        "INFO": sum(i.level == "INFO" for i in items),
    }
    lines = [
        f"PC TeleRC Diagnostic Report — v{app_version}",
        f"Summary: {counts['PASS']} PASS | {counts['WARN']} WARN | {counts['FAIL']} FAIL",
        "",
    ]
    lines.extend(f"[{item.level}] {item.name}: {item.detail}" for item in items)
    lines.extend(["", "Diagnostics are read-only and do not alter control state."])
    return DiagnosticReport(tuple(items), "\n".join(lines))

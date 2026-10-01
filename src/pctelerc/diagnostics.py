from __future__ import annotations

from dataclasses import dataclass
import platform
import time
from typing import Iterable

from .config import AppSettings
from .controller import ControllerDevice, ControllerSnapshot
from .core import LinkState, control_is_fresh
from .mavlink import MavlinkSnapshot


@dataclass(frozen=True)
class DiagnosticItem:
    level: str
    name: str
    detail: str

    @property
    def ok(self) -> bool:
        return self.level in {"PASS", "INFO"}


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
    now = time.monotonic() if now is None else now
    devices = tuple(devices)
    items: list[DiagnosticItem] = []

    items.append(_item("INFO", "App", f"PC TeleRC {app_version} on {platform.system()} {platform.release()}"))
    items.append(
        _item(
            "WARN" if settings_dirty else "PASS",
            "Settings",
            "Pending edits are not applied." if settings_dirty else "Applied configuration is active.",
        )
    )
    if network_dirty:
        items.append(_item("WARN", "MAVLink restart", "Network address/port edits require Apply & Reconnect."))

    items.append(
        _item(
            "PASS" if mav.running else "FAIL",
            "MAVLink worker",
            "Listener thread is running." if mav.running else "Listener thread is not running.",
        )
    )

    if mav.state == LinkState.CONNECTED:
        age = 0.0 if mav.heartbeat_age is None else mav.heartbeat_age
        items.append(_item("PASS", "Vehicle heartbeat", f"Connected; latest heartbeat age {age:.2f}s."))
    elif mav.state == LinkState.STALE:
        age = 0.0 if mav.heartbeat_age is None else mav.heartbeat_age
        items.append(_item("FAIL", "Vehicle heartbeat", f"Heartbeat stale at {age:.2f}s (limit {settings.heartbeat_timeout:.2f}s)."))
    elif mav.rx_messages > 0:
        items.append(_item("WARN", "Vehicle heartbeat", f"MAVLink traffic is arriving ({mav.rx_messages} RX) but no accepted vehicle heartbeat is current."))
    else:
        items.append(_item("FAIL", "Vehicle heartbeat", "No vehicle heartbeat received."))

    items.append(
        _item(
            "INFO" if settings.target_host else "WARN",
            "MAVLink endpoint",
            f"Listen {settings.bind_host}:{settings.listen_port}; "
            + (f"fixed target {settings.target_host}:{settings.target_port}." if settings.target_host
               else "no fixed target IP; reply routing depends on the received UDP peer. A fixed ESP32 target is preferred for field use."),
        )
    )
    items.append(_item("INFO", "MAVLink traffic", f"RX {mav.rx_messages}; TX {mav.tx_messages}."))
    if mav.ignored_heartbeats:
        items.append(_item("WARN", "Foreign vehicle heartbeat", f"Ignored {mav.ignored_heartbeats} heartbeat(s) from another MAVLink system ID."))
    if mav.vehicle_system is not None:
        items.append(
            _item(
                "INFO",
                "Vehicle",
                f"sys {mav.vehicle_system}, comp {mav.vehicle_component or '—'}, mode {mav.mode or '—'}, "
                f"{'ARMED' if mav.armed else 'disarmed'}.",
            )
        )

    selected = settings.wheel_guid
    if not devices:
        items.append(_item("FAIL", "Controller discovery", "Windows/SDL reports no controllers."))
    else:
        items.append(_item("PASS", "Controller discovery", f"{len(devices)} controller(s) detected."))

    if selected:
        match = next((device for device in devices if device.guid == selected), None)
        items.append(
            _item(
                "PASS" if match is not None else "FAIL",
                "Selected controller",
                f"{match.name} ({match.axes} axes)." if match else "Saved controller GUID is not currently present.",
            )
        )
    else:
        items.append(_item("WARN", "Selected controller", "No controller GUID has been explicitly saved."))

    if wheel.connected:
        fresh = control_is_fresh(wheel.frame, now=now, stale_after=settings.controller_timeout)
        items.append(_item("PASS" if fresh else "FAIL", "Controller freshness", "Input stream is fresh." if fresh else "Controller input stream is stale."))
        items.append(_item("PASS" if wheel.axes else "FAIL", "Controller axes", f"{len(wheel.axes)} live axis value(s)." if wheel.axes else "No live axes available."))
        items.append(
            _item(
                "PASS" if wheel.frame is not None and wheel.frame.neutral else "WARN",
                "Throttle neutral",
                f"Drive value {wheel.throttle:+.3f}; neutral required before ARM/PC Control.",
            )
        )
        max_axis = len(wheel.axes) - 1
        mapped = [settings.steer_axis, settings.throttle_axis]
        if settings.pedal_mode == "separate":
            mapped.append(settings.brake_axis)
        invalid = [axis for axis in mapped if axis > max_axis]
        items.append(
            _item(
                "FAIL" if invalid else "PASS",
                "Axis mapping",
                f"Mapped axis index/indices out of range: {invalid}; available 0..{max_axis}." if invalid
                else f"steer={settings.steer_axis}, throttle={settings.throttle_axis}, "
                     + (f"brake={settings.brake_axis}." if settings.pedal_mode == "separate" else "combined pedal mode."),
            )
        )
    else:
        detail = wheel.error or "Selected controller is not producing input."
        items.append(_item("FAIL", "Controller input", detail))

    same_channel = settings.steering_channel == settings.throttle_channel
    items.append(
        _item(
            "FAIL" if same_channel else "PASS",
            "RC channel mapping",
            "Steering and throttle must use different channels." if same_channel
            else f"Steering CH{settings.steering_channel}; throttle CH{settings.throttle_channel}.",
        )
    )
    items.append(_item("INFO", "Throttle limit", f"{settings.throttle_limit * 100:.0f}% authority."))
    items.append(
        _item(
            "WARN" if mav.failsafe_latched else "PASS",
            "PC-control fail-safe",
            "Fail-safe is latched; manual re-enable is required." if mav.failsafe_latched
            else ("PC Control ACTIVE." if mav.control_enabled else "PC Control is OFF."),
        )
    )
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
        f"Summary: {counts['PASS']} PASS | {counts['WARN']} WARN | {counts['FAIL']} FAIL | {counts['INFO']} INFO",
        "",
    ]
    lines.extend(f"[{item.level}] {item.name}: {item.detail}" for item in items)
    lines.extend(
        [
            "",
            "Safety note: Diagnostics are read-only. They do not arm the vehicle or enable PC Control.",
        ]
    )
    return DiagnosticReport(tuple(items), "\n".join(lines))

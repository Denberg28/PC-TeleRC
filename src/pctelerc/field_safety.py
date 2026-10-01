from __future__ import annotations
from dataclasses import dataclass

from .config import AppSettings
from .core import ControlFrame, LinkState, control_is_fresh


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    code: str
    message: str


def validate_mapping(settings: AppSettings, axis_count: int | None = None) -> SafetyDecision:
    if settings.steering_channel == settings.throttle_channel:
        return SafetyDecision(False, "duplicate_rc_channel", "Steering and throttle must use different RC channels.")
    if axis_count is not None:
        mapped = [settings.steer_axis, settings.throttle_axis]
        if settings.pedal_mode == "separate":
            mapped.append(settings.brake_axis)
        invalid = [axis for axis in mapped if axis < 0 or axis >= axis_count]
        if invalid:
            return SafetyDecision(False, "axis_out_of_range", f"Mapped controller axis is unavailable: {invalid}.")
    return SafetyDecision(True, "ok", "Mapping valid.")


def can_enable_control(
    *,
    settings: AppSettings,
    link_state: LinkState,
    frame: ControlFrame | None,
    axis_count: int | None,
    now: float | None = None,
) -> SafetyDecision:
    mapping = validate_mapping(settings, axis_count)
    if not mapping.allowed:
        return mapping
    if link_state != LinkState.CONNECTED:
        return SafetyDecision(False, "link_unhealthy", "MAVLink heartbeat is not healthy.")
    if not control_is_fresh(frame, now=now, stale_after=settings.controller_timeout):
        return SafetyDecision(False, "controller_stale", "Controller input is missing or stale.")
    if frame is None or not frame.neutral:
        return SafetyDecision(False, "throttle_not_neutral", "Release throttle/brake to neutral before enabling PC control.")
    return SafetyDecision(True, "ok", "PC control prerequisites satisfied.")


def can_arm(
    *,
    settings: AppSettings,
    link_state: LinkState,
    frame: ControlFrame | None,
    axis_count: int | None,
    now: float | None = None,
) -> SafetyDecision:
    decision = can_enable_control(
        settings=settings,
        link_state=link_state,
        frame=frame,
        axis_count=axis_count,
        now=now,
    )
    if not decision.allowed:
        return SafetyDecision(False, decision.code, decision.message.replace("enabling PC control", "arming"))
    return SafetyDecision(True, "ok", "Arm prerequisites satisfied.")

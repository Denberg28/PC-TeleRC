from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import math, time

PWM_MIN = 1000
PWM_NEUTRAL = 1500
PWM_MAX = 2000

class LinkState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    STALE = "stale"

@dataclass(frozen=True)
class AxisConfig:
    deadzone: float = 0.04
    expo: float = 0.15
    invert: bool = False

@dataclass(frozen=True)
class ControlFrame:
    steering: float
    throttle: float
    timestamp: float
    unscaled_throttle: float | None = None
    @property
    def neutral(self) -> bool:
        return abs(self.throttle if self.unscaled_throttle is None else self.unscaled_throttle) <= 0.05

def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))

def shape_axis(raw: float, config: AxisConfig) -> float:
    if not math.isfinite(float(raw)):
        raise ValueError("Controller axis is not finite.")
    value = clamp(float(raw), -1.0, 1.0)
    if config.invert:
        value = -value
    dz = clamp(config.deadzone, 0.0, 0.5)
    magnitude = abs(value)
    if magnitude <= dz:
        return 0.0
    scaled = (magnitude - dz) / (1.0 - dz)
    expo = clamp(config.expo, 0.0, 1.0)
    curved = (1.0 - expo) * scaled + expo * (scaled ** 3)
    return math.copysign(curved, value)

def separate_pedals_to_throttle(throttle_axis: float, brake_axis: float, *, throttle_invert: bool = False, brake_invert: bool = False) -> float:
    if not all(math.isfinite(float(v)) for v in (throttle_axis, brake_axis)):
        raise ValueError("Pedal axis is not finite.")
    t = clamp(float(throttle_axis), -1.0, 1.0)
    b = clamp(float(brake_axis), -1.0, 1.0)
    if throttle_invert: t = -t
    if brake_invert: b = -b
    throttle = (1.0 - t) * 0.5
    brake = (1.0 - b) * 0.5
    return clamp(throttle - brake, -1.0, 1.0)

def combined_pedal_to_throttle(axis: float, *, invert: bool = False, deadzone: float = 0.04) -> float:
    return shape_axis(axis, AxisConfig(deadzone=deadzone, expo=0.0, invert=invert))

def apply_sensitivity(value: float, sensitivity: float = 1.0) -> float:
    """Scale steering authority without changing the configured expo curve."""
    value = clamp(float(value), -1.0, 1.0)
    sensitivity = clamp(float(sensitivity), 0.25, 1.0)
    return clamp(value * sensitivity, -1.0, 1.0)

def normalized_to_pwm(value: float, limit: float = 1.0) -> int:
    value = clamp(value, -1.0, 1.0)
    limit = clamp(limit, 0.0, 1.0)
    return int(round(PWM_NEUTRAL + value * 500.0 * limit))

def heartbeat_link_state(last_heartbeat: float | None, *, now: float | None = None, stale_after: float = 3.0) -> LinkState:
    if last_heartbeat is None:
        return LinkState.CONNECTING
    now = time.monotonic() if now is None else now
    return LinkState.CONNECTED if now - last_heartbeat <= stale_after else LinkState.STALE

def control_is_fresh(frame: ControlFrame | None, *, now: float | None = None, stale_after: float = 0.35) -> bool:
    if frame is None:
        return False
    now = time.monotonic() if now is None else now
    if not all(math.isfinite(v) for v in (frame.steering, frame.throttle, frame.timestamp, now)):
        return False
    if frame.unscaled_throttle is not None and (not math.isfinite(frame.unscaled_throttle) or abs(frame.unscaled_throttle) > 1):
        return False
    if abs(frame.steering) > 1 or abs(frame.throttle) > 1:
        return False
    return 0 <= now - frame.timestamp <= stale_after

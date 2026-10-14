"""Thread-safe keyboard input; snapshots never renew acquisition timestamps."""
from __future__ import annotations

from dataclasses import replace
import threading
import time

from .config import AppSettings
from .controller import ControllerSnapshot
from .core import ControlFrame, apply_sensitivity


class KeyboardService:
    KEYS = frozenset({"w", "a", "s", "d", "up", "left", "down", "right", "space"})

    def __init__(self):
        self._lock = threading.Lock()
        self._settings = AppSettings()
        self._active = False
        self._pressed: set[str] = set()
        self._blocked: set[str] = set()
        self._session = 0
        self._snapshot = ControllerSnapshot(name="Keyboard", guid="keyboard")

    def configure(self, settings):
        with self._lock:
            self._settings = replace(settings).validate()
            self._pressed.clear()
            self._blocked.clear()
            self._session += 1
            self._publish(time.monotonic())

    def set_active(self, active: bool):
        with self._lock:
            if active != self._active:
                self._active = active
                self._pressed.clear()
                self._blocked.clear()
                self._session += 1
                self._publish(time.monotonic())

    def key(self, key: str, pressed: bool, *, auto_repeat=False):
        if key not in self.KEYS or auto_repeat:
            return
        with self._lock:
            if not self._active:
                return
            now = time.monotonic()
            self._check_deadline(now)
            if pressed:
                self._pressed.add(key)
                if key == "space":
                    self._blocked.update(self._pressed - {"space"})
                elif "space" in self._pressed:
                    self._blocked.add(key)
            else:
                self._pressed.discard(key)
                self._blocked.discard(key)
            self._publish(now)

    def sample(self):
        """Called by the keyboard event-loop timer, independently of UI refresh."""
        with self._lock:
            now = time.monotonic()
            self._check_deadline(now)
            self._publish(now)

    def _check_deadline(self, now):
        frame = self._snapshot.frame
        if frame is not None and now - frame.timestamp > self._settings.controller_timeout:
            # A recovered GUI must not revive keys held during a stall.
            self._blocked.update(self._pressed - {"space"})
            self._session += 1

    def _publish(self, now):
        keys = self._pressed - self._blocked
        steering = float(bool(keys & {"d", "right"})) - float(bool(keys & {"a", "left"}))
        throttle = float(bool(keys & {"w", "up"})) - float(bool(keys & {"s", "down"}))
        if "space" in self._pressed:
            steering = throttle = 0.0
        steering = apply_sensitivity(steering, self._settings.steering_sensitivity)
        frame = ControlFrame(steering, throttle, now, self._session,
                             acquisition_ready=not self._pressed) if self._active else None
        self._snapshot = ControllerSnapshot(
            connected=self._active, name="Keyboard", guid="keyboard",
            steering=steering if self._active else 0.0,
            throttle=throttle if self._active else 0.0, frame=frame,
            error="" if self._active else "Click the keyboard driving area to focus it.",
        )

    def snapshot(self):
        with self._lock:
            return self._snapshot


class InputService:
    """One applied input source, preserving wheel acquisition time and session."""
    def __init__(self, wheel, keyboard):
        self.wheel = wheel
        self.keyboard = keyboard
        self._lock = threading.Lock()
        self._mode = "wheel"
        self._generation = 0

    def configure(self, settings):
        with self._lock:
            if settings.input_source != self._mode:
                self._mode = settings.input_source
                self._generation += 1
            self.keyboard.configure(settings)

    def snapshot(self):
        with self._lock:
            sample = (self.keyboard if self._mode == "keyboard" else self.wheel).snapshot()
            if sample.frame is not None:
                sample = replace(sample, frame=replace(sample.frame,
                    session=(self._generation << 32) + sample.frame.session))
            return sample

    def devices(self):
        return self.wheel.devices()

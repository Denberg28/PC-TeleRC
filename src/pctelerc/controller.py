from __future__ import annotations

from dataclasses import dataclass
import os
import threading
import time
from typing import Optional

from .config import AppSettings
from .core import (
    AxisConfig,
    ControlFrame,
    apply_sensitivity,
    combined_pedal_to_throttle,
    separate_pedals_to_throttle,
    shape_axis,
)

os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")


@dataclass(frozen=True)
class ControllerDevice:
    index: int
    name: str
    guid: str
    axes: int
    buttons: int


@dataclass(frozen=True)
class ControllerSnapshot:
    connected: bool = False
    name: str = "No controller"
    guid: str = ""
    axes: tuple[float, ...] = ()
    steering: float = 0.0
    throttle: float = 0.0
    frame: Optional[ControlFrame] = None
    error: str = ""


class WheelService:
    def __init__(self):
        self._lock = threading.Lock()
        self._snapshot = ControllerSnapshot()
        self._devices: list[ControllerDevice] = []
        self._settings = AppSettings()
        self._selected_guid = ""
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="pctelerc-wheel")
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.5)

    def configure(self, settings: AppSettings):
        with self._lock:
            self._settings = AppSettings(**vars(settings)).validate()
            self._selected_guid = settings.wheel_guid

    def select(self, guid: str):
        with self._lock:
            self._selected_guid = guid

    def devices(self) -> list[ControllerDevice]:
        with self._lock:
            return list(self._devices)

    def snapshot(self) -> ControllerSnapshot:
        with self._lock:
            return self._snapshot

    def _run(self):
        try:
            import pygame

            # SDL events back joystick hot-plug/input updates; initialize only
            # the display/event and joystick subsystems (no mixer/audio side effects).
            pygame.display.init()
            pygame.joystick.init()
        except Exception as exc:
            with self._lock:
                self._snapshot = ControllerSnapshot(error=f"Controller subsystem unavailable: {exc}")
            return

        joystick = None
        active_guid = ""
        last_scan = 0.0

        while not self._stop.is_set():
            now = time.monotonic()
            try:
                pygame.event.pump()

                if now - last_scan >= 1.0:
                    devices: list[ControllerDevice] = []
                    for index in range(pygame.joystick.get_count()):
                        probe = pygame.joystick.Joystick(index)
                        probe.init()
                        devices.append(
                            ControllerDevice(
                                index=index,
                                name=probe.get_name(),
                                guid=probe.get_guid(),
                                axes=probe.get_numaxes(),
                                buttons=probe.get_numbuttons(),
                            )
                        )

                    with self._lock:
                        self._devices = devices
                        desired_guid = self._selected_guid

                    if desired_guid:
                        chosen = next((device for device in devices if device.guid == desired_guid), None)
                    else:
                        chosen = devices[0] if devices else None

                    if chosen and (joystick is None or chosen.guid != active_guid):
                        joystick = pygame.joystick.Joystick(chosen.index)
                        joystick.init()
                        active_guid = chosen.guid
                    elif not chosen:
                        joystick = None
                        active_guid = ""

                    last_scan = now

                if joystick is None:
                    with self._lock:
                        selected = self._selected_guid
                        message = "Selected controller is not connected." if selected else ""
                        self._snapshot = ControllerSnapshot(error=message)
                    time.sleep(0.05)
                    continue

                axes = tuple(float(joystick.get_axis(i)) for i in range(joystick.get_numaxes()))
                with self._lock:
                    settings = AppSettings(**vars(self._settings)).validate()

                steer_raw = axes[settings.steer_axis] if settings.steer_axis < len(axes) else 0.0
                steer = shape_axis(
                    steer_raw,
                    AxisConfig(settings.deadzone, settings.expo, settings.invert_steer),
                )
                steer = apply_sensitivity(steer, settings.steering_sensitivity)

                if settings.pedal_mode == "combined":
                    pedal_raw = axes[settings.throttle_axis] if settings.throttle_axis < len(axes) else 0.0
                    throttle = combined_pedal_to_throttle(
                        pedal_raw,
                        invert=settings.invert_throttle,
                        deadzone=settings.deadzone,
                    )
                else:
                    throttle_raw = axes[settings.throttle_axis] if settings.throttle_axis < len(axes) else 1.0
                    brake_raw = axes[settings.brake_axis] if settings.brake_axis < len(axes) else 1.0
                    throttle = separate_pedals_to_throttle(
                        throttle_raw,
                        brake_raw,
                        throttle_invert=settings.invert_throttle,
                        brake_invert=settings.invert_brake,
                    )
                    if abs(throttle) <= settings.deadzone:
                        throttle = 0.0

                frame = ControlFrame(steer, throttle, now)
                with self._lock:
                    self._snapshot = ControllerSnapshot(
                        connected=True,
                        name=joystick.get_name(),
                        guid=active_guid,
                        axes=axes,
                        steering=steer,
                        throttle=throttle,
                        frame=frame,
                    )

            except Exception as exc:
                joystick = None
                active_guid = ""
                with self._lock:
                    self._snapshot = ControllerSnapshot(error=f"Controller read error: {exc}")

            time.sleep(0.02)

        try:
            pygame.joystick.quit()
            pygame.display.quit()
        except Exception:
            pass

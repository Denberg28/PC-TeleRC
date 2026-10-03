from __future__ import annotations

from dataclasses import dataclass
import os
import math
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
    generation: int = 0


class WheelService:
    def __init__(self):
        self._lock = threading.Lock()
        self._snapshot = ControllerSnapshot()
        self._devices: list[ControllerDevice] = []
        self._settings = AppSettings()
        self._selected_guid = ""
        self._generation = 0
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
            updated = AppSettings(**vars(settings)).validate()
            if updated != self._settings:
                self._generation += 1
                self._snapshot = ControllerSnapshot(generation=self._generation)
            self._settings = updated
            if settings.wheel_guid:
                self._selected_guid = settings.wheel_guid

    def select(self, guid: str):
        with self._lock:
            self._selected_guid = guid
            self._generation += 1
            self._snapshot = ControllerSnapshot(generation=self._generation)

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
        active_generation = -1
        last_scan = 0.0

        while not self._stop.is_set():
            now = time.monotonic()
            try:
                pygame.event.get()
                if joystick is not None and not joystick.get_attached():
                    raise RuntimeError("Selected controller was disconnected.")

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
                        generation = self._generation

                    if desired_guid:
                        chosen = next((device for device in devices if device.guid == desired_guid), None)
                    else:
                        chosen = devices[0] if devices else None

                    if chosen and sum(device.guid == chosen.guid for device in devices) > 1:
                        raise RuntimeError("Multiple identical controllers detected. Connect only the selected wheel.")
                    if chosen and (joystick is None or chosen.guid != active_guid or generation != active_generation):
                        joystick = pygame.joystick.Joystick(chosen.index)
                        joystick.init()
                        active_guid = chosen.guid
                        with self._lock:
                            if not self._selected_guid:
                                self._selected_guid = chosen.guid
                            self._generation += 1
                            active_generation = self._generation
                    elif not chosen:
                        joystick = None
                        active_guid = ""

                    last_scan = now

                if joystick is None:
                    with self._lock:
                        selected = self._selected_guid
                        message = "Selected controller is not connected." if selected else ""
                        if self._snapshot.connected:
                            self._generation += 1
                        self._snapshot = ControllerSnapshot(error=message, generation=self._generation)
                    time.sleep(0.05)
                    continue

                axes = tuple(float(joystick.get_axis(i)) for i in range(joystick.get_numaxes()))
                if not all(math.isfinite(v) and -1 <= v <= 1 for v in axes):
                    raise ValueError("Invalid controller axis reading.")
                with self._lock:
                    settings = AppSettings(**vars(self._settings)).validate()
                    generation = self._generation
                    desired_guid = self._selected_guid
                if active_guid != desired_guid or active_generation != generation:
                    last_scan = 0.0
                    self._stop.wait(.02)
                    continue

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
                    if generation != self._generation:
                        continue
                    self._snapshot = ControllerSnapshot(
                        connected=True,
                        name=joystick.get_name(),
                        guid=active_guid,
                        axes=axes,
                        steering=steer,
                        throttle=throttle,
                        frame=frame,
                        generation=self._generation,
                    )

            except Exception as exc:
                joystick = None
                active_guid = ""
                with self._lock:
                    self._generation += 1
                    self._snapshot = ControllerSnapshot(error=f"Controller read error: {exc}", generation=self._generation)

            time.sleep(0.02)

        with self._lock:
            self._snapshot = ControllerSnapshot(generation=self._generation)
        try:
            pygame.joystick.quit()
            pygame.display.quit()
        except Exception:
            pass

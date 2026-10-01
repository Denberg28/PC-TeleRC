from __future__ import annotations
from dataclasses import dataclass
import os, threading, time
from typing import Optional
from .config import AppSettings
from .core import AxisConfig, ControlFrame, combined_pedal_to_throttle, separate_pedals_to_throttle, shape_axis

os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")

@dataclass(frozen=True)
class ControllerDevice:
    index: int; name: str; guid: str; axes: int; buttons: int

@dataclass(frozen=True)
class ControllerSnapshot:
    connected: bool=False; name: str="No controller"; guid: str=""; axes: tuple[float,...]=()
    steering: float=0.0; throttle: float=0.0; frame: Optional[ControlFrame]=None; error: str=""

class WheelService:
    def __init__(self):
        self._lock=threading.Lock(); self._snapshot=ControllerSnapshot(); self._devices=[]; self._settings=AppSettings(); self._selected_guid=""
        self._stop=threading.Event(); self._thread=None
    def start(self):
        if self._thread and self._thread.is_alive(): return
        self._stop.clear(); self._thread=threading.Thread(target=self._run, daemon=True); self._thread.start()
    def stop(self):
        self._stop.set()
        if self._thread: self._thread.join(timeout=1.5)
    def configure(self, settings):
        with self._lock: self._settings=AppSettings(**vars(settings)).validate(); self._selected_guid=settings.wheel_guid
    def select(self,guid):
        with self._lock: self._selected_guid=guid
    def devices(self):
        with self._lock: return list(self._devices)
    def snapshot(self):
        with self._lock: return self._snapshot
    def _run(self):
        try:
            import pygame; pygame.init(); pygame.joystick.init()
        except Exception as exc:
            with self._lock: self._snapshot=ControllerSnapshot(error=f"Controller subsystem unavailable: {exc}")
            return
        joystick=None; active_guid=""; last_scan=0.0
        while not self._stop.is_set():
            now=time.monotonic()
            try:
                pygame.event.pump()
                if now-last_scan>=1:
                    devices=[]
                    for i in range(pygame.joystick.get_count()):
                        p=pygame.joystick.Joystick(i); p.init(); devices.append(ControllerDevice(i,p.get_name(),p.get_guid(),p.get_numaxes(),p.get_numbuttons()))
                    with self._lock: self._devices=devices; desired=self._selected_guid
                    chosen=next((d for d in devices if desired and d.guid==desired), None) or (devices[0] if devices else None)
                    if chosen and (joystick is None or chosen.guid!=active_guid):
                        joystick=pygame.joystick.Joystick(chosen.index); joystick.init(); active_guid=chosen.guid
                    elif not chosen: joystick=None; active_guid=""
                    last_scan=now
                if joystick is None:
                    with self._lock: self._snapshot=ControllerSnapshot()
                    time.sleep(.05); continue
                axes=tuple(float(joystick.get_axis(i)) for i in range(joystick.get_numaxes()))
                with self._lock: s=AppSettings(**vars(self._settings)).validate()
                steer=shape_axis(axes[s.steer_axis] if s.steer_axis<len(axes) else 0.0, AxisConfig(s.deadzone,s.expo,s.invert_steer))
                if s.pedal_mode=="combined":
                    throttle=combined_pedal_to_throttle(axes[s.throttle_axis] if s.throttle_axis<len(axes) else 0.0, invert=s.invert_throttle, deadzone=s.deadzone)
                else:
                    throttle=separate_pedals_to_throttle(axes[s.throttle_axis] if s.throttle_axis<len(axes) else 1.0, axes[s.brake_axis] if s.brake_axis<len(axes) else 1.0, throttle_invert=s.invert_throttle, brake_invert=s.invert_brake)
                    if abs(throttle)<=s.deadzone: throttle=0.0
                frame=ControlFrame(steer,throttle,now)
                with self._lock: self._snapshot=ControllerSnapshot(True,joystick.get_name(),active_guid,axes,steer,throttle,frame,"")
            except Exception as exc:
                joystick=None; active_guid=""
                with self._lock: self._snapshot=ControllerSnapshot(error=f"Controller read error: {exc}")
            time.sleep(.02)
        try: pygame.joystick.quit(); pygame.quit()
        except Exception: pass

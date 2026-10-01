from __future__ import annotations
from dataclasses import asdict, dataclass, fields
import json, os
from pathlib import Path

APP_DIR_NAME = "PC-TeleRC"

@dataclass
class AppSettings:
    bind_host: str = "0.0.0.0"
    listen_port: int = 14550
    target_host: str = ""
    target_port: int = 14550
    wheel_guid: str = ""
    steer_axis: int = 0
    throttle_axis: int = 1
    brake_axis: int = 2
    pedal_mode: str = "separate"
    invert_steer: bool = False
    invert_throttle: bool = False
    invert_brake: bool = False
    deadzone: float = 0.04
    expo: float = 0.15
    throttle_limit: float = 0.25
    steering_channel: int = 1
    throttle_channel: int = 3
    heartbeat_timeout: float = 3.0
    controller_timeout: float = 0.35
    def validate(self) -> "AppSettings":
        self.listen_port = int(min(65535, max(1, self.listen_port)))
        self.target_port = int(min(65535, max(1, self.target_port)))
        self.steer_axis = max(0, int(self.steer_axis)); self.throttle_axis = max(0, int(self.throttle_axis)); self.brake_axis = max(0, int(self.brake_axis))
        self.deadzone = min(0.30, max(0.0, float(self.deadzone))); self.expo = min(1.0, max(0.0, float(self.expo)))
        self.throttle_limit = min(1.0, max(0.05, float(self.throttle_limit)))
        self.steering_channel = min(8, max(1, int(self.steering_channel))); self.throttle_channel = min(8, max(1, int(self.throttle_channel)))
        self.heartbeat_timeout = min(15.0, max(1.0, float(self.heartbeat_timeout))); self.controller_timeout = min(2.0, max(0.1, float(self.controller_timeout)))
        if self.pedal_mode not in {"separate","combined"}: self.pedal_mode = "separate"
        return self

def data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    return Path(base) / APP_DIR_NAME if base else Path.home() / f".{APP_DIR_NAME.lower()}"

def settings_path() -> Path:
    return data_dir() / "settings.json"

def load_settings(path: Path | None = None) -> AppSettings:
    target = path or settings_path()
    if not target.exists(): return AppSettings()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
        allowed = {f.name for f in fields(AppSettings)}
        return AppSettings(**{k:v for k,v in raw.items() if k in allowed}).validate()
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return AppSettings()

def save_settings(settings: AppSettings, path: Path | None = None) -> Path:
    target = path or settings_path(); target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(settings.validate()), indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(target)
    return target

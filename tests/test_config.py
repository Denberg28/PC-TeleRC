import json
from pathlib import Path

from pctelerc.config import AppSettings, CURRENT_SETTINGS_VERSION, load_settings, save_settings


def test_settings_round_trip(tmp_path: Path):
    path = tmp_path / "settings.json"
    save_settings(
        AppSettings(
            target_host="192.168.4.1",
            throttle_limit=.4,
            steering_sensitivity=.65,
            steering_channel=2,
            throttle_channel=4,
        ),
        path,
    )
    loaded = load_settings(path)
    assert loaded.target_host == "192.168.4.1"
    assert loaded.throttle_limit == .4
    assert loaded.steering_sensitivity == .65
    assert loaded.steering_channel == 2
    assert loaded.throttle_channel == 4
    assert loaded.settings_version == CURRENT_SETTINGS_VERSION


def test_default_rover_channels_match_android_telerc():
    settings = AppSettings()
    assert settings.steering_channel == 1
    assert settings.throttle_channel == 2


def test_legacy_untouched_ch1_ch3_mapping_migrates_to_ch1_ch2(tmp_path: Path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"steering_channel": 1, "throttle_channel": 3}), encoding="utf-8")
    loaded = load_settings(path)
    assert loaded.steering_channel == 1
    assert loaded.throttle_channel == 2
    assert loaded.settings_version == CURRENT_SETTINGS_VERSION


def test_legacy_custom_channel_mapping_is_preserved(tmp_path: Path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"steering_channel": 2, "throttle_channel": 3}), encoding="utf-8")
    loaded = load_settings(path)
    assert loaded.steering_channel == 2
    assert loaded.throttle_channel == 3


def test_current_explicit_ch3_mapping_is_preserved(tmp_path: Path):
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({
            "settings_version": CURRENT_SETTINGS_VERSION,
            "steering_channel": 1,
            "throttle_channel": 3,
        }),
        encoding="utf-8",
    )
    loaded = load_settings(path)
    assert loaded.steering_channel == 1
    assert loaded.throttle_channel == 3


def test_settings_clamp_invalid_values():
    s = AppSettings(listen_port=99999, throttle_limit=3, deadzone=-1, steering_channel=20).validate()
    assert s.listen_port == 65535
    assert s.throttle_limit == 1.0
    assert s.deadzone == 0.0
    assert s.steering_channel == 8


def test_sensitivity_clamps_to_safe_ui_range():
    assert AppSettings(steering_sensitivity=5).validate().steering_sensitivity == 1.0
    assert AppSettings(steering_sensitivity=0).validate().steering_sensitivity == 0.25

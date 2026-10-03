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


def test_nonfinite_settings_are_rejected_and_corrupt_file_loads_safely(tmp_path):
    import pytest
    for value in (float('nan'), float('inf'), float('-inf')):
        with pytest.raises(ValueError):
            AppSettings(throttle_limit=value).validate()
    path = tmp_path / 'bad.json'
    path.write_text('{"throttle_limit": NaN}')
    assert load_settings(path).throttle_limit == .25


def test_target_rejects_hostnames_and_nonunicast_addresses():
    import pytest
    for address in ('evil.example', '0.0.0.0', '255.255.255.255', '224.0.0.1', '127.0.0.1:80'):
        with pytest.raises(ValueError):
            AppSettings(target_host=address).validate()


def test_drive_sensitivity_saved_independently_and_legacy_default(tmp_path):
    path = tmp_path / 'settings.json'
    save_settings(AppSettings(steering_sensitivity=.75, drive_sensitivity=.4), path)
    settings = load_settings(path)
    assert settings.drive_sensitivity == .4
    assert settings.steering_sensitivity == .75
    assert settings.throttle_limit == .25
    assert AppSettings(drive_sensitivity=0).validate().drive_sensitivity == .25
    path.write_text('{"settings_version":2,"steering_sensitivity":0.5}')
    assert load_settings(path).drive_sensitivity == 1

from pathlib import Path
from pctelerc.config import AppSettings, load_settings, save_settings

def test_settings_round_trip(tmp_path: Path):
    path=tmp_path/"settings.json"
    save_settings(AppSettings(target_host="192.168.4.1",throttle_limit=.4,steering_sensitivity=.65,steering_channel=2),path)
    loaded=load_settings(path)
    assert loaded.target_host=="192.168.4.1" and loaded.throttle_limit==.4 and loaded.steering_sensitivity==.65 and loaded.steering_channel==2

def test_settings_clamp_invalid_values():
    s=AppSettings(listen_port=99999,throttle_limit=3,deadzone=-1,steering_channel=20).validate()
    assert s.listen_port==65535 and s.throttle_limit==1.0 and s.deadzone==0.0 and s.steering_channel==8


def test_sensitivity_clamps_to_safe_ui_range():
    assert AppSettings(steering_sensitivity=5).validate().steering_sensitivity == 1.0
    assert AppSettings(steering_sensitivity=0).validate().steering_sensitivity == 0.25

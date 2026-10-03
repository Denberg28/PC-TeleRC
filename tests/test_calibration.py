import pytest
from pctelerc.calibration import CalibrationError, build_calibration, detect_steering

def test_separate_pedal_calibration_detects_axes_and_direction():
    result=build_calibration({
        "neutral": (0.0,1.0,1.0,0.0),
        "left": (-1.0,1.0,1.0,0.0),
        "right": (1.0,1.0,1.0,0.0),
        "throttle": (0.0,-1.0,1.0,0.0),
        "brake": (0.0,1.0,-1.0,0.0),
    },"separate")
    assert (result.steer_axis,result.invert_steer)==(0,False)
    assert (result.throttle_axis,result.invert_throttle)==(1,False)
    assert (result.brake_axis,result.invert_brake)==(2,False)

def test_reversed_driver_axes_are_inverted():
    result=build_calibration({
        "neutral": (0.0,-1.0,-1.0,0.0),
        "left": (1.0,-1.0,-1.0,0.0),
        "right": (-1.0,-1.0,-1.0,0.0),
        "throttle": (0.0,1.0,-1.0,0.0),
        "brake": (0.0,-1.0,1.0,0.0),
    },"separate")
    assert result.invert_steer and result.invert_throttle and result.invert_brake

def test_combined_pedal_calibration():
    result=build_calibration({
        "neutral": (0.0,0.0,0.0),
        "left": (-1.0,0.0,0.0),
        "right": (1.0,0.0,0.0),
        "forward": (0.0,1.0,0.0),
        "reverse": (0.0,-1.0,0.0),
    },"combined")
    assert result.throttle_axis==1
    assert result.brake_axis==1
    assert not result.invert_throttle

def test_small_steering_motion_is_rejected():
    with pytest.raises(CalibrationError):
        detect_steering((0.0,0.0),(-.1,0.0),(.1,0.0))


def test_samples_on_same_side_of_neutral_are_rejected():
    with pytest.raises(CalibrationError):
        detect_steering((0,), (.2,), (.9,))


def test_nonfinite_calibration_is_rejected():
    with pytest.raises(CalibrationError):
        detect_steering((0,), (float('nan'),), (1,))


def test_unsupported_pedal_range_cannot_silently_map_to_half_throttle():
    from pctelerc.calibration import detect_pedal
    with pytest.raises(CalibrationError, match='axis range'):
        detect_pedal((0,), (1,))

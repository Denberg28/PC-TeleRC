import math
from pctelerc.core import *

def test_axis_deadzone_and_endpoints():
    cfg=AxisConfig(deadzone=.05,expo=0)
    assert shape_axis(.03,cfg)==0 and shape_axis(1,cfg)==1 and shape_axis(-1,cfg)==-1

def test_axis_invert():
    assert shape_axis(.5,AxisConfig(deadzone=0,expo=0,invert=True))==-.5

def test_separate_pedals():
    assert separate_pedals_to_throttle(1,1)==0
    assert separate_pedals_to_throttle(-1,1)==1
    assert separate_pedals_to_throttle(1,-1)==-1

def test_pwm_limit():
    assert normalized_to_pwm(1,.25)==1625
    assert normalized_to_pwm(-1,.25)==1375
    assert normalized_to_pwm(0,1)==1500

def test_link_state_and_control_freshness():
    assert heartbeat_link_state(None,now=10)==LinkState.CONNECTING
    assert heartbeat_link_state(8,now=10,stale_after=3)==LinkState.CONNECTED
    assert heartbeat_link_state(6,now=10,stale_after=3)==LinkState.STALE
    f=ControlFrame(0,0,9.8)
    assert control_is_fresh(f,now=10,stale_after=.35)
    assert not control_is_fresh(f,now=11,stale_after=.35)

def test_combined_pedal_respects_inversion():
    a=combined_pedal_to_throttle(.6,invert=False,deadzone=0); b=combined_pedal_to_throttle(.6,invert=True,deadzone=0)
    assert math.isclose(a,-b)


def test_steering_sensitivity_is_gain():
    assert apply_sensitivity(0.0, 0.5) == 0.0
    assert math.isclose(apply_sensitivity(1.0, 0.5), 0.5)
    assert math.isclose(apply_sensitivity(-1.0, 0.5), -0.5)

def test_lower_sensitivity_reduces_authority_linearly():
    assert math.isclose(apply_sensitivity(0.5, 1.0), 0.5)
    assert math.isclose(apply_sensitivity(0.5, 0.5), 0.25)

def test_sensitivity_is_clamped():
    assert math.isclose(apply_sensitivity(0.5, 5.0), 0.5)
    assert math.isclose(apply_sensitivity(0.5, 0.0), 0.125)

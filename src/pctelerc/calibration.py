from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Sequence

class CalibrationError(ValueError):
    pass

@dataclass(frozen=True)
class CalibrationResult:
    steer_axis: int
    invert_steer: bool
    throttle_axis: int
    invert_throttle: bool
    brake_axis: int
    invert_brake: bool
    pedal_mode: str

def _vectors(*samples: Sequence[float]) -> tuple[tuple[float, ...], ...]:
    if not samples:
        raise CalibrationError("No calibration samples were captured.")
    vectors=tuple(tuple(float(v) for v in sample) for sample in samples)
    size=len(vectors[0])
    if size==0 or any(len(v)!=size for v in vectors):
        raise CalibrationError("Controller axis samples are missing or inconsistent.")
    return vectors

def _best_axis(scores: Iterable[tuple[int,float]], minimum: float, label: str) -> int:
    ordered=sorted(scores,key=lambda item:item[1],reverse=True)
    if not ordered or ordered[0][1] < minimum:
        raise CalibrationError(f"{label} movement was too small. Repeat calibration and move the control through its full travel.")
    return ordered[0][0]

def detect_steering(neutral: Sequence[float], left: Sequence[float], right: Sequence[float], *, minimum_span: float=.60) -> tuple[int,bool]:
    n,l,r=_vectors(neutral,left,right)
    axis=_best_axis(((i,abs(r[i]-l[i])) for i in range(len(n))),minimum_span,"Steering")
    if abs(l[axis]-n[axis]) < .15 or abs(r[axis]-n[axis]) < .15:
        raise CalibrationError("Steering samples do not clearly bracket the neutral position.")
    invert=r[axis] < l[axis]
    return axis,invert

def detect_pedal(neutral: Sequence[float], pressed: Sequence[float], *, excluded: set[int]|None=None, minimum_delta: float=.35) -> tuple[int,bool]:
    n,p=_vectors(neutral,pressed); excluded=excluded or set()
    axis=_best_axis(((i,abs(p[i]-n[i])) for i in range(len(n)) if i not in excluded),minimum_delta,"Pedal")
    # Separate-pedal conversion expects released ~= +1 and pressed ~= -1.
    invert=p[axis] > n[axis]
    return axis,invert

def detect_combined_pedal(neutral: Sequence[float], forward: Sequence[float], reverse: Sequence[float], *, excluded: set[int]|None=None, minimum_span: float=.60) -> tuple[int,bool]:
    n,f,r=_vectors(neutral,forward,reverse); excluded=excluded or set()
    axis=_best_axis(((i,abs(f[i]-r[i])) for i in range(len(n)) if i not in excluded),minimum_span,"Combined pedal")
    if abs(f[axis]-n[axis]) < .15 or abs(r[axis]-n[axis]) < .15:
        raise CalibrationError("Combined-pedal samples do not clearly bracket neutral.")
    # Combined conversion expects forward to be positive.
    invert=f[axis] < r[axis]
    return axis,invert

def build_calibration(captures: dict[str,Sequence[float]], pedal_mode: str) -> CalibrationResult:
    neutral=captures["neutral"]
    steer_axis,invert_steer=detect_steering(neutral,captures["left"],captures["right"])
    if pedal_mode=="combined":
        throttle_axis,invert_throttle=detect_combined_pedal(neutral,captures["forward"],captures["reverse"],excluded={steer_axis})
        return CalibrationResult(steer_axis,invert_steer,throttle_axis,invert_throttle,throttle_axis,False,"combined")
    throttle_axis,invert_throttle=detect_pedal(neutral,captures["throttle"],excluded={steer_axis})
    brake_axis,invert_brake=detect_pedal(neutral,captures["brake"],excluded={steer_axis,throttle_axis})
    return CalibrationResult(steer_axis,invert_steer,throttle_axis,invert_throttle,brake_axis,invert_brake,"separate")

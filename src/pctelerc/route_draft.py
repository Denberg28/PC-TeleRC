"""Bounded, command-free native draft decoding shared by storage and import."""
import json
import math
from .mission_plan import parse_text

MAX_BYTES = 120000


def location(value):
    return (isinstance(value, (list, tuple)) and len(value) == 2
        and all(type(v) in (int, float) and math.isfinite(v) for v in value)
        and -85 <= value[0] <= 85 and -180 <= value[1] <= 180
        and not (abs(value[0]) < 1e-7 and abs(value[1]) < 1e-7))


def decode(text):
    if len(text.encode('utf-8')) > MAX_BYTES:
        raise ValueError('Draft exceeds size limit')
    data = json.loads(text)
    if not isinstance(data, dict) or type(data.get('version')) is not int or data['version'] != 1:
        raise ValueError('Unsupported draft version')
    wpl = data.get('wpl')
    if wpl is not None:
        if not isinstance(wpl, str):
            raise ValueError('Invalid imported route')
        parse_text(wpl)
    points = data.get('points', [])
    if not isinstance(points, list) or len(points) > 60:
        raise ValueError('Draft exceeds point limit')
    restored = []
    for point in points:
        if not isinstance(point, list) or not 3 <= len(point) <= 5 or not location(point[:2]):
            raise ValueError('Invalid draft location')
        actions = point[2]
        if (not isinstance(actions, list) or len(actions) > 3
            or any(not isinstance(a, list) or len(a) != 2
                or type(a[0]) is not int or a[0] not in range(3) or type(a[1]) is not bool for a in actions)
            or len({a[0] for a in actions}) != len(actions)):
            raise ValueError('Invalid draft actions')
        kind = point[3] if len(point) > 3 else 'go'
        seconds = point[4] if len(point) > 4 else 5
        if kind not in ('go', 'hold', 'rth') or type(seconds) is not int or not 2 <= seconds <= 10:
            raise ValueError('Invalid map action')
        restored.append([*point[:3], kind, seconds])
    home = data.get('home')
    if home is not None and not location(home):
        raise ValueError('Invalid planned home')
    returns = [i for i, p in enumerate(restored) if p[3] == 'rth']
    if returns and (returns != [len(restored)-1] or home is None
        or restored[-1][:2] != home or restored[-1][2]):
        raise ValueError('Invalid return to planned home')
    bindings = data.get('functions', [[0,1100,1900] for _ in range(3)])
    if (not isinstance(bindings, list) or len(bindings) != 3
        or any(not isinstance(row, list) or len(row) != 3
            or any(type(v) is not int for v in row)
            or not 0 <= row[0] <= 16 or not 1000 <= row[1] <= 2000
            or not 1000 <= row[2] <= 2000 for row in bindings)):
        raise ValueError('Invalid function bindings')
    speed = data.get('speed', 0.5)
    if type(speed) not in (int, float) or not math.isfinite(speed) or not 0.1 <= speed <= 3:
        raise ValueError('Invalid draft speed')
    return dict(version=1, wpl=wpl, points=restored, home=home, functions=bindings, speed=speed)

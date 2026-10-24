"""Read-only identification of supported mission BASE USB capabilities."""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class FirmwareProfile:
    version: str
    family: str
    relays: int
    dynamic_routes: bool = False

    @property
    def description(self):
        route = (f"automatic routes, up to {self.relays} relays" if self.dynamic_routes
                 else f"{self.relays} fixed relays" if self.relays else "direct")
        return f"{self.family} {self.version} · {route}"


def mission_capabilities(data):
    """Keep the released TM2 API distinct from the board's component version."""
    try:
        if not 0 < len(data) <= 100:
            raise ValueError
        fields = data.decode('ascii').split(';')
        if fields.pop(0) != 'TM2':
            raise ValueError
        values = {}
        for field in fields:
            key, value = field.split('=')
            if key in values or key not in {'fw', 'relays', 'mask', 'unified'}:
                raise ValueError
            values[key] = value
        if values.get('fw') != '0.2.0':
            raise ValueError
        if not all(re.fullmatch('[0-9]{1,5}', values[k]) for k in ('relays', 'mask')):
            raise ValueError
        relays, mask = int(values['relays']), int(values['mask'])
        if relays not in (0, 1, 2) or not 0 <= mask <= 65535 or mask & 0xF0:
            raise ValueError
        unified = values.get('unified')
        if unified is not None and unified not in ('0.3.0', '0.4.0'):
            raise ValueError
        profile = FirmwareProfile(unified or '0.2.0',
            'Scalable LoRa' if unified == '0.4.0' else 'Unified LoRa' if unified else 'Mission',
            relays, unified == '0.4.0')
        return dict(relays=relays, mask=mask, firmware='0.2.0'), profile
    except (UnicodeError, ValueError, KeyError):
        raise RuntimeError('Incompatible mission BASE capabilities; use a matching TeleRC firmware set') from None


def route_interrupted(text):
    """These notices mean the BASE discarded work or invalidated its route."""
    return text.startswith(('Route lost;', 'Route learned;', 'Discovering nodes;',
        'Route too slow for manual;', 'RF fault;', 'RF OFF;', 'Command queue full'))

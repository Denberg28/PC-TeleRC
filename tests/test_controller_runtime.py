import sys
import time
from types import SimpleNamespace

from pctelerc.controller import WheelService


def test_pygame_ce_controller_stays_connected_and_handles_removal(monkeypatch):
    # Match the pinned pygame-ce API: JoystickType has no get_attached().
    class Joystick:
        def init(self): pass
        def get_instance_id(self): return 17
        def get_name(self): return 'Test wheel'
        def get_guid(self): return 'wheel-guid'
        def get_numaxes(self): return 3
        def get_numbuttons(self): return 2
        def get_axis(self, index): return 0.0

    devices = [Joystick()]
    events = []
    def poll():
        result = list(events)
        events.clear()
        return result
    subsystem = SimpleNamespace(init=lambda: None, quit=lambda: None)
    pygame = SimpleNamespace(
        display=subsystem, JOYDEVICEREMOVED=1542,
        event=SimpleNamespace(get=poll),
        joystick=SimpleNamespace(init=lambda: None, quit=lambda: None,
                                 get_count=lambda: len(devices), Joystick=lambda i: devices[i]),
    )
    monkeypatch.setitem(sys.modules, 'pygame', pygame)
    service = WheelService()
    service.start()
    try:
        deadline = time.monotonic() + 2
        while not service.snapshot().connected and time.monotonic() < deadline:
            time.sleep(.01)
        first = service.snapshot()
        assert first.connected, first.error
        time.sleep(.15)  # Exercise multiple polls after acquisition.
        next_frame = service.snapshot()
        assert next_frame.connected, next_frame.error
        assert next_frame.frame.timestamp > first.frame.timestamp
        assert next_frame.generation == first.generation
        devices.clear()
        events.append(SimpleNamespace(type=1542, instance_id=17))
        deadline = time.monotonic() + 1
        while service.snapshot().connected and time.monotonic() < deadline:
            time.sleep(.01)
        assert not service.snapshot().connected
        assert service.snapshot().generation > first.generation
    finally:
        service.stop()

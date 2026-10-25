"""Planning-only route model; execution always uses a validated immutable WPL snapshot."""

from dataclasses import dataclass, field
import math
from pathlib import Path
import tempfile

from .mission_protocol.client import read_plan


@dataclass(frozen=True)
class Function:
    channel: int = 0
    off: int = 1100
    on: int = 1900

    def validate(self):
        # M5-M8 are reserved in the existing TeleRC wiring. Other motor outputs
        # must also be excluded by the operator and the firmware permission mask.
        if self.channel not in range(1, 17) or self.channel in range(5, 9):
            raise ValueError("Assign a dedicated auxiliary output outside M5–M8")
        if (
            not 1000 <= self.off <= 2000
            or not 1000 <= self.on <= 2000
            or self.off == self.on
        ):
            raise ValueError("Use distinct ON/OFF values between 1000 and 2000 µs")


@dataclass
class Point:
    latitude: float
    longitude: float
    actions: list[tuple[int, bool]] = field(default_factory=list)
    kind: str = "go"
    hold_seconds: int = 5


@dataclass
class Plan:
    points: list[Point] = field(default_factory=list)
    functions: list[Function] = field(
        default_factory=lambda: [Function() for _ in range(3)]
    )
    speed: float = 0.5
    home: tuple[float, float] | None = None

    def validate(self):
        if (
            not 1 <= len(self.points) <= 60
            or not math.isfinite(self.speed)
            or not 0 < self.speed <= 3
        ):
            raise ValueError("Use 1–60 points and speed above 0, up to 3 m/s")
        used = set()
        final = {}
        if self.home is not None and (
            len(self.home) != 2 or not all(math.isfinite(v) for v in self.home)
            or not -85 <= self.home[0] <= 85 or not -180 <= self.home[1] <= 180
            or (abs(self.home[0]) < 1e-7 and abs(self.home[1]) < 1e-7)
        ):
            raise ValueError("Invalid planned home")
        for index, point in enumerate(self.points):
            if point.kind not in ("go", "hold", "rth"):
                raise ValueError("Unknown map action")
            if point.kind == "hold" and (type(point.hold_seconds) is not int or not 2 <= point.hold_seconds <= 10):
                raise ValueError("Hold must be 2–10 seconds")
            if point.kind == "rth" and (
                index != len(self.points)-1 or self.home is None
                or (point.latitude, point.longitude) != tuple(self.home) or point.actions
            ):
                raise ValueError("Return to planned home must be the final point and match Home")
            if (
                not all(math.isfinite(x) for x in (point.latitude, point.longitude))
                or not -85 <= point.latitude <= 85
                or not -180 <= point.longitude <= 180
                or (abs(point.latitude) < 1e-7 and abs(point.longitude) < 1e-7)
            ):
                raise ValueError("Invalid location; review the map coordinates")
            if len(point.actions) > 3 or len({a[0] for a in point.actions}) != len(
                point.actions
            ):
                raise ValueError("Each point can contain one action per function")
            for function, on in point.actions:
                if (
                    type(function) is not int
                    or function not in range(3)
                    or type(on) is not bool
                ):
                    raise ValueError("Invalid function event")
                used.add(function)
                final[function] = on
        channels = []
        for i in sorted(used):
            self.functions[i].validate()
            channels.append(self.functions[i].channel)
            if final[i]:
                raise ValueError(f"F{i + 1} needs a final OFF event")
        if len(set(channels)) != len(channels):
            raise ValueError("Each used function needs a unique output")
        return used

    def wpl(self):
        used = self.validate()
        rows = ["QGC WPL 110"]

        def row(command, frame, params, lat=0, lon=0):
            rows.append(
                "\t".join(
                    map(
                        str, [len(rows) - 1, 0, frame, command, *params, lat, lon, 0, 1]
                    )
                )
            )

        # Home placeholder is plan metadata, never a fabricated live GPS fix.
        first = self.points[0]
        row(16, 3, [0, 0, 0, 0], first.latitude, first.longitude)

        def stopped_window(actions, initial=False):
            # Rover 4.6.3 starts the first DO/CONDITION while loading the next
            # NAV command. Put the settling/action block BEFORE NAV_DELAY so
            # that NAV_DELAY is the active stopped command while actions run.
            row(112, 2, [1, 0, 0, 0])
            if initial:
                row(178, 2, [1, self.speed, -1, 0])
            for channel, pwm in actions:
                row(183, 2, [channel, pwm, 0, 0])
            row(93, 2, [4, -1, -1, -1])

        stopped_window(
            [(self.functions[i].channel, self.functions[i].off) for i in sorted(used)],
            initial=True,
        )
        for point in self.points:
            row(
                16,
                3,
                [1 if point.actions else 0, 0, 0, 0],
                point.latitude,
                point.longitude,
            )
            if point.actions:
                stopped_window(
                    [
                        (
                            self.functions[i].channel,
                            self.functions[i].on if on else self.functions[i].off,
                        )
                        for i, on in point.actions
                    ]
                )
            if point.kind == "hold":
                row(93, 2, [point.hold_seconds, -1, -1, -1])
        if used:
            stopped_window(
                [
                    (self.functions[i].channel, self.functions[i].off)
                    for i in sorted(used)
                ]
            )
        if len(rows) > 201:
            raise ValueError("Plan exceeds 200 mission rows; reduce points/actions")
        return "\n".join(rows) + "\n"


def parse_text(text):
    # Reuse the commissioning client's authoritative validation unchanged.
    with tempfile.TemporaryDirectory(prefix="pctelerc-plan-") as folder:
        path = Path(folder) / "route.waypoints"
        path.write_text(text, encoding="utf-8")
        return read_plan(path)

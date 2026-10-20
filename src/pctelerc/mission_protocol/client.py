#!/usr/bin/env python3
"""Upload, read back and optionally start an ArduRover mission. Never arms."""

import hashlib
import json
import math
import os
from pathlib import Path
import time

os.environ["MAVLINK20"] = "1"
from pymavlink import mavutil

TIMEOUT = 4.0
RETRIES = 5
MAX_ITEMS = 200


def read_plan(path):
    lines = Path(path).read_text().strip().splitlines()
    if not lines or lines[0].strip() != "QGC WPL 110":
        raise ValueError("Export a QGC WPL 110 .waypoints file from Mission Planner")
    items = []
    for line in lines[1:]:
        if not line.strip():
            continue
        cols = line.split()
        if len(cols) != 12:
            raise ValueError("Expected 12 columns per mission row")
        seq, current, frame, command = map(int, cols[:4])
        values = list(map(float, cols[4:11]))
        auto = int(cols[11])
        if seq != len(items) or auto != 1 or not all(math.isfinite(x) for x in values):
            raise ValueError("Use sequential rows, finite values and autocontinue=1")
        if command not in (16, 93, 112, 178, 183):
            raise ValueError(f"Command {command} is outside this candidate allowlist")
        if seq == 0 and command != 16:
            raise ValueError("Row 0 must be the ArduPilot home placeholder")
        if command == 16:
            if frame not in (0, 3, 5, 6) or abs(values[4]) > 90 or abs(values[5]) > 180:
                raise ValueError("Waypoint requires valid global coordinates/frame")
            if seq and (abs(values[4]) < 1e-7 and abs(values[5]) < 1e-7):
                raise ValueError("Refusing navigation to zero latitude AND longitude")
            frame = 5 if frame in (0, 5) else 6
            x, y = round(values[4] * 1e7), round(values[5] * 1e7)
        else:
            if frame not in (0, 2) or values[4] != 0 or values[5] != 0:
                raise ValueError(
                    "Non-position commands require MISSION/GLOBAL frame and zero x/y"
                )
            frame = 2
            x = y = 0
        if command == 93 and (not 2 <= values[0] <= 10 or values[1:4] != [-1, -1, -1]):
            raise ValueError("NAV_DELAY must be relative, 2..10 seconds")
        if command == 112 and (not 0.5 <= values[0] <= 5 or any(values[1:4])):
            raise ValueError("CONDITION_DELAY must be 0.5..5 seconds")
        if command == 178 and (
            values[0] != 1 or not 0 < values[1] <= 3 or values[2] != -1
        ):
            raise ValueError(
                "Speed command must use ground speed 0..3 m/s and throttle=-1"
            )
        if command == 183 and (
            values[0] != int(values[0])
            or not 1 <= values[0] <= 16
            or not 1000 <= values[1] <= 2000
        ):
            raise ValueError("Invalid auxiliary servo command")
        items.append(
            dict(
                seq=seq,
                frame=frame,
                command=command,
                params=values[:4],
                x=x,
                y=y,
                z=values[6],
                autocontinue=1,
            )
        )
    if not 2 <= len(items) <= MAX_ITEMS:
        raise ValueError("Use a home row plus 1..199 mission items")
    validate_actions(items)
    return items


def validate_actions(items):
    """Require each servo block to run with a relative stopped NAV_DELAY active."""
    for index, item in enumerate(items[1:], 1):
        if item["command"] != 183:
            continue
        start = index
        while start > 1 and items[start - 1]["command"] not in (16, 93):
            start -= 1
        block = items[start:index]
        if not block or block[0]["command"] != 112:
            raise ValueError(
                "Servo event needs a settling condition before its stopped NAV_DELAY; rebuild legacy F plans"
            )
        end = index + 1
        while end < len(items) and items[end]["command"] not in (16, 93):
            end += 1
        if (
            end == len(items)
            or items[end]["command"] != 93
            or block[0]["params"][0] + 1 >= items[end]["params"][0]
        ):
            raise ValueError(
                "Servo event must precede a sufficiently long stopped NAV_DELAY"
            )


def fingerprint(items, rover):
    # Home is FC metadata; compare and hash the flown/action rows (1 onward).
    return hashlib.sha256(
        json.dumps(
            {"rover": rover, "items": items[1:]}, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def compare(expected, actual):
    if len(expected) != len(actual):
        raise RuntimeError("Mission readback count mismatch")
    for a, b in zip(expected[1:], actual[1:]):
        for key in ("seq", "command", "autocontinue", "x", "y"):
            if a[key] != b[key]:
                raise RuntimeError(
                    f"Readback differs at row {a['seq']}, {key}: {a[key]} vs {b[key]}"
                )
        fa, fb = a["frame"], b["frame"]
        norm = lambda f: 5 if f in (0, 5) else 6 if f in (3, 6) else f
        # ArduRover 4.6.3 returns GLOBAL for non-position mission commands.
        # These carry zero x/y; MISSION and GLOBAL are the same stored action.
        action_frame = a["command"] != 16 and fa in (0, 2) and fb in (0, 2)
        if not action_frame and norm(fa) != norm(fb):
            raise RuntimeError(f"Readback frame mismatch at row {a['seq']}")
        for x, y in zip(a["params"] + [a["z"]], b["params"] + [b["z"]]):
            if not math.isfinite(y) or not math.isclose(
                x, y, rel_tol=1e-6, abs_tol=1e-4
            ):
                raise RuntimeError(f"Readback parameter mismatch at row {a['seq']}")


def from_message(m):
    integer = m.get_type() == "MISSION_ITEM_INT"
    return dict(
        seq=m.seq,
        frame=m.frame,
        command=m.command,
        params=[m.param1, m.param2, m.param3, m.param4],
        x=int(m.x) if integer else round(m.x * 1e7) if m.command == 16 else round(m.x),
        y=int(m.y) if integer else round(m.y * 1e7) if m.command == 16 else round(m.y),
        z=m.z,
        autocontinue=m.autocontinue,
    )


class Client:
    def __init__(self, endpoint, rover, link=None):
        self.log = lambda *args: None
        self.check = lambda: None
        self.rover = rover
        self.link = (
            link
            if link is not None
            else mavutil.mavlink_connection(
                endpoint, source_system=255, source_component=190, dialect="common"
            )
        )
        self.last_tx = -10
        self.hb = None
        self.hb_at = 0
        self.start_attempted = False

    def beat(self):
        self.check()
        now = time.monotonic()
        if now - self.last_tx >= 1:
            self.link.mav.heartbeat_send(6, 8, 0, 0, 4)
            self.last_tx = now

    def recv(self, types, timeout=TIMEOUT):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            self.check()
            if self.hb is not None and time.monotonic() - self.hb_at > 5:
                raise RuntimeError(
                    "FC heartbeat lost during mission transaction; reconnect manually"
                )
            self.beat()
            m = self.link.recv_match(blocking=False)
            if m is None:
                time.sleep(0.005)
                continue
            if m.get_srcSystem() != self.rover or m.get_srcComponent() != 1:
                continue
            if m.get_type() == "HEARTBEAT":
                if m.type != 10 or m.autopilot != 3:
                    continue
                self.hb, self.hb_at = m, time.monotonic()
            if m.get_type() in (
                "MISSION_REQUEST",
                "MISSION_REQUEST_INT",
                "MISSION_ACK",
                "MISSION_COUNT",
                "MISSION_ITEM",
                "MISSION_ITEM_INT",
            ):
                if (
                    getattr(m, "mission_type", 0) != 0
                    or m.target_system != 255
                    or m.target_component != 190
                ):
                    continue
            if m.get_type() in types:
                return m
        return None

    def heartbeat(self, disarmed=False, armed=False):
        # Require a newly received heartbeat, not a retained cached value.
        m = self.recv(["HEARTBEAT"], 12)
        if m is None or m.type != 10 or m.autopilot != 3:
            raise RuntimeError("No fresh addressed ArduRover heartbeat")
        if disarmed and (m.base_mode & 128 or m.custom_mode not in (0, 4)):
            raise RuntimeError("Upload requires DISARMED MANUAL/HOLD")
        if armed and (not m.base_mode & 128 or m.custom_mode not in (0, 4)):
            raise RuntimeError(
                "Start requires ARMED MANUAL/HOLD; arm with your RC transmitter"
            )
        return m

    def item_send(self, item, legacy=False):
        # MAVLink mission protocol requires INT even for deprecated
        # MISSION_REQUEST. Float replies would change stored coordinates.
        s = item
        self.link.mav.mission_item_int_send(
            self.rover,
            1,
            s["seq"],
            s["frame"],
            s["command"],
            0,
            1,
            *s["params"],
            s["x"],
            s["y"],
            s["z"],
            0,
        )

    def parameter(self, name, retries=3):
        for _ in range(retries):
            self.link.mav.param_request_read_send(
                self.rover, 1, name.encode("ascii"), -1
            )
            end = time.monotonic() + TIMEOUT
            while time.monotonic() < end:
                m = self.recv(["PARAM_VALUE"], 0.5)
                if m is not None:
                    pid = (
                        m.param_id.decode("ascii")
                        if isinstance(m.param_id, bytes)
                        else m.param_id
                    )
                    if pid.rstrip("\x00") == name:
                        return m.param_value
        raise RuntimeError(f"Cannot verify FC parameter {name}; do not start")

    def loss_policy(self, continue_in_auto=False, min_timeout=1):
        enabled = self.parameter("FS_GCS_ENABLE")
        action = self.parameter("FS_ACTION")
        expected = 2 if continue_in_auto else 1
        if enabled != expected or action != 2:
            raise RuntimeError(
                f"Expected FS_GCS_ENABLE={expected}, FS_ACTION=2 (HOLD). FC reports {enabled}, {action}. Configure FC deliberately before retrying."
            )
        try:
            gcs = self.parameter("MAV_GCS_SYSID", retries=1)
        except RuntimeError:
            gcs = self.parameter("SYSID_MYGCS", retries=1)
        if gcs != 255:
            raise RuntimeError("FC GCS system ID must match this client (255)")
        try:
            timeout = self.parameter("FS_GCS_TIMEOUT", retries=1)
        except RuntimeError:
            timeout = self.parameter("FS_TIMEOUT", retries=1)
        if not min_timeout <= timeout <= 10:
            raise RuntimeError(
                f"FC GCS timeout {timeout} is outside this commissioning profile ({min_timeout}..10 seconds)"
            )
        self.log(
            "Verified FC loss policy: "
            + (
                "CONTINUE onboard mission in AUTO; remote HOLD unavailable without a link"
                if continue_in_auto
                else f"HOLD after configured {timeout:g}s GCS timeout"
            )
        )

    def upload(self, items):
        validate_actions(items)
        self.heartbeat(disarmed=True)
        self.link.mav.mission_count_send(self.rover, 1, len(items), 0)
        sent = set()
        last = None
        attempts = 0
        deadline = time.monotonic() + max(60, len(items) * TIMEOUT * 3)
        while time.monotonic() < deadline:
            m = self.recv(["MISSION_REQUEST_INT", "MISSION_REQUEST", "MISSION_ACK"])
            if self.hb and (
                time.monotonic() - self.hb_at > 5
                or self.hb.base_mode & 128
                or self.hb.custom_mode not in (0, 4)
            ):
                raise RuntimeError("FC state changed or heartbeat stale during upload")
            if m is None:
                attempts += 1
                if attempts > RETRIES:
                    raise RuntimeError(
                        "Upload timed out; mission state UNKNOWN; do not start"
                    )
                if last is None:
                    self.link.mav.mission_count_send(self.rover, 1, len(items), 0)
                else:
                    self.item_send(items[last[0]], last[1])
                continue
            if m.get_type() == "MISSION_ACK":
                if m.type != 0 or len(sent) != len(items):
                    raise RuntimeError(
                        f"Upload not accepted or incomplete (ACK {m.type})"
                    )
                return
            if not 0 <= m.seq < len(items):
                raise RuntimeError("FC requested an out-of-range mission item")
            attempts = 0
            last = (m.seq, m.get_type() == "MISSION_REQUEST")
            self.item_send(items[m.seq], last[1])
            sent.add(m.seq)
            self.log(f"Upload row {m.seq}/{len(items) - 1}")
        raise RuntimeError("Upload deadline exceeded; do not start")

    def download(self):
        count = None
        for _ in range(RETRIES):
            self.link.mav.mission_request_list_send(self.rover, 1, 0)
            m = self.recv(["MISSION_COUNT"])
            if m is not None:
                count = m.count
                break
        if count is None or not 2 <= count <= MAX_ITEMS:
            raise RuntimeError("Invalid or missing mission readback count")
        result = []
        for seq in range(count):
            found = None
            for _ in range(RETRIES):
                self.link.mav.mission_request_int_send(self.rover, 1, seq, 0)
                m = self.recv(["MISSION_ITEM_INT", "MISSION_ITEM"])
                if m is not None and m.seq == seq:
                    found = from_message(m)
                    break
            if found is None:
                raise RuntimeError(f"Readback row {seq} timed out; do not start")
            result.append(found)
        self.link.mav.mission_ack_send(self.rover, 1, 0, 0)
        return result

    def hold(self):
        self.heartbeat()
        # HOLD may be repeated; a timeout is never a confirmed stop.
        for _ in range(RETRIES):
            self.link.mav.command_long_send(self.rover, 1, 176, 0, 1, 4, 0, 0, 0, 0, 0)
            end = time.monotonic() + TIMEOUT
            while time.monotonic() < end:
                m = self.recv(["HEARTBEAT", "COMMAND_ACK"], 0.3)
                if m is not None and m.get_type() == "HEARTBEAT" and m.custom_mode == 4:
                    self.log(
                        "HOLD confirmed by fresh FC heartbeat. Vehicle motion still requires visual confirmation."
                    )
                    return
        raise RuntimeError("HOLD UNCONFIRMED: use RC takeover/physical stop")

    def start_once(self):
        if self.start_attempted:
            raise RuntimeError(
                "START already attempted; re-upload disarmed before another start"
            )
        self.heartbeat(armed=True)
        self.check()
        self.start_attempted = True
        self.link.mav.command_long_send(self.rover, 1, 300, 0, 0, 0, 0, 0, 0, 0, 0)
        # Never automatically retry START. A missing ACK is UNKNOWN, not failure.
        accepted = False
        end = time.monotonic() + 12
        while time.monotonic() < end:
            m = self.recv(["COMMAND_ACK", "HEARTBEAT"], 0.5)
            if m is None:
                continue
            if m.get_type() == "COMMAND_ACK" and m.command == 300:
                if m.result not in (0, 5):
                    raise RuntimeError(
                        f"FC rejected START ({m.result}); inspect GPS/EKF and FC messages. START is not retried."
                    )
                accepted |= m.result == 0
            if (
                m.get_type() == "HEARTBEAT"
                and m.custom_mode == 10
                and m.base_mode & 128
                and accepted
            ):
                self.log("START ACK accepted and fresh ARMED AUTO heartbeat received.")
                return
        raise RuntimeError(
            "START state UNKNOWN; inspect live FC mode; do not retry blindly"
        )

"""Optional real Rover-4.6.3 SITL action-timing acceptance; never connects to hardware.

The harness starts its own temporary loopback-only SITL instance, configures only
that instance and explicitly arms it for simulation. Production mission code never
arms. Supply a freshly built Rover-4.6.3 SITL binary and rover defaults file.
"""

import argparse
import json
import math
from pathlib import Path
import socket
import subprocess
import tempfile
import time

from pctelerc.mission_plan import Plan, Point, Function, parse_text
from pctelerc.mission_protocol.client import Client, compare


def run(binary, defaults, report):
    binary = Path(binary).resolve()
    defaults = Path(defaults).read_text()
    if not binary.is_file():
        raise ValueError("Build the Rover-4.6.3 SITL binary first")
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    result = dict(passed=False, simulation_only=True, events=[])
    with tempfile.TemporaryDirectory(prefix="pctelerc-sitl-") as folder:
        folder = Path(folder)
        params = folder / "defaults.parm"
        params.write_text(
            defaults
            + "\nFS_GCS_ENABLE 1\nFS_ACTION 2\nFS_TIMEOUT 5\nSYSID_MYGCS 255\nSERVO9_FUNCTION 0\nSERVO9_MIN 1000\nSERVO9_MAX 2000\nWP_SPEED 0.5\nWP_RADIUS 0.5\n"
        )
        log = (folder / "sitl.log").open("w")
        child = subprocess.Popen(
            [
                str(binary),
                "--model",
                "rover",
                "--home",
                "13.6,123.2,20,0",
                "--speedup",
                "1",
                "--defaults",
                str(params),
                "--serial0",
                f"tcp:{port}",
            ],
            cwd=folder,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        c = None
        try:
            end = time.monotonic() + 30
            while time.monotonic() < end:
                if child.poll() is not None:
                    raise RuntimeError("SITL exited before connection")
                try:
                    c = Client(f"tcp:127.0.0.1:{port}", 1)
                    break
                except OSError:
                    time.sleep(0.1)
            if c is None:
                raise RuntimeError("SITL did not open its loopback port")
            c.log = lambda *args: print(*args, flush=True)
            original_recv = c.link.recv_match
            result["status"] = []

            def receive(*args, **kwargs):
                message = original_recv(*args, **kwargs)
                if message is not None and message.get_type() == "STATUSTEXT":
                    text = str(message.text)
                    result["status"].append(text)
                    print(text, flush=True)
                return message

            c.link.recv_match = receive
            c.heartbeat()
            # Explicit SIMULATION setup: set HOLD and request telemetry, not app behavior.
            c.link.mav.command_long_send(1, 1, 176, 0, 1, 4, 0, 0, 0, 0, 0)
            for message in (24, 33, 36):
                c.link.mav.command_long_send(
                    1, 1, 511, 0, message, 100000, 0, 0, 0, 0, 0
                )
            p = Plan(
                [
                    Point(13.600045, 123.2, [(0, True)]),
                    Point(13.60009, 123.2, [(0, False)]),
                ]
            )
            p.functions[0] = Function(9)
            items = parse_text(p.wpl())
            c.heartbeat(disarmed=True)
            c.loss_policy(min_timeout=3)
            c.upload(items)
            compare(items, c.download())
            result["upload_readback"] = True
            end = time.monotonic() + 75
            gps = False
            gps_since = None
            while time.monotonic() < end:
                m = c.recv(["GPS_RAW_INT", "HEARTBEAT"], 0.3)
                if m is not None and m.get_type() == "GPS_RAW_INT" and m.fix_type >= 3:
                    gps = True
                    if gps_since is None:
                        gps_since = time.monotonic()
                if gps and gps_since is not None and time.monotonic() - gps_since >= 20:
                    # Only this spawned virtual instance is explicitly armed.
                    c.link.mav.command_long_send(1, 1, 400, 0, 1, 0, 0, 0, 0, 0, 0)
                    h = c.recv(["HEARTBEAT"], 1.2)
                    if h is not None and h.base_mode & 128:
                        break
            else:
                raise RuntimeError("SITL did not pass normal arming checks")
            # HOLD can arm before AUTO's navigation filter is settled. Keep
            # observing this virtual FC; do not bypass its normal mode checks.
            settle_end = time.monotonic() + 15
            while time.monotonic() < settle_end:
                c.recv(["HEARTBEAT", "GLOBAL_POSITION_INT"], 0.3)
            c.start_once()
            result["start_ack_auto"] = True
            position = None
            previous = None
            seen_on = False
            end = time.monotonic() + 90
            while time.monotonic() < end:
                m = c.recv(
                    ["GLOBAL_POSITION_INT", "SERVO_OUTPUT_RAW", "HEARTBEAT"], 0.3
                )
                if m is None:
                    continue
                if m.get_type() == "GLOBAL_POSITION_INT":
                    position = (m.lat / 1e7, m.lon / 1e7, math.hypot(m.vx, m.vy) / 100)
                if m.get_type() != "SERVO_OUTPUT_RAW" or position is None:
                    continue
                pwm = m.servo9_raw
                if pwm == previous:
                    continue
                previous = pwm
                if pwm not in (1100, 1900):
                    continue
                event = dict(
                    pwm=pwm,
                    latitude=position[0],
                    longitude=position[1],
                    speed=position[2],
                )
                result["events"].append(event)
                if pwm == 1900:
                    distance = abs(position[0] - p.points[0].latitude) * 111320
                    if distance > 2 or position[2] > 0.2:
                        raise RuntimeError(
                            f"ON outside stopped arrival window: {event}"
                        )
                    seen_on = True
                elif seen_on:
                    distance = abs(position[0] - p.points[1].latitude) * 111320
                    if distance > 2 or position[2] > 0.2:
                        raise RuntimeError(
                            f"OFF outside stopped arrival window: {event}"
                        )
                    result["on_off_at_stopped_points"] = True
                    break
            else:
                raise RuntimeError("SITL did not report the ON then OFF events")
            c.hold()
            result["hold_confirmed"] = True
            result["passed"] = True
        except Exception as exc:
            result["error"] = str(exc)
        finally:
            if c is not None:
                c.link.close()
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
            log.close()
            Path(report).with_suffix(".sitl.log").write_text(
                (folder / "sitl.log").read_text(errors="replace")
            )
            Path(report).write_text(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True)
    parser.add_argument("--defaults", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.binary, args.defaults, args.report))

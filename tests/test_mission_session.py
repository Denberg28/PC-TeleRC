"""Real MAVLink2 and addressed USB frames through the desktop worker (no RF/SITL)."""

from dataclasses import replace
import time
from PySide6.QtWidgets import QApplication
from pymavlink.dialects.v20 import common as mav

from pctelerc.mission_service import MissionService
from pctelerc.mission_plan import Plan, Point, parse_text
from pctelerc.mission_transport import MissionUSB
from pctelerc.mission_protocol.usb_gateway import Decoder, encode


class NativePeer:
    def __init__(self, rover):
        self.rover = rover
        self.incoming = bytearray()
        self.decoder = Decoder()
        self.sender = mav.MAVLink(None, srcSystem=rover, srcComponent=1)
        self.parser = mav.MAVLink(None)
        self.mode = 4
        self.armed = False
        self.items = {}
        self.count = 0
        self.commands = []
        self.last_beat = 0
        self.active = True
        self.parameters = {
            "FS_GCS_ENABLE": 1,
            "FS_ACTION": 2,
            "MAV_GCS_SYSID": 255,
            "FS_GCS_TIMEOUT": 5,
        }
        self.heartbeats = 0

    def send(self, msg):
        self.incoming.extend(encode(self.rover, 1, msg.pack(self.sender)))

    @property
    def in_waiting(self):
        return len(self.incoming)

    @property
    def out_waiting(self):
        return 0

    def write(self, data):
        for rover, kind, raw in self.decoder.feed(data):
            assert rover == self.rover
            if kind == 3:
                assert raw == b"INFO"
                self.incoming.extend(
                    encode(self.rover, 3, b"TM2;fw=0.2.0;relays=0;mask=0")
                )
                continue
            assert kind == 1
            m = self.parser.parse_char(raw)
            name = m.get_type()
            if name == "HEARTBEAT":
                self.heartbeats += 1
            elif name == "PARAM_REQUEST_READ":
                key = m.param_id.rstrip("\x00")
                self.send(
                    mav.MAVLink_param_value_message(
                        key.encode(), self.parameters[key], 9, 4, 0
                    )
                )
            elif name == "MISSION_COUNT":
                self.count = m.count
                self.items = {}
                self.send(mav.MAVLink_mission_request_int_message(255, 190, 0, 0))
            elif name == "MISSION_ITEM_INT":
                self.items[m.seq] = m
                if len(self.items) == self.count:
                    self.send(mav.MAVLink_mission_ack_message(255, 190, 0, 0))
                else:
                    self.send(
                        mav.MAVLink_mission_request_int_message(255, 190, m.seq + 1, 0)
                    )
            elif name == "MISSION_REQUEST_LIST":
                self.send(mav.MAVLink_mission_count_message(255, 190, self.count, 0))
            elif name == "MISSION_REQUEST_INT":
                r = self.items[m.seq]
                self.send(
                    mav.MAVLink_mission_item_int_message(
                        255,
                        190,
                        r.seq,
                        r.frame,
                        r.command,
                        0,
                        1,
                        r.param1,
                        r.param2,
                        r.param3,
                        r.param4,
                        r.x,
                        r.y,
                        r.z,
                        0,
                    )
                )
            elif name == "COMMAND_LONG":
                self.commands.append(m.command)
                if m.command == 300:
                    self.mode = 10
                elif m.command == 176:
                    self.mode = 4
                else:
                    raise AssertionError(f"Forbidden command {m.command}")
                self.send(mav.MAVLink_command_ack_message(m.command, 0, 0, 0, 255, 190))
        return len(data)

    def read(self, n):
        now = time.monotonic()
        if self.active and now - self.last_beat > 0.3:
            self.last_beat = now
            self.send(
                mav.MAVLink_heartbeat_message(
                    10, 3, 129 if self.armed else 1, self.mode, 3, 3
                )
            )
            self.send(
                mav.MAVLink_gps_raw_int_message(
                    0, 3, 136000000, 1232000000, 0, 100, 100, 0, 0, 10
                )
            )
            self.send(
                mav.MAVLink_global_position_int_message(
                    int(now * 1000) & 0xFFFFFFFF,
                    136000000,
                    1232000000,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                )
            )
        d = bytes(self.incoming[:n])
        del self.incoming[:n]
        return d

    def reset_output_buffer(self):
        pass

    def close(self):
        self.active = False


def pump(service, predicate, timeout=10):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        service.pulse()
        QApplication.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Mission condition timed out")


def test_native_usb_worker_upload_start_hold_and_no_replay(qt_application):
    peers = []

    def factory(port, rover):
        from collections import deque
        import threading

        link = MissionUSB.__new__(MissionUSB)
        link.rover = rover
        link.port = NativePeer(rover)
        peers.append(link.port)
        link.gate = threading.RLock()
        link.check = lambda: None
        link.status = lambda text: None
        link.capabilities = None
        link.decoder = Decoder()
        link.messages = deque(maxlen=64)
        link.mav = mav.MAVLink(link, srcSystem=255, srcComponent=190)
        return link

    service = MissionService(factory)
    messages = []
    service.events.message.connect(messages.append)
    items = parse_text(Plan([Point(13.6, 123.2), Point(13.6001, 123.2001)]).wpl())
    service.connect("COM9", 2)
    try:
        pump(service, lambda: service.snapshot.last_heartbeat is not None)
        peer = peers[0]
        assert not peer.commands
        service.submit("upload", items)
        pump(service, lambda: bool(service.verified_digest))
        assert len(peer.items) == len(items) and not peer.commands
        peer.armed = True
        pump(service, lambda: service.snapshot.armed)
        service.submit("start", items)
        pump(service, lambda: peer.commands == [300])
        pump(service, lambda: any("START ACK accepted" in m for m in messages))
        assert peer.mode == 10
        service.hold()
        pump(service, lambda: 176 in peer.commands)
        pump(service, lambda: any("HOLD confirmed" in m for m in messages))
        assert (
            peer.mode == 4
            and peer.commands.count(300) == 1
            and 400 not in peer.commands
        )
        assert not service.verified_digest
    finally:
        assert service.close()
    assert not service.running and len(peers) == 1


def test_stalled_ui_closes_link_and_stops_host_heartbeats(qt_application):
    # Exercise _check in the actual worker while waiting for the first FC heartbeat.
    class QuietLink:
        def __init__(self):
            self.closed = False
            self.count = 0
            self.mav = type(
                "M",
                (),
                {
                    "heartbeat_send": lambda *args: setattr(
                        self, "count", self.count + 1
                    )
                },
            )()

        def recv_match(self, **kwargs):
            return None

        def close(self):
            self.closed = True

    link = QuietLink()
    service = MissionService(lambda port, rover: link)
    service.connect("COM9", 1)
    service.ui_at = time.monotonic() - 3
    service.thread.join(1)
    assert not service.running and link.closed
    n = link.count
    time.sleep(0.05)
    assert link.count == n

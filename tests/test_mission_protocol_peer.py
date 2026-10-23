"""Real pymavlink UDP roundtrip to a small protocol peer, not ArduRover SITL."""

from pathlib import Path
import socket
import sys
import threading
import time

from pymavlink.dialects.v20 import common as mav
import pytest

from pctelerc.mission_protocol import client


class Peer:
    def __init__(self, reject=False):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(0.01)
        self.port = self.sock.getsockname()[1]
        self.parser = mav.MAVLink(None)
        self.sender = mav.MAVLink(None, srcSystem=1, srcComponent=1)
        self.peer = None
        self.stopped = False
        self.error = None
        self.items = {}
        self.count = 0
        self.mode = 4
        self.armed = False
        self.received_commands = []
        self.parameters = {
            "FS_GCS_ENABLE": 1,
            "FS_ACTION": 2,
            "MAV_GCS_SYSID": 255,
            "FS_GCS_TIMEOUT": 5,
        }
        self.reject = reject
        self.drop_count_once = True
        self.drop_read_once = True
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def send(self, m):
        self.sock.sendto(m.pack(self.sender), self.peer)

    def heartbeat(self):
        self.send(
            mav.MAVLink_heartbeat_message(
                10, 3, 129 if self.armed else 1, self.mode, 3, 3
            )
        )

    def run(self):
        beat = 0
        try:
            while not self.stopped:
                try:
                    data, addr = self.sock.recvfrom(512)
                    self.peer = addr
                    m = self.parser.parse_char(data)
                except socket.timeout:
                    m = None
                if self.peer and time.monotonic() - beat > 0.15:
                    self.heartbeat()
                    beat = time.monotonic()
                if m is None:
                    continue
                kind = m.get_type()
                if kind == "PARAM_REQUEST_READ":
                    name = (
                        m.param_id.decode()
                        if isinstance(m.param_id, bytes)
                        else m.param_id
                    )
                    name = name.rstrip("\x00")
                    if name in self.parameters:
                        self.send(
                            mav.MAVLink_param_value_message(
                                name.encode(), self.parameters[name], 9, 3, 0
                            )
                        )
                elif kind == "MISSION_COUNT":
                    self.count = m.count
                    if self.reject:
                        self.send(mav.MAVLink_mission_ack_message(255, 190, 14, 0))
                    elif self.drop_count_once:
                        self.drop_count_once = False
                    else:
                        self.send(
                            mav.MAVLink_mission_request_int_message(255, 190, 0, 0)
                        )
                elif kind == "MISSION_ITEM_INT":
                    self.items[m.seq] = m
                    if len(self.items) == self.count:
                        self.send(mav.MAVLink_mission_ack_message(255, 190, 0, 0))
                    else:
                        self.send(
                            mav.MAVLink_mission_request_int_message(
                                255, 190, m.seq + 1, 0
                            )
                        )
                elif kind == "MISSION_REQUEST_LIST":
                    self.send(
                        mav.MAVLink_mission_count_message(255, 190, self.count, 0)
                    )
                elif kind == "MISSION_REQUEST_INT":
                    if m.seq == 1 and self.drop_read_once:
                        self.drop_read_once = False
                        continue
                    s = self.items[m.seq]
                    self.send(
                        mav.MAVLink_mission_item_int_message(
                            255,
                            190,
                            s.seq,
                            s.frame,
                            s.command,
                            0,
                            1,
                            s.param1,
                            s.param2,
                            s.param3,
                            s.param4,
                            s.x,
                            s.y,
                            s.z,
                            0,
                        )
                    )
                elif kind == "COMMAND_LONG":
                    self.received_commands.append(m.command)
                    if m.command == 300:
                        self.mode = 10
                    elif m.command == 176:
                        self.mode = 4
                    self.send(
                        mav.MAVLink_command_ack_message(m.command, 0, 0, 0, 255, 190)
                    )
                    self.heartbeat()
        except Exception as e:
            self.error = e

    def close(self):
        self.stopped = True
        self.thread.join(2)
        self.sock.close()
        assert not self.thread.is_alive()
        assert self.error is None


def make_items():
    return [
        dict(
            seq=i,
            frame=6,
            command=16,
            params=[0, 0, 0, 0],
            x=136000000 + i * 100,
            y=1232000000,
            z=0,
            autocontinue=1,
        )
        for i in range(3)
    ]


def test_protocol_loss_readback_start_hold_no_arm():
    p = Peer()
    c = client.Client(f"udpout:127.0.0.1:{p.port}", 1)
    try:
        # Outgoing UDP must not reuse the peer's listening port on Windows.
        assert c.link.port.getsockname()[1] != p.port
        expected = make_items()
        c.heartbeat(disarmed=True)
        c.loss_policy()
        with pytest.raises(RuntimeError, match="Expected FS_GCS_ENABLE=2"):
            c.loss_policy(continue_in_auto=True)
        p.parameters["FS_GCS_TIMEOUT"] = 30
        with pytest.raises(RuntimeError, match="outside this commissioning profile"):
            c.loss_policy()
        p.parameters["FS_GCS_TIMEOUT"] = 5
        c.upload(expected)
        actual = c.download()
        client.compare(expected, actual)
        assert p.mode == 4 and not p.armed
        p.armed = True
        # Discard any older queued pre-arm heartbeat before explicit start.
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            m = c.recv(["HEARTBEAT"], 0.3)
            if m and m.base_mode & 128:
                break
        c.start_once()
        assert p.mode == 10
        c.hold()
        assert p.mode == 4
        assert p.received_commands == [300, 176]
        assert 400 not in p.received_commands
    finally:
        c.link.close()
        p.close()


def test_nack_blocks_upload_and_start():
    p = Peer(reject=True)
    c = client.Client(f"udpout:127.0.0.1:{p.port}", 1)
    try:
        with pytest.raises(RuntimeError, match="not accepted"):
            c.upload(make_items())
        assert not c.start_attempted
        assert p.received_commands == []
    finally:
        c.link.close()
        p.close()

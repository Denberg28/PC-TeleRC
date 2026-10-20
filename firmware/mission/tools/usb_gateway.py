#!/usr/bin/env python3
"""One rover per process. Loopback MAVLink gateway, no arming or heartbeat synthesis."""

import argparse
import socket
import struct
import time

MAX_MAV = 100


def crc(data):
    c = 0xFFFF
    for b in data:
        t = b ^ (c & 255)
        t ^= (t << 4) & 255
        c = ((c >> 8) ^ (t << 8) ^ (t << 3) ^ (t >> 4)) & 65535
    return c


def encode(rover, kind, data):
    if not 1 <= rover <= 20 or not 0 < len(data) <= MAX_MAV:
        raise ValueError("Invalid USB frame")
    body = struct.pack("<BBH", rover, kind, len(data)) + data
    return b"\xa5\x5a" + body + struct.pack("<H", crc(body))


class Decoder:
    def __init__(self):
        self.buf = bytearray()

    def feed(self, data):
        self.buf.extend(data)
        frames = []
        while self.buf:
            pos = self.buf.find(b"\xa5\x5a")
            if pos < 0:
                self.buf[:] = self.buf[-1:] if self.buf[-1:] == b"\xa5" else b""
                break
            if pos:
                del self.buf[:pos]
            if len(self.buf) < 6:
                break
            rover, kind, n = struct.unpack_from("<BBH", self.buf, 2)
            if not 1 <= n <= MAX_MAV:
                del self.buf[:2]
                continue
            if len(self.buf) < n + 8:
                break
            frame = bytes(self.buf[: n + 8])
            del self.buf[: n + 8]
            if crc(frame[2:-2]) == struct.unpack("<H", frame[-2:])[0]:
                frames.append((rover, kind, frame[6:-2]))
        return frames


def split_mav(data):
    frames = []
    while data:
        if len(data) < 2 or data[0] not in (0xFE, 0xFD):
            raise ValueError("Expected complete MAVLink datagram")
        n = data[1] + (12 if data[0] == 0xFD else 8)
        if data[0] == 0xFD and len(data) > 2 and data[2] & 1:
            n += 13
        if n > MAX_MAV or len(data) < n:
            raise ValueError("Oversize or incomplete MAVLink datagram")
        frames.append(data[:n])
        data = data[n:]
    if len(frames) > 4:
        raise ValueError("More than four frames per datagram")
    return frames


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", required=True, help="BASE USB COM port, e.g. COM9")
    p.add_argument("--rover", type=int, required=True, choices=range(1, 21))
    p.add_argument("--udp-port", type=int, default=14551)
    a = p.parse_args()
    import serial

    decoder = Decoder()
    peer = None
    last_peer = 0
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", a.udp_port))
    sock.setblocking(False)
    # Construct closed first so DTR/RTS do not pulse a running BASE.
    ser = serial.Serial(port=None, baudrate=115200, timeout=0, write_timeout=0.1)
    ser.dtr = True
    ser.rts = False
    ser.port = a.port
    ser.open()
    info = encode(a.rover, 3, b"INFO")
    caps = None
    deadline = time.monotonic() + 3
    next_request = 0
    try:
        while time.monotonic() < deadline:
            if time.monotonic() >= next_request:
                if ser.write(info) != len(info):
                    raise RuntimeError("Partial capability write")
                next_request = time.monotonic() + 0.5
            for rover, kind, data in decoder.feed(ser.read(512)):
                if rover == a.rover and kind == 3:
                    caps = data.decode("ascii")
            if caps and caps.startswith("TM2;fw=0.2.0;"):
                break
            time.sleep(0.005)
        if not caps or not caps.startswith("TM2;fw=0.2.0;"):
            raise RuntimeError("Matching Mission BASE 0.2.0 not confirmed")
    except Exception:
        ser.close()
        sock.close()
        raise
    print(caps)
    print(
        f"Rover {a.rover}; SYSID {a.rover}; loopback UDP {a.udp_port}; mission-only; no auto-arm"
    )
    try:
        while True:
            now = time.monotonic()
            try:
                data, addr = sock.recvfrom(512)
                if peer is None or now - last_peer > 5:
                    peer = addr
                if addr == peer:
                    frames = split_mav(data)
                    for frame in frames:
                        packet = encode(a.rover, 1, frame)
                        if ser.write(packet) != len(packet):
                            raise RuntimeError(
                                "Partial USB write; close and reconnect manually"
                            )
                    last_peer = now
            except BlockingIOError:
                pass
            except ValueError as e:
                print(f"Rejected datagram: {e}")
            for rover, kind, data in decoder.feed(ser.read(512)):
                if rover != a.rover:
                    continue
                if kind == 1 and peer is not None and now - last_peer <= 5:
                    sock.sendto(data, peer)
                elif kind == 2:
                    print(data.decode("ascii", errors="replace"))
            time.sleep(0.002)
    except KeyboardInterrupt:
        pass
    finally:
        # No queued commands, synthetic heartbeats or reconnect replay.
        ser.close()
        sock.close()


if __name__ == "__main__":
    main()

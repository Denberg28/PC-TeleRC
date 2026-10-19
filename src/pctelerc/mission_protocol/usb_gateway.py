#!/usr/bin/env python3
"""One rover per process. Loopback MAVLink gateway, no arming or heartbeat synthesis."""
import argparse
import socket
import struct
import time

MAX_MAV = 100

def crc(data):
    c = 0xffff
    for b in data:
        t = b ^ (c & 255)
        t ^= (t << 4) & 255
        c = ((c >> 8) ^ (t << 8) ^ (t << 3) ^ (t >> 4)) & 65535
    return c

def encode(rover, kind, data):
    if not 1 <= rover <= 20 or not 0 < len(data) <= MAX_MAV:
        raise ValueError('Invalid USB frame')
    body = struct.pack('<BBH', rover, kind, len(data)) + data
    return b'\xa5\x5a' + body + struct.pack('<H', crc(body))

class Decoder:
    def __init__(self):
        self.buf = bytearray()
    def feed(self, data):
        self.buf.extend(data)
        frames = []
        while self.buf:
            pos = self.buf.find(b'\xa5\x5a')
            if pos < 0:
                self.buf[:] = self.buf[-1:] if self.buf[-1:] == b'\xa5' else b''
                break
            if pos:
                del self.buf[:pos]
            if len(self.buf) < 6:
                break
            rover, kind, n = struct.unpack_from('<BBH', self.buf, 2)
            if not 1 <= n <= MAX_MAV:
                del self.buf[:2]
                continue
            if len(self.buf) < n + 8:
                break
            frame = bytes(self.buf[:n+8])
            del self.buf[:n+8]
            if crc(frame[2:-2]) == struct.unpack('<H', frame[-2:])[0]:
                frames.append((rover, kind, frame[6:-2]))
        return frames

def split_mav(data):
    frames = []
    while data:
        if len(data) < 2 or data[0] not in (0xfe, 0xfd):
            raise ValueError('Expected complete MAVLink datagram')
        n = data[1] + (12 if data[0] == 0xfd else 8)
        if data[0] == 0xfd and len(data) > 2 and data[2] & 1:
            n += 13
        if n > MAX_MAV or len(data) < n:
            raise ValueError('Oversize or incomplete MAVLink datagram')
        frames.append(data[:n])
        data = data[n:]
    if len(frames) > 4:
        raise ValueError('More than four frames per datagram')
    return frames

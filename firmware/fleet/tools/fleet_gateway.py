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


def parse_watch(value):
    result = []
    for token in value.split(','):
        bits = token.split('-')
        if len(bits) == 1:
            ids = [int(bits[0])]
        elif len(bits) == 2 and int(bits[0]) <= int(bits[1]):
            ids = range(int(bits[0]), int(bits[1])+1)
        else:
            raise ValueError('Use IDs/ranges, e.g. 1,3,5-8')
        for identity in ids:
            if not 1 <= identity <= 20:
                raise ValueError('Rover IDs must be 1..20')
            if identity not in result:
                result.append(identity)
    if not result:
        raise ValueError('Empty watch list')
    return result


def main():
    p = argparse.ArgumentParser(description='TF2 Fleet BASE gateway: one mission writer OR read-only fleet monitor. Never arms or synthesizes heartbeats.')
    p.add_argument('--port', required=True, help='BASE USB port, e.g. COM9')
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--rover', type=int, choices=range(1,21), help='Address one mission writer')
    mode.add_argument('--monitor', action='store_true', help='Read-only; no MAVLink commands or GCS heartbeats')
    p.add_argument('--watch', default='1-20', help='Monitor IDs/ranges; reduces time spent polling absent rovers')
    p.add_argument('--udp-port', type=int, default=14551)
    args = p.parse_args()
    try:
        watching = parse_watch(args.watch) if args.monitor else [args.rover]
    except ValueError as e:
        p.error(str(e))
    import serial
    from pymavlink.dialects.v20 import ardupilotmega as mav
    parsers = {identity:mav.MAVLink(None) for identity in watching}
    # A single process owns the COM port. No command multiplexing across vehicles.
    sock = None
    if not args.monitor:
        sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        sock.bind(('127.0.0.1',args.udp_port));sock.setblocking(False)
    ser = serial.Serial(port=None,baudrate=115200,timeout=0,write_timeout=0.1)
    ser.dtr=True;ser.rts=False;ser.port=args.port
    decoder = Decoder();peer=None;last_peer=0
    def send(kind,data):
        packet=encode(watching[0],kind,data)
        if ser.write(packet)!=len(packet):
            raise RuntimeError('Partial USB write; close and inspect link. No automatic replay.')
    try:
        ser.open();caps=None;deadline=time.monotonic()+4;next_request=0
        while time.monotonic()<deadline:
            if time.monotonic()>=next_request:
                send(3,b'INFO');next_request=time.monotonic()+0.5
            for identity,kind,data in decoder.feed(ser.read(512)):
                if identity==watching[0] and kind==3:
                    caps=data.decode('ascii',errors='replace')
            if caps and caps.startswith('TFM1;fw=1.1.0-dev1;'):
                break
            time.sleep(0.005)
        if not caps or not caps.startswith('TFM1;fw=1.1.0-dev1;'):
            raise RuntimeError('Matching Fleet 1.1.0-dev1 BASE not confirmed')
        print(caps)
        send(4,('WATCH:'+','.join(map(str,watching))).encode())
        deadline=time.monotonic()+2;accepted=False
        while time.monotonic()<deadline:
            for identity,kind,data in decoder.feed(ser.read(512)):
                if identity==watching[0] and kind==4:
                    accepted=data==b'WATCH_OK'
            if accepted:
                break
            time.sleep(0.005)
        if not accepted:
            raise RuntimeError('Watch configuration not confirmed')
        print('Read-only monitoring '+str(watching) if args.monitor else f'Mission writer rover {args.rover}; loopback UDP {args.udp_port}. No auto-arm.')
        records={identity:dict(at=None,hb=None,mode='?',armed='?') for identity in watching}
        display_at=0
        while True:
            now=time.monotonic()
            if sock:
                try:
                    data,addr=sock.recvfrom(512)
                    if peer is None or now-last_peer>5:
                        peer=addr
                    if addr==peer:
                        for frame in split_mav(data):
                            send(1,frame)
                        last_peer=now
                except BlockingIOError:
                    pass
                except ValueError as e:
                    print(f'Rejected datagram: {e}')
            for identity,kind,data in decoder.feed(ser.read(1024)):
                if kind==2:
                    print(data.decode('ascii',errors='replace'))
                elif kind==1 and identity in records:
                    if sock and peer and now-last_peer<=5:
                        sock.sendto(data,peer)
                    if args.monitor:
                        for byte in data:
                            message=parsers[identity].parse_char(bytes([byte]))
                            if message and message.get_srcSystem()==identity and message.get_srcComponent()==1:
                                records[identity]['at']=now
                                if message.get_type()=='HEARTBEAT' and message.type==10 and message.autopilot==3:
                                    records[identity].update(hb=now,mode=message.custom_mode,armed=bool(message.base_mode&128))
            if args.monitor and now-display_at>=5:
                display_at=now
                print('ROVER  last-data(s)  FC-heartbeat(s)  armed  mode  [ages are observations, not stop confirmation]')
                for identity,record in records.items():
                    age=lambda key: f'{now-record[key]:.1f}' if record[key] is not None else 'never'
                    print(f'{identity:5}  {age("at"):>12}  {age("hb"):>15}  {str(record["armed"]):>5}  {record["mode"]}')
            time.sleep(0.002)
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()
        if sock:
            sock.close()


if __name__=='__main__':
    main()

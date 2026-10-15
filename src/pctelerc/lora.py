"""TeleRC v0.8.53 USB datagrams and serialized, secret-free setup state."""
from __future__ import annotations

import binascii
import hashlib
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
import struct

MAX_PAYLOAD = 280
SYNC = b'\xa5\x5a'


def encode(payload: bytes) -> bytes:
    if not 0 < len(payload) <= MAX_PAYLOAD:
        raise ValueError('Invalid LoRa USB datagram size.')
    body = struct.pack('<H', len(payload)) + payload
    return SYNC + body + struct.pack('<H', binascii.crc_hqx(body, 0xffff))


class Parser:
    def __init__(self):
        self.buffer = bytearray()
        self.last_at = 0.0

    def feed(self, data: bytes, now: float) -> list[bytes]:
        # Empty polls do not extend the life of an incomplete frame.
        if self.buffer and now - self.last_at > .020:
            self.buffer.clear()
        if data:
            self.last_at = now
        self.buffer.extend(data)
        packets = []
        while self.buffer:
            sync = self.buffer.find(SYNC)
            if sync < 0:
                self.buffer[:] = self.buffer[-1:] if self.buffer[-1] == 0xa5 else b''
                break
            if sync:
                del self.buffer[:sync]
            if len(self.buffer) < 4:
                break
            length = struct.unpack_from('<H', self.buffer, 2)[0]
            if not 0 < length <= MAX_PAYLOAD:
                del self.buffer[:2]
                continue
            total = length + 6
            if len(self.buffer) < total:
                break
            frame = bytes(self.buffer[:total])
            del self.buffer[:total]
            if binascii.crc_hqx(frame[2:-2], 0xffff) == struct.unpack_from('<H', frame, total - 2)[0]:
                packets.append(frame[4:-2])
        return packets


@dataclass(frozen=True)
class Board:
    role: str
    chip: int
    active: bool
    khz: int
    power: int
    fingerprint: str
    rx: int
    rejected: int
    tx_failures: int
    uart_drops: int
    backend: str = "DIRECT"

    @classmethod
    def parse(cls, reply: bytes) -> Board | None:
        try:
            f = reply.decode('ascii').split(',')
            backend = 'DIRECT'
            if len(f) == 12 and f[0] == 'TELERC_LORA_INFO_V2' and f[-1] == 'ARDUROVER':
                backend = f.pop()
                f[0] = 'TELERC_LORA_INFO_V1'
            if len(f) != 11 or f[0] != 'TELERC_LORA_INFO_V1' or f[1] not in ('BASE', 'ROVER'):
                return None
            if f[2] not in ('1262', '1276') or f[3] not in ('0', '1') or not re.fullmatch('[0-9a-fA-F]{4}', f[6]):
                return None
            if any(not re.fullmatch('[0-9]+', f[i]) for i in (4, 5, 7, 8, 9, 10)):
                return None
            khz, power = int(f[4]), int(f[5])
            if not (150000 <= khz <= 960000 or khz == 0 and f[3] == '0') or not 2 <= power <= 17:
                return None
            counters = [int(v) for v in f[7:]]
            if any(not 0 <= n <= 0xffffffff for n in counters):
                return None
            return cls(f[1], int(f[2]), f[3] == '1', khz, power, f[6].lower(), *counters, backend)
        except (UnicodeError, ValueError):
            return None

    def describe(self):
        return (f'{self.role} · SX{self.chip} · {self.backend} · radio {"active" if self.active else "inactive"}\n'
                f'{self.khz / 1000:g} MHz · {self.power} dBm · fingerprint {self.fingerprint}\n'
                f'RX {self.rx} · rejected {self.rejected} · TX failures {self.tx_failures} · UART drops {self.uart_drops}')


def password_pairing_key(password: str) -> str:
    """Matches LilyGO Pairing.h; raw passwords never enter the USB protocol."""
    if not 8 <= len(password) <= 32 or any(not 33 <= ord(c) <= 126 for c in password):
        raise ValueError('LoRa password must contain 8–32 visible ASCII characters, without spaces.')
    return hashlib.pbkdf2_hmac('sha256', password.encode('ascii'),
                               b'TeleRC-LoRa-Link-v1', 10000, dklen=32).hex()


def setup_request(mhz: str, power: int, key: str) -> bytes:
    try:
        khz = Decimal(mhz.strip()) * 1000
        valid = khz.is_finite() and khz == khz.to_integral_value() and 150000 <= khz <= 960000
    except (InvalidOperation, ValueError):
        valid = False
    if not valid or not 2 <= power <= 17:
        raise ValueError('Enter a frequency in MHz (150–960, up to 3 decimals) and power 2–17 dBm.')
    secret = key.strip()
    if not re.fullmatch('[0-9a-fA-F]{64}', secret) or not any(bytes.fromhex(secret)):
        raise ValueError('Pairing key must contain 64 hexadecimal characters and must not be all zero.')
    return f'TELERC_LORA_SET_V1,{int(khz)},{power},{secret}'.encode('ascii')


RESULTS = {
    b'SKETCH_PAIRING_LOCKED': 'Pairing is defined in the sketch. Edit its password/frequency and upload again; saved pairing cannot override it.',
    b'SAVED_RESTART_BOARD': 'Saved. Close USB and restart this board. Provision its partner with the same frequency, power and key.',
    b'ACTIVE_DISCONNECT_AND_ERASE_NVS_FIRST': 'Active radio unchanged. Hold BOOT after startup to pause supported firmware, then read again. For older boards, follow the firmware setup guide.',
    b'STORAGE_FAILED': 'Board storage failed. Read settings before retrying.',
    b'INVALID': 'Board rejected the values. Settings were not saved.',
}


class SetupExchange:
    """Firmware has no request IDs; after timeout require a fresh USB session."""
    def __init__(self):
        self.board = None
        self.pending = None
        self.blocked = False
        self.restart_required = False

    @property
    def can_save(self):
        return self.board is not None and not self.board.active and not self.pending and not self.blocked and not self.restart_required

    def begin_read(self):
        if self.pending or self.blocked or self.restart_required:
            raise ValueError('Close and reopen USB before another exchange.')
        self.board = None
        self.pending = 'read'
        return b'TELERC_LORA_GET_V1'

    def begin_save(self, mhz, power, key):
        if not self.can_save:
            raise ValueError('Read an inactive board before saving pairing settings.')
        request = setup_request(mhz, power, key)
        self.pending = 'save'
        return request

    def receive(self, reply):
        if self.blocked:
            return None
        if self.pending == 'read':
            board = Board.parse(reply)
            if board:
                self.board = board
                self.pending = None
                return board.describe()
        elif self.pending == 'save':
            prefix = b'TELERC_LORA_RESULT_V1,'
            result = reply[len(prefix):] if reply.startswith(prefix) else b''
            if result in RESULTS:
                self.pending = None
                self.board = None
                self.restart_required = result == b'SAVED_RESTART_BOARD'
                return RESULTS[result]
        return None

    def timeout(self):
        if self.pending:
            self.pending = None
            self.board = None
            self.blocked = True


@dataclass(frozen=True)
class RemoteStatus:
    ready: bool
    owned: int
    stops: int
    boot: int
    reason: int
    command_age_ms: int
    received_at: float

    @classmethod
    def parse(cls, reply: bytes, now: float):
        try:
            fields = reply.decode('ascii').split(',')
            if len(fields) != 7 or fields[0] != 'TELERC_LORA_STATUS_V1':
                return None
            if any(not re.fullmatch('[0-9]+', v) for v in fields[1:]):
                return None
            ready, owned, stops, boot, reason, age = map(int, fields[1:])
            if ready > 1 or owned > 3 or reason > 7 or not 1 <= boot <= 0xffffffff:
                return None
            if stops > 0xffffffff or age > 0xffffffff:
                return None
            return cls(bool(ready), owned, stops, boot, reason, age, now)
        except (UnicodeError, ValueError):
            return None

    def fresh(self, now):
        return 0 <= now - self.received_at < .5

    def describe(self):
        reasons = ('boot', 'command-timeout', 'FC-heartbeat-timeout', 'release',
                   'disconnect', 'UART-write-failure', 'radio-fault', 'disarm')
        return f'LoRa rover: ready={int(self.ready)} owned={self.owned} stops={self.stops} last={reasons[self.reason]} command age={self.command_age_ms}ms'



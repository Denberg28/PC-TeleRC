"""Bounded, read-only FC inspection. Never used to authorize upload/ARM/START."""
import math
import time
from .mission_protocol.client import MAX_ITEMS,RETRIES,TIMEOUT,from_message


HOP_TIMEOUT = 2


class ReadbackError(RuntimeError):
    """Read-only operation failed without a vehicle state-changing command."""


def read_stored_mission(client, relays=0, progress=lambda *_:None):
    timeout = TIMEOUT+HOP_TIMEOUT*max(0,min(4,int(relays)))
    deadline = time.monotonic()+30

    def receive(types, end):
        while time.monotonic() < min(end,deadline):
            client.check()
            msg = client.recv(types,min(.3,max(0,min(end,deadline)-time.monotonic())))
            if msg is not None:return msg
        return None

    def count_request():
        for _ in range(RETRIES):
            client.check()
            if time.monotonic() >= deadline:break
            client.link.mav.mission_request_list_send(client.rover,1,0)
            msg = receive(['MISSION_COUNT','MISSION_ACK'],time.monotonic()+timeout)
            if msg is None:continue
            if msg.get_type() == 'MISSION_ACK':
                raise ReadbackError(f'FC declined mission read ({msg.type})')
            if not 0 <= msg.count <= MAX_ITEMS:
                raise ReadbackError(f'FC mission has {msg.count} rows; inspection limit is {MAX_ITEMS}')
            return msg
        raise ReadbackError('FC mission count timed out; no mission was changed')

    count_msg = count_request()
    count = count_msg.count
    mission_id = getattr(count_msg,'opaque_id',0)
    deadline = time.monotonic()+min(600,max(30,count*timeout*2))
    result = []
    for seq in range(count):
        found = None
        for attempt in range(RETRIES):
            client.check()
            if time.monotonic() >= deadline:break
            progress(seq,count,attempt)
            client.link.mav.mission_request_int_send(client.rover,1,seq,0)
            end = min(deadline,time.monotonic()+timeout)
            while time.monotonic() < end:
                msg = receive(['MISSION_ITEM_INT','MISSION_ITEM','MISSION_COUNT','MISSION_ACK'],end)
                if msg is None:break
                kind = msg.get_type()
                if kind == 'MISSION_ACK':
                    raise ReadbackError(f'FC ended mission read ({msg.type})')
                if kind == 'MISSION_COUNT':
                    if msg.count != count or (mission_id and getattr(msg,'opaque_id',0) != mission_id):
                        raise ReadbackError('FC mission changed during read; load again')
                    continue
                if msg.seq != seq:continue
                try:row = from_message(msg)
                except (ValueError,OverflowError,TypeError) as exc:
                    raise ReadbackError('Invalid FC mission row') from exc
                # Optional MAVLink parameters may legitimately be NaN; preserve
                # them for inspection, never convert inspection into a flyable plan.
                if any(math.isinf(v) for v in row['params']+[row['z']]):
                    raise ReadbackError('FC mission row contains infinite parameters')
                row['current'] = bool(getattr(msg,'current',0))
                found = row
                break
            if found is not None:break
        if found is None:
            raise ReadbackError(f'FC row {seq} timed out; no partial mission is displayed')
        result.append(found)
    client.check()
    # Finish the download before an independent count/id check; this is not an
    # upload, CLEAR_ALL, SET_CURRENT or command. Empty/home-only storage is valid.
    client.link.mav.mission_ack_send(client.rover,1,0,0)
    final = count_request()
    if final.count != count or (mission_id and getattr(final,'opaque_id',0) != mission_id):
        raise ReadbackError('FC mission changed during read; load again')
    client.link.mav.mission_ack_send(client.rover,1,0,0)
    progress(count,count,0)
    return result

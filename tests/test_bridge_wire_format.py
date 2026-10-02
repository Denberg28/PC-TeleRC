from pymavlink.dialects.v10 import ardupilotmega as mavlink1


class CaptureWriter:
    def __init__(self):
        self.frames = []

    def write(self, data):
        self.frames.append(bytes(data))
        return len(data)


def u16(frame, offset):
    return frame[offset] | (frame[offset + 1] << 8)


def test_bridge_control_encoder_stays_mavlink1_and_sparse():
    writer = CaptureWriter()
    mav = mavlink1.MAVLink(writer, srcSystem=255, srcComponent=190)

    channels = [65535] * 8
    channels[0] = 1700
    channels[2] = 1600
    mav.rc_channels_override_send(1, 1, *channels)

    frame = writer.frames[-1]
    assert frame[0] == 0xFE
    assert frame[1] == 18
    assert frame[3] == 255
    assert frame[4] == 190
    assert frame[5] == 70
    assert u16(frame, 6) == 1700
    assert u16(frame, 8) == 65535
    assert u16(frame, 10) == 1600
    assert u16(frame, 12) == 65535
    assert all(u16(frame, 6 + 2 * ch) == 65535 for ch in range(4, 8))
    assert frame[22] == 1
    assert frame[23] == 1


def test_bridge_control_release_stays_mavlink1_sparse():
    writer = CaptureWriter()
    mav = mavlink1.MAVLink(writer, srcSystem=255, srcComponent=190)

    channels = [65535] * 8
    channels[0] = 0
    channels[2] = 0
    mav.rc_channels_override_send(1, 1, *channels)

    frame = writer.frames[-1]
    assert frame[0] == 0xFE
    assert u16(frame, 6) == 0
    assert u16(frame, 8) == 65535
    assert u16(frame, 10) == 0
    assert u16(frame, 12) == 65535

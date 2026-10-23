from pathlib import Path
from pymavlink.dialects.v20 import common as m

def fixtures(path):
    gcs = m.MAVLink(None, srcSystem=255, srcComponent=190)
    fc = m.MAVLink(None, srcSystem=1, srcComponent=1)
    def raw(obj, sender=gcs):
        return bytes(obj.pack(sender))
    rows = {}
    rows['hostHeartbeat'] = raw(m.MAVLink_heartbeat_message(6, 8, 0, 0, 4, 3))
    rows['disarmed'] = raw(m.MAVLink_heartbeat_message(10, 3, 1, 4, 3, 3), fc)
    rows['armed'] = raw(m.MAVLink_heartbeat_message(10, 3, 129, 4, 3, 3), fc)
    rows['missionCount'] = raw(m.MAVLink_mission_count_message(1, 1, 2, 0))
    rows['foreignCount'] = raw(m.MAVLink_mission_count_message(2, 1, 2, 0))
    for i in range(2):
        rows[f'item{i}'] = raw(m.MAVLink_mission_item_int_message(1, 1, i, 6, 16, 0, 1, 0, 0, 0, 0, 136000000+i*100, 1232000000, 0, 0))
    rows['navDelay'] = raw(m.MAVLink_mission_item_int_message(1, 1, 1, 2, 93, 0, 1, 4, -1, -1, -1, 0, 0, 0, 0))
    rows['conditionDelay'] = raw(m.MAVLink_mission_item_int_message(1, 1, 1, 2, 112, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0))
    rows['badDelay'] = raw(m.MAVLink_mission_item_int_message(1, 1, 1, 2, 93, 0, 1, 0, -1, -1, -1, 0, 0, 0, 0))
    rows['motorServo'] = raw(m.MAVLink_mission_item_int_message(1, 1, 1, 2, 183, 0, 1, 5, 1500, 0, 0, 0, 0, 0, 0))
    rows['servoItem'] = raw(m.MAVLink_mission_item_int_message(1, 1, 1, 2, 183, 0, 1, 9, 1500, 0, 0, 0, 0, 0, 0))
    rows['gps'] = raw(m.MAVLink_gps_raw_int_message(1000000,3,136000000,1232000000,0,100,100,0,0,10),fc)
    rows['current'] = raw(m.MAVLink_mission_current_message(2),fc)
    rows['reached'] = raw(m.MAVLink_mission_item_reached_message(2),fc)
    rows['missionAck'] = raw(m.MAVLink_mission_ack_message(255, 190, 0, 0), fc)
    rows['startMission'] = raw(m.MAVLink_command_long_message(1, 1, 300, 0, 0, 0, 0, 0, 0, 0, 0))
    rows['holdMode'] = raw(m.MAVLink_command_long_message(1, 1, 176, 0, 1, 4, 0, 0, 0, 0, 0))
    rows['armCommand'] = raw(m.MAVLink_command_long_message(1, 1, 400, 0, 1, 0, 0, 0, 0, 0, 0))
    rows['forceArm'] = raw(m.MAVLink_command_long_message(1, 1, 400, 0, 1, 21196, 0, 0, 0, 0, 0))
    rows['rcOverride'] = raw(m.MAVLink_rc_channels_override_message(1, 1, 1500, 1500, 65535, 65535, 65535, 65535, 65535, 65535))
    for t in (1000, 100):
        rows[f'position{t}'] = raw(m.MAVLink_global_position_int_message(t, 136000000, 1232000000, 0, 0, 0, 0, 0, 0), fc)
    Path(path).write_text('#pragma once\n#include <vector>\n' + '\n'.join('const std::vector<uint8_t> '+name+'={'+','.join(str(x) for x in data)+'};' for name, data in rows.items()))

if __name__ == '__main__':
    import sys
    fixtures(sys.argv[1])

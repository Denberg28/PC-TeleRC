"""Actual fleet role guard checks under ASan/UBSan; no physical RF claim."""
from pathlib import Path
import os,subprocess,sys,tempfile
from pymavlink.dialects.v20 import common as m
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from provision import provision,add_device

def main():
 with tempfile.TemporaryDirectory() as temp:
  temp=Path(temp);profiles=temp/'profiles';provision(profiles,count=3,relays=1)
  add_device(profiles/'NETWORK.private.json',profiles/'TeleRCFleet_NODE_200','NODE',200)
  pc=m.MAVLink(None,srcSystem=255,srcComponent=190);fc=m.MAVLink(None,srcSystem=1,srcComponent=1)
  fixtures={
   'fcHb':m.MAVLink_heartbeat_message(10,3,1,4,3,3).pack(fc),
   'autoHb':m.MAVLink_heartbeat_message(10,3,129,10,3,3).pack(fc),
   'arm':m.MAVLink_command_long_message(1,1,400,0,1,0,0,0,0,0,0).pack(pc),
   'disarm':m.MAVLink_command_long_message(1,1,400,0,0,0,0,0,0,0,0).pack(pc),
   'forceArm':m.MAVLink_command_long_message(1,1,400,0,1,21196,0,0,0,0,0).pack(pc),
   'foreignArm':m.MAVLink_command_long_message(2,1,400,0,1,0,0,0,0,0,0).pack(pc),
   'paramSet':m.MAVLink_param_set_message(1,1,b'ARMING_CHECK',0,9).pack(pc)}
  (temp/'fixtures.h').write_text(''.join('const unsigned char '+name+'[]={'+','.join(map(str,data))+'};\n' for name,data in fixtures.items()))
  for role in ('BASE','ROVER_001','ROVER_003','NODE_1','NODE_200'):
   binary=temp/role
   subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
    '-fsanitize=address,undefined','-fno-omit-frame-pointer','-fno-pie','-no-pie',
    '-I'+str(profiles/('TeleRCFleet_'+role)),'-I'+str(ROOT/'tests/stubs'),'-I'+str(temp),
    str(ROOT/'tests/test_native.cpp'),'-lcrypto','-o',str(binary)],check=True)
   subprocess.run([str(binary)],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
   print('PASS fleet native sanitizer',role,flush=True)
if __name__=='__main__':main()

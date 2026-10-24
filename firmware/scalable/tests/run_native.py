"""Compile actual unified role runtimes with protocol fixtures and sanitizers."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from provision import provision
from make_fixtures import fixtures

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--sanitize',action='store_true');args=parser.parse_args()
    with tempfile.TemporaryDirectory() as temp:
        temp=Path(temp);fixtures(temp/'fixtures.h')
        folder=temp/'profiles';provision(folder,count=1,relays=3)
        from provision import add_device
        add_device(folder/'NETWORK.private.json',folder/'TeleRCScale_NODE_200','NODE',200)
        for role in ['BASE','ROVER_001','NODE_1','NODE_3','NODE_200']:
            binary=temp/role
            cmd=['g++','-std=c++17','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
                 '-I'+str(folder/f'TeleRCScale_{role}'),'-I'+str(ROOT/'tests/stubs'),
                 '-I'+str(temp),str(ROOT/'tests/test_native.cpp'),'-lcrypto','-o',str(binary)]
            if args.sanitize:cmd[1:1]=['-fsanitize=address,undefined','-fno-omit-frame-pointer','-fno-pie','-no-pie']
            subprocess.run(cmd,check=True);print('ROLE',role,flush=True)
            subprocess.run([str(binary)],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
        check=temp/'blank.cpp';check.write_text('#include <cassert>\n#include "Runtime.h"\nint main(){setup();for(int i=0;i<5000;++i)loop();assert(!running&&!authorizedRadio&&fc.tx.empty());}\n')
        for example in sorted((ROOT/'sketches').glob('TeleRCScale_*')):
            binary=temp/'blank';cmd=['g++','-std=c++17','-I'+str(example),'-I'+str(ROOT/'tests/stubs'),str(check),'-lcrypto','-o',str(binary)]
            subprocess.run(cmd,check=True);subprocess.run([str(binary)],check=True)
        print('PASS: 5 provisioned role profiles + 5 public RF-OFF examples; no hardware qualification implied')

if __name__=='__main__':main()

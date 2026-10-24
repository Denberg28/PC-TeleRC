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
        for relays in (0,1,2):
            folder=temp/f'profiles-{relays}';provision(folder,count=2,relays=relays)
            for role in ['BASE','ROVER_001']+[f'NODE_{i}' for i in range(1,relays+1)]:
                binary=temp/f'{relays}-{role}'
                cmd=['g++','-std=c++17','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
                     '-I'+str(folder/f'TeleRCUnified_{role}'),'-I'+str(ROOT/'tests/stubs'),
                     '-I'+str(temp),str(ROOT/'tests/test_native.cpp'),'-lcrypto','-o',str(binary)]
                if args.sanitize:cmd[1:1]=['-fsanitize=address,undefined','-fno-omit-frame-pointer','-fno-pie','-no-pie']
                subprocess.run(cmd,check=True)
                print('ROLE',role,'max relays',relays,flush=True)
                subprocess.run([str(binary)],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
        check=temp/'blank.cpp';check.write_text('#include <cassert>\n#include "Runtime.h"\nint main(){setup();for(int i=0;i<5000;++i)loop();assert(!running&&!authorizedRadio&&fc.tx.empty());}\n')
        for example in sorted((ROOT/'sketches').glob('TeleRCUnified_*')):
            binary=temp/'blank';cmd=['g++','-std=c++17','-I'+str(example),'-I'+str(ROOT/'tests/stubs'),str(check),'-lcrypto','-o',str(binary)]
            subprocess.run(cmd,check=True);subprocess.run([str(binary)],check=True)
        print('PASS: 9 provisioned role profiles + 4 public RF-OFF examples; no hardware qualification implied')

if __name__=='__main__':main()

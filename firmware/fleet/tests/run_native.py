#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from network import init,sketch
from make_fixtures import fixtures


def main():
    p=argparse.ArgumentParser();p.add_argument('--sanitize',action='store_true');args=p.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        temp=Path(tmp);credentials=init(temp/'private');network=json.loads(credentials.read_text());fixtures(temp/'fixtures.h')
        for role,identity in [('base',1),('rover',1),('rover',20),('node',1),('node',200)]:
            folder=temp/f'{role}{identity}';sketch(folder,role,identity,network)
            text=f'#define ROLE {dict(base=1,rover=2,node=3)[role]}\n#define ROVER_ID {identity if role=="rover" else 1}\n#define NODE_ID {identity if role=="node" else 1}\n'
            text+='static const unsigned char testRoot[32]={'+','.join(str(v) for v in bytes.fromhex(network['endpoint_root']))+'};\n'
            (temp/'TestRole.h').write_text(text)
            binary=temp/f'test-{role}-{identity}'
            cmd=['g++','-std=c++17','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-g',
                 '-I'+str(ROOT/'firmware'),'-I'+str(folder),'-I'+str(ROOT/'tests/stubs'),'-I'+str(temp),
                 str(ROOT/'tests/test_native.cpp'),'-lcrypto','-o',str(binary)]
            if args.sanitize:
                cmd[1:1]=['-fsanitize=address,undefined','-fno-omit-frame-pointer','-fno-pie','-no-pie']
            subprocess.run(cmd,check=True)
            print(f'ROLE {role} ID {identity}; sanitizer={args.sanitize}',flush=True)
            subprocess.run([str(binary)],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
        blank=temp/'blank.cpp'
        for role,identity in [('base',1),('rover',1),('node',1),('node',2)]:
            folder=temp/f'blank-{role}{identity}';sketch(folder,role,identity)
            blank.write_text(f'#include "{folder.name}.ino"\n#include <cassert>\nint main(){{setup();assert(!running&&stopped&&fc.tx.empty());}}\n')
            binary=temp/'blank'
            subprocess.run(['g++','-std=c++17','-I'+str(folder),'-I'+str(ROOT/'tests/stubs'),str(blank),'-lcrypto','-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)
            print(f'PASS keyless {role} {identity}: RF OFF',flush=True)
    print('PASS: five provisioned runtime builds + four RF-OFF profiles; no hardware/RF certification implied.')

if __name__=='__main__':
    main()

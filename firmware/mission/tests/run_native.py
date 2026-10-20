#!/usr/bin/env python3
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from provision import provision
from make_fixtures import fixtures

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--sanitize', action='store_true')
    a = p.parse_args()
    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)
        fixtures(temp / 'fixtures.h')
        for relays in (0, 1, 2):
            private = temp / f'profiles-{relays}'
            provision(private, count=2, relays=relays)
            profiles = ['BASE', 'ROVER_001'] + [f'NODE_{i}' for i in range(1, relays+1)]
            for role in profiles:
                binary = temp / f'test-{relays}-{role}'
                cmd = ['g++', '-std=c++17', '-Wall', '-Wextra', '-Wno-misleading-indentation', '-Werror', '-g',
                       '-I'+str(ROOT/'firmware'), '-I'+str(private/f'TeleRCMission_{role}'),
                       '-I'+str(ROOT/'tests/stubs'), '-I'+str(temp), str(ROOT/'tests/test_native.cpp'), '-lcrypto', '-o', str(binary)]
                if a.sanitize:
                    cmd[1:1] = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-pie', '-no-pie']
                subprocess.run(cmd, check=True)
                print(f'=== role {role}; relays {relays}; sanitizer {a.sanitize} ===', flush=True)
                subprocess.run([str(binary)], check=True, env={**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0'})
        blank = temp/'blank.cpp'
        blank.write_text('#include <cassert>\n#include "Runtime.h"\nint main(){setup();assert(!running);assert(fc.tx.empty());}\n')
        for folder in sorted((ROOT/'sketches').glob('TeleRCMission_*')):
            binary = temp/f'blank-{folder.name}'
            cmd = ['g++', '-std=c++17', '-I'+str(ROOT/'firmware'), '-I'+str(folder), '-I'+str(ROOT/'tests/stubs'), str(blank), '-lcrypto', '-o', str(binary)]
            if a.sanitize:
                cmd[1:1] = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-pie', '-no-pie']
            subprocess.run(cmd, check=True)
            subprocess.run([str(binary)], check=True, env={**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0'})
            print(f'PASS: {folder.name} keyless example keeps RF OFF', flush=True)
    print('PASS: 9 provisioned runtime/profile builds plus 4 keyless RF-OFF builds (13 total host builds and executions)')

if __name__ == '__main__':
    main()

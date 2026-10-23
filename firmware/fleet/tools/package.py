#!/usr/bin/env python3
"""Package public RF-OFF sources only. Never package a generated private fleet."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parents[1]
NAME='TeleRC-LoRa-Fleet-v1.1.0-dev1'


def files():
    result=[]
    for file in sorted(ROOT.rglob('*')):
        if not file.is_file() or any(p in ('__pycache__','.pytest_cache','.git') for p in file.parts) or file.suffix=='.pyc':
            continue
        if file.name=='MANIFEST.sha256.json':
            continue
        if file.name=='FleetCredentials.json' or file.suffix in ('.bin','.elf','.map','.zip'):
            raise ValueError(f'Unexpected private/build artifact: {file.relative_to(ROOT)}')
        if 'sketches' in file.relative_to(ROOT).parts and file.suffix=='.h' and file.name!='NetworkConfig.h':
            canonical=ROOT/'firmware'/file.name
            if not canonical.is_file() or canonical.read_bytes()!=file.read_bytes():
                raise ValueError(f'Stale example header: {file.relative_to(ROOT)}')
        if file.name=='NetworkConfig.h':
            text=file.read_text()
            if '#define PROVISIONED 0' not in text or '0x' in text:
                raise ValueError('Refusing provisioned sketch in public package')
        result.append(file)
    return result


def package(out):
    out=Path(out).resolve()
    if out==ROOT or ROOT in out.parents:
        raise ValueError('Package output must be outside the source tree')
    out.mkdir(parents=True,exist_ok=True)
    public=files()
    manifest={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in public}
    manifest_bytes=(json.dumps(dict(format='TeleRC-Fleet-source-sha256-v1',files=manifest),indent=2,sort_keys=True)+'\n').encode()
    archive=out/(NAME+'.zip')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        entries=[(str(p.relative_to(ROOT)).replace('\\','/'),p.read_bytes()) for p in public]
        entries.append(('MANIFEST.sha256.json',manifest_bytes))
        for name,data in sorted(entries):
            info=zipfile.ZipInfo(NAME+'/'+name,date_time=(2026,10,23,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,data)
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    sums=out/(NAME+'.sha256')
    sums.write_text(f'{digest}  {archive.name}\n')
    print(f'{archive}: {len(public)} public source files; sha256={digest}')
    return archive


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    package(p.parse_args().out)

"""Compile public and private test profiles; package only keyless public output."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
sys.path.insert(0,str(REPO/'scripts'))
from release_safety import check_directory
from provision import provision,add_device

FQBN='esp32:esp32:lilygo_t3s3:Revision=Radio_SX1262,PSRAM=disabled,USBMode=hwcdc,CDCOnBoot=cdc'
NAME='TeleRC-Scalable-LoRa-v0.4.0rc1'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    out=REPO/'scalable-dist';out.mkdir(exist_ok=True)
    stage=out/NAME
    if stage.exists():raise ValueError('Use a clean candidate staging directory')
    shutil.copytree(ROOT,stage,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache','*.pyc'))
    records=[]
    with tempfile.TemporaryDirectory() as temp:
        temp=Path(temp);private=temp/'private';provision(private,relays=0)
        for number in (1,3,200):add_device(private/'NETWORK.private.json',private/f'TeleRCScale_NODE_{number}','NODE',number)
        for kind,folder in [('public',ROOT/'sketches'),('private-test',private)]:
            for profile in sorted(folder.glob('TeleRCScale_*')):
                build=temp/(kind+'-'+profile.name)
                log=temp/'compile.txt'
                with log.open('w') as stream:
                    result=subprocess.run(['arduino-cli','compile','--fqbn',FQBN,'--output-dir',str(build),str(profile)],stdout=stream,stderr=subprocess.STDOUT)
                if result.returncode:
                    # Never publish generated private headers or private build output.
                    if kind=='public':print(log.read_text())
                    raise RuntimeError(kind+' actual-board compilation failed: '+profile.name)
                record=dict(role=profile.name,profile=kind,fqbn=FQBN,result='PASS')
                if kind=='public':
                    destination=stage/'binaries'/profile.name;destination.mkdir(parents=True)
                    images=[]
                    for suffix,offset in [('.ino.bootloader.bin','0x0'),('.ino.partitions.bin','0x8000'),('.ino.bin','0x10000')]:
                        source=build/(profile.name+suffix);target=destination/source.name;shutil.copyfile(source,target)
                        images.append(dict(file=target.relative_to(stage).as_posix(),offset=offset,bytes=target.stat().st_size,sha256=sha(target)))
                    source=Path.home()/'.arduino15/packages/esp32/hardware/esp32/3.3.2/tools/partitions/boot_app0.bin'
                    target=destination/'boot_app0.bin';shutil.copyfile(source,target)
                    images.append(dict(file=target.relative_to(stage).as_posix(),offset='0xe000',bytes=target.stat().st_size,sha256=sha(target)))
                    record['images']=images
                records.append(record);print('PASS',kind,profile.name,flush=True)
    report=dict(version='0.4.0rc1',source_commit=os.environ['GITHUB_SHA'],
        esp32_core='3.3.2',radiolib='7.2.1',builds=records,
        public_radio='RF OFF; generate matching private roles before use',
        private_binaries_distributed=False,hardware_validation='NOT TESTED',
        pc_compatibility='v1.0.1 legacy manual USB and TM2 mission USB driver handshakes tested',
        manual_rover_id=1,mission_rover_ids='1..20; BASE keys fixed at project creation',
        node_ids='1..200 identities; capacity under contention NOT TESTED',max_active_relay_hops=2,
        routing='TU2 authenticated source routes, rate-limited read-only discovery, 3 samples before command admission',
        enrollment='Saved private project; adding IDs does not change deployed configs')
    (stage/'BUILD_REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    (stage/'SHA256SUMS.txt').write_text(''.join(sha(p)+'  '+p.relative_to(stage).as_posix()+'\n' for p in sorted(stage.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.txt'))
    archive=out/(NAME+'.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as writer:
        for p in sorted(stage.rglob('*')):
            if p.is_file():writer.write(p,NAME+'/'+p.relative_to(stage).as_posix())
    shutil.copyfile(stage/'BUILD_REPORT.json',out/'BUILD_REPORT.json')
    shutil.copyfile(ROOT/'README.md',out/'README.md')
    (out/'SHA256SUMS.txt').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in sorted(out.iterdir()) if p.is_file() and p.name!='SHA256SUMS.txt'))
    # Validate nested source/binaries before they are offered for download.
    check_directory(out)
    print('PASS sanitized candidate:',archive.name)

if __name__=='__main__':main()

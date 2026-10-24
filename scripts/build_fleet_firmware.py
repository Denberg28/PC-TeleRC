"""Board-build matching fleet roles; distribute only keyless RF-OFF examples."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,tempfile,zipfile
from release_safety import check_directory
ROOT=Path(__file__).resolve().parents[1];FW=ROOT/'firmware/fleet';NAME='TeleRC-Fleet-LoRa-v0.5.0rc1'
FQBN='esp32:esp32:lilygo_t3s3:Revision=Radio_SX1262,PSRAM=disabled,USBMode=hwcdc,CDCOnBoot=cdc'
sys.path.insert(0,str(FW/'tools'))
from provision import provision,add_device

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 out=ROOT/'fleet-dist';out.mkdir();stage=out/NAME
 shutil.copytree(FW,stage,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache','*.pyc'))
 records=[]
 with tempfile.TemporaryDirectory() as temp:
  temp=Path(temp);private=temp/'profiles';provision(private,count=3,relays=0)
  add_device(private/'NETWORK.private.json',private/'TeleRCFleet_ROVER_020','ROVER',20)
  add_device(private/'NETWORK.private.json',private/'TeleRCFleet_NODE_200','NODE',200)
  chosen=[('public',p) for p in sorted((FW/'sketches').glob('TeleRCFleet_*'))]
  chosen += [('private-test',private/('TeleRCFleet_'+r)) for r in ('BASE','ROVER_001','ROVER_003','ROVER_020','NODE_200')]
  converter=ROOT/'firmware/TeleRC_4x_BTS7960_PWM_GlitchFilter'
  pwmfqbn='esp32:esp32:esp32s3:CDCOnBoot=cdc,USBMode=hwcdc,FlashSize=4M,PartitionScheme=default,PSRAM=disabled,FlashMode=dio'
  shutil.copytree(converter,stage/'PWM'/converter.name)
  chosen.append(('converter',converter))
  for kind,profile in chosen:
   build=temp/(kind+'-'+profile.name);fqbn=pwmfqbn if kind=='converter' else FQBN
   log=temp/'compile.log'
   with log.open('w') as stream:r=subprocess.run(['arduino-cli','compile','--fqbn',fqbn,'--output-dir',str(build),str(profile)],stdout=stream,stderr=subprocess.STDOUT)
   if r.returncode:
    if kind!='private-test':print(log.read_text())
    raise RuntimeError('Board compilation failed: '+kind+' '+profile.name)
   record=dict(profile=kind,role=profile.name,fqbn=fqbn,result='PASS')
   if kind!='private-test':
    dest=stage/'binaries'/profile.name;dest.mkdir(parents=True);images=[]
    for suffix,offset in (('.ino.bootloader.bin','0x0'),('.ino.partitions.bin','0x8000'),('.ino.bin','0x10000')):
     source=build/(profile.name+suffix);target=dest/source.name;shutil.copyfile(source,target)
     images.append(dict(file=target.relative_to(stage).as_posix(),offset=offset,bytes=target.stat().st_size,sha256=sha(target)))
    boot=Path.home()/'.arduino15/packages/esp32/hardware/esp32/3.3.2/tools/partitions/boot_app0.bin';target=dest/'boot_app0.bin';shutil.copyfile(boot,target)
    images.append(dict(file=target.relative_to(stage).as_posix(),offset='0xe000',bytes=target.stat().st_size,sha256=sha(target)));record['images']=images
   records.append(record);print('PASS fleet board',kind,profile.name,flush=True)
 report=dict(version='0.5.0rc1',application='1.2.0rc1',source_commit=os.environ['GITHUB_SHA'],
  arduino_cli='1.3.1',esp32_core='3.3.2',radiolib='7.2.1',builds=records,hardware_validation='NOT TESTED',
  protocol='TF3 USB / TU2 authenticated radio',private_keys_distributed=False,private_binaries_distributed=False,
  existing_tu2_nodes_compatible=True,max_relay_hops=2,rover_id_namespace='1..20',
  simultaneous_capacity='measured airtime admission; physical capacity NOT QUALIFIED',
  checks='native guard sanitizers; three-rover actual encrypted-role graph; old TU2 relay compatibility')
 (stage/'BUILD_REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
 (stage/'SHA256SUMS.txt').write_text(''.join(sha(p)+'  '+p.relative_to(stage).as_posix()+'\n' for p in sorted(stage.rglob('*')) if p.is_file()))
 archive=out/(NAME+'.zip')
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
  for p in sorted(stage.rglob('*')):
   if p.is_file():z.write(p,NAME+'/'+p.relative_to(stage).as_posix())
 shutil.copyfile(stage/'BUILD_REPORT.json',out/'BUILD_REPORT.json')
 check_directory(out)
 print('PASS sanitized fleet firmware',len(records),'actual-board builds')
if __name__=='__main__':main()

"""Compile exact role profiles; ship only separate NVS-preserving images."""
import hashlib,json,os,subprocess,zipfile
from pathlib import Path
import shutil
m=json.loads(Path('ecosystem-release.json').read_text());product=m['product']
generic='esp32:esp32:esp32s3:CDCOnBoot=cdc,USBMode=hwcdc,FlashSize=4M,PartitionScheme=default,PSRAM=disabled,FlashMode=dio'
t3='esp32:esp32:lilygo_t3s3:Revision=Radio_SX1262,PSRAM=disabled,USBMode=hwcdc,CDCOnBoot=cdc'
if product=='TeleRC':
 targets=[('wifi-fc-bridge','bridge/TeleRCBridge',generic),('pwm-four-bts7960','bridge/BTS7960PWMConverter',generic),('dedicated-motor','bridge/TeleRCMotorController',generic),('dedicated-wifi-gateway','bridge/TeleRCWiFiGateway',generic),('balancer-existing','bridge/TT_Balancer_ESP32S3',generic)]
elif product=='telerc_go':
 targets=[('mini-four-motor-mx1508','firmware/go/TeleRC_MiniRover_WiFi',generic),('tt-car-jog-steering','firmware/go/TeleRC_Go_TT_Car',generic),('balancer-sbrb-candidate','bridge/TT_Balancer_ESP32S3',generic)]
else:
 targets=[(p.name,str(p),t3) for p in sorted(Path('firmware/mission/sketches').glob('TeleRCMission_*'))]
out=Path('firmware-dist');out.mkdir(exist_ok=True);evidence=Path('firmware-v1-evidence');evidence.mkdir(exist_ok=True)
core=Path.home()/'.arduino15/packages/esp32/hardware/esp32/3.3.2'
boot=core/'tools/partitions/boot_app0.bin'
builds=[]
for role,folder,fqbn in targets:
 path=Path(folder);target=out/role;target.mkdir(exist_ok=True)
 build=Path(os.environ.get('RUNNER_TEMP','/tmp'))/('v1-build-'+role)
 command=['arduino-cli','compile','--fqbn',fqbn,'--output-dir',str(build.resolve())]
 if Path('bridge/libraries').is_dir():command+=['--libraries',str(Path('bridge/libraries').resolve())]
 command+=[str(path.resolve())]
 with (evidence/(role+'.log')).open('w') as log: subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT)
 images=[]
 for suffix,offset,kind in [('.ino.bin','0x10000','application'),('.ino.bootloader.bin','0x0','bootloader'),('.ino.partitions.bin','0x8000','partitions')]:
  original=build/(path.name+suffix)
  if not original.is_file() or not original.stat().st_size: raise RuntimeError('Missing compiled image '+str(original))
  dest=target/original.name;shutil.copyfile(original,dest)
  images.append(dict(file=str(dest.relative_to(out)),offset=offset,kind=kind,bytes=dest.stat().st_size,sha256=hashlib.sha256(dest.read_bytes()).hexdigest()))
 dest=target/'boot_app0.bin';shutil.copyfile(boot,dest)
 images.append(dict(file=str(dest.relative_to(out)),offset='0xe000',kind='boot_app0',bytes=dest.stat().st_size,sha256=hashlib.sha256(dest.read_bytes()).hexdigest()))
 builds.append(dict(role=role,source=folder,fqbn=fqbn,images=images))
info=dict(baseline='1.0',product=product,source_commit=os.environ['GITHUB_SHA'],esp32_core='3.3.2',radiolib='7.2.1',hardware_validation='BLOCKED',builds=builds,mission_examples_rf_enabled=False if product=='PC-TeleRC' else None)
(out/'FIRMWARE_MANIFEST.json').write_text(json.dumps(info,indent=2)+'\n')
(out/'FLASH.md').write_text('Candidate images only. Match the exact role, board and vehicle wiring. Use manifest offsets; preserve NVS. Never flash a merged/NVS image. LoRa Mission examples are keyless and RF OFF: generate a private matching fleet and compile locally before deployment. Physical acceptance remains BLOCKED.\n')
(out/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(out).as_posix()+'\n' for p in sorted(out.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.txt'))
with zipfile.ZipFile(out/(product+'-v1.0-firmware.zip'),'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(out.rglob('*')):
  if p.is_file() and p.suffix!='.zip':z.write(p,p.relative_to(out).as_posix())
print('PASS: compiled and packaged',len(builds),'actual board profiles; hardware acceptance pending')

"""Compile role/profile groups independently; release jobs run groups in parallel."""
from pathlib import Path
import re, shutil, subprocess, sys, zipfile
root=Path(__file__).resolve().parents[1]
group=sys.argv[1]
profiles={
 'BASE':[('BASE',0,0,1),('BASE_RELAY1',1,0,1),('BASE_RELAY2',2,0,1)],
 'ROVER':[('ROVER_WIFI',0,1,1),('ROVER_LORA',0,0,1),('ROVER_RELAY1',1,0,1),('ROVER_RELAY2',2,0,1)],
 'NODE':[('NODE',1,0,1),('NODE1_RELAY2',2,0,1),('NODE2_RELAY2',2,0,2)],
}
for name,relays,wifi,index in profiles[group]:
 source=root/'firmware'/('TeleRCLoRa_'+group)
 folder=root/'firmware-build-input'/name
 shutil.copytree(source,folder,dirs_exist_ok=True)
 ino=folder/('TeleRCLoRa_'+group+'.ino')
 text=ino.read_text()
 for key,value in {'TELERC_RELAY_COUNT':relays,'TELERC_TRANSPORT_WIFI':wifi,'TELERC_NODE_INDEX':index}.items():
  text=re.sub(r'(#define '+key+r')\s+\d+',lambda m:m[1]+' '+str(value),text)
 ino.unlink();(folder/(name+'.ino')).write_text(text)
 subprocess.run(['arduino-cli','compile','--fqbn','esp32:esp32:lilygo_t3s3:CDCOnBoot=cdc,Revision=Radio_SX1262,PSRAM=enabled',
                 '--output-dir',str(root/'firmware-build'/name),str(folder)],check=True)
output=root/'release-dist';output.mkdir(exist_ok=True)
archive=output/f'TeleRC-Firmware-v0.1.2rc2-LilyGO-{group}-targets.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for name,*_ in profiles[group]:
  for p in sorted((root/'firmware-build'/name).rglob('*')):
   if p.is_file():z.write(p,p.relative_to(root/'firmware-build'))
 z.write(root/'docs/LILYGO-SKETCH-RELAYS.md','READ-ME-FIRST.md')
print(archive)

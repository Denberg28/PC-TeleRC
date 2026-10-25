"""Verify current source, public firmware and map-only frozen Windows evidence."""
from pathlib import Path
import hashlib,json,sys,zipfile
from release_safety import check_archive
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from pctelerc.fleet_contract import FROZEN_CHECKS
FW_NAME='TeleRC-Fleet-LoRa-v0.5.0rc1.zip'
VERSION='1.2.0rc3'
FIRMWARE_COMMIT='6ba272867165eee31e21792ea259fce7225579f7'

def sha(path):
 with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def verify_firmware(path,commit):
 check_archive(path)
 with zipfile.ZipFile(path) as z:
  prefix=FW_NAME[:-4]+'/'
  report=json.loads(z.read(prefix+'BUILD_REPORT.json'))
  if report['source_commit']!=commit or report['version']!='0.5.0rc1' or len(report['builds'])!=11 or any(b['result']!='PASS' for b in report['builds']):raise ValueError('Fleet board qualification mismatch')
  expected={('public','TeleRCFleet_'+r) for r in ('BASE','ROVER_001','NODE_1','NODE_3','NODE_200')} | {('private-test','TeleRCFleet_'+r) for r in ('BASE','ROVER_001','ROVER_003','ROVER_020','NODE_200')} | {('converter','TeleRC_4x_BTS7960_PWM_GlitchFilter')}
  if {(b['profile'],b['role']) for b in report['builds']}!=expected:raise ValueError('Fleet role build matrix mismatch')
  for build in report['builds']:
   images=build.get('images',[])
   if build['profile']=='private-test':
    if images:raise ValueError('Private images distributed')
   else:
    if len(images)!=4 or {i['offset'] for i in images}!={'0x0','0x8000','0xe000','0x10000'}:raise ValueError('Incomplete board image set')
    for image in images:
     data=z.read(prefix+image['file'])
     if len(data)!=image['bytes'] or hashlib.sha256(data).hexdigest()!=image['sha256']:raise ValueError('Board image checksum mismatch')
  if report['private_binaries_distributed'] or report['private_keys_distributed'] or report['hardware_validation']!='NOT TESTED':raise ValueError('Invalid firmware boundary/qualification')
  listed={}
  for row in z.read(prefix+'SHA256SUMS.txt').decode().splitlines():
   digest,name=row.split('  ',1)
   if name in listed or hashlib.sha256(z.read(prefix+name)).hexdigest()!=digest:raise ValueError('Fleet firmware internal checksum mismatch')
   listed[name]=digest
  actual={n[len(prefix):] for n in z.namelist() if not n.endswith('/')}
  if actual!=set(listed)|{'SHA256SUMS.txt'}:raise ValueError('Unexpected firmware archive members')
 return sha(path)

def verify_report(report):
 if report.get('version')!=VERSION or report.get('passed') is not True or not FROZEN_CHECKS.issubset(report.get('checks',{})) or any(v is not True for v in report['checks'].values()):raise ValueError('Map-only frozen Windows checks failed')

"""Fleet publication needs the current Windows app and complete matching firmware."""
import hashlib,json,sys,zipfile
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import publish_fleet as release
from fleet_release_support import FW_NAME,FROZEN_CHECKS
COMMIT='a'*40

def archive(path,entries):
 with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
  for name,data in entries.items():z.writestr(name,data)

def seal(root):
 (root/'SHA256SUMS.txt').write_text(''.join(release.sha(p)+'  '+p.name+'\n' for p in sorted(root.iterdir()) if p.name!='SHA256SUMS.txt'))

@pytest.fixture
def bundle(tmp_path,monkeypatch):
 monkeypatch.setattr(release,'FIRMWARE_COMMIT',COMMIT)
 root=tmp_path
 for name in release.REQUIRED-{'SHA256SUMS.txt'}:(root/name).write_bytes(b'fixture')
 records=[];entries={};prefix=FW_NAME[:-4]+'/'
 roles=[('public','TeleRCFleet_'+r) for r in ('BASE','ROVER_001','NODE_1','NODE_3','NODE_200')]+[('private-test','TeleRCFleet_'+r) for r in ('BASE','ROVER_001','ROVER_003','ROVER_020','NODE_200')]+[('converter','TeleRC_4x_BTS7960_PWM_GlitchFilter')]
 for kind,role in roles:
  build=dict(profile=kind,role=role,result='PASS')
  if kind!='private-test':
   build['images']=[]
   for index,offset in enumerate(('0x0','0x8000','0xe000','0x10000')):
    name=f'binaries/{role}/{index}.bin';data=(role+str(index)).encode();entries[name]=data
    build['images'].append(dict(file=name,offset=offset,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
  records.append(build)
 entries['BUILD_REPORT.json']=json.dumps(dict(source_commit=COMMIT,version='0.5.0rc1',builds=records,
  private_binaries_distributed=False,private_keys_distributed=False,hardware_validation='NOT TESTED')).encode()
 entries['Config.h']=b'#define PROVISIONED 0\n'
 entries['SHA256SUMS.txt']=''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in entries.items()).encode()
 archive(root/FW_NAME,{prefix+k:v for k,v in entries.items()});digest=release.sha(root/FW_NAME)
 archive(root/f'PC-TeleRC-portable-v{release.VERSION}.zip',{
  'frozen-ui-check.json':json.dumps(dict(version=release.VERSION,passed=True,checks=dict.fromkeys(FROZEN_CHECKS,True))),
  'build-provenance.json':json.dumps(dict(version=release.VERSION,source_commit=COMMIT,firmware_sha256=digest)),
  'Fleet-firmware/'+FW_NAME:(root/FW_NAME).read_bytes()})
 archive(root/f'PC-TeleRC-Mission-v{release.VERSION}-source.zip',{f'PC-TeleRC-v{release.VERSION}/SOURCE_COMMIT.txt':COMMIT})
 archive(root/'test-evidence.zip',{'windows-tests.xml':'<testsuites><testsuite tests="10" errors="0" failures="0"/></testsuites>'})
 (root/'RELEASE_STATUS.json').write_text(json.dumps(dict(version=release.VERSION,source_commit=COMMIT,firmware_sha256=digest)))
 seal(root);return root

def test_matching_complete_fleet_build_passes(bundle):release.validate(bundle,COMMIT)

def test_another_source_cannot_be_published(bundle):
 with pytest.raises(ValueError,match='source/version mismatch'):release.validate(bundle,'b'*40)

def test_resealed_installer_removal_is_rejected(bundle):
 (bundle/f'PC-TeleRC-Setup-v{release.VERSION}.exe').unlink();seal(bundle)
 with pytest.raises(ValueError,match='Missing'):release.validate(bundle,COMMIT)

def test_missing_frozen_fleet_check_is_rejected_even_with_valid_checksums(bundle):
 path=bundle/f'PC-TeleRC-portable-v{release.VERSION}.zip'
 with zipfile.ZipFile(path) as z:entries={n:z.read(n) for n in z.namelist()}
 report=json.loads(entries['frozen-ui-check.json']);del report['checks']['no_video_runtime']
 entries['frozen-ui-check.json']=json.dumps(report);archive(path,entries);seal(bundle)
 with pytest.raises(ValueError,match='frozen'):release.validate(bundle,COMMIT)

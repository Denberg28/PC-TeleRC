"""Publish only the verified Windows build and pinned public firmware baseline."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from fleet_release_support import FW_NAME as NAME, verify_firmware, verify_report, VERSION, FIRMWARE_COMMIT
from mission_release_support import REQUIRED_CHECKS
from release_safety import check_directory

ROOT = Path(__file__).resolve().parents[1]
TAG = 'v'+VERSION
OUT = ROOT/'fleet-release'
REQUIRED = {f'PC-TeleRC-portable-v{VERSION}.zip', f'PC-TeleRC-Setup-v{VERSION}.exe',
    f'PC-TeleRC-Mission-v{VERSION}-source.zip', NAME, 'README.md',
    'FIRMWARE-COMPATIBILITY.md', 'RELEASE_STATUS.json', 'test-evidence.zip', 'SHA256SUMS.txt'}

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def validate(folder, commit):
    folder = Path(folder)
    check_directory(folder)
    if {p.name for p in folder.iterdir()} != REQUIRED:
        raise ValueError('Missing or unexpected firmware-support release assets')
    lines = (folder/'SHA256SUMS.txt').read_text().splitlines()
    listed = dict(line.split('  ', 1)[::-1] for line in lines)
    if len(lines) != len(listed):
        raise ValueError('Duplicate checksum manifest entry')
    actual = {p.name:sha(p) for p in folder.iterdir() if p.name != 'SHA256SUMS.txt'}
    if listed != actual:
        raise ValueError('Release checksum mismatch')
    firmware_sha = verify_firmware(folder/NAME, FIRMWARE_COMMIT)
    status = json.loads((folder/'RELEASE_STATUS.json').read_text())
    if status['source_commit'] != commit or status['version'] != VERSION or status['firmware_sha256'] != firmware_sha:
        raise ValueError('Release source/version mismatch')
    with zipfile.ZipFile(folder/f'PC-TeleRC-portable-v{VERSION}.zip') as z:
        report = json.loads(z.read('frozen-ui-check.json'))
        verify_report(report)
        provenance = json.loads(z.read('build-provenance.json'))
        if provenance['source_commit'] != commit or provenance['version'] != VERSION or provenance['firmware_sha256'] != firmware_sha:
            raise ValueError('Portable provenance mismatch')
        if hashlib.sha256(z.read('Fleet-firmware/'+NAME)).hexdigest() != firmware_sha:
            raise ValueError('Portable firmware baseline changed')
    with zipfile.ZipFile(folder/f'PC-TeleRC-Mission-v{VERSION}-source.zip') as z:
        if z.read(f'PC-TeleRC-v{VERSION}/SOURCE_COMMIT.txt').decode().strip() != commit:
            raise ValueError('Source snapshot mismatch')
    with zipfile.ZipFile(folder/'test-evidence.zip') as z:
        suites = ET.fromstring(z.read('windows-tests.xml'))
        if sum(int(s.get('tests', 0)) for s in suites.iter('testsuite')) < 1 or any(int(s.get(k,0)) for s in suites.iter('testsuite') for k in ('errors','failures')):
            raise ValueError('Windows regression evidence failed')
    return actual

def gh(*args):
    return subprocess.check_output(['gh', *args], text=True)

def main():
    commit = os.environ['GITHUB_SHA']
    repo = os.environ['GITHUB_REPOSITORY']
    OUT.mkdir()
    for name in (f'PC-TeleRC-portable-v{VERSION}.zip',f'PC-TeleRC-Setup-v{VERSION}.exe',f'PC-TeleRC-Mission-v{VERSION}-source.zip'):
        shutil.copyfile(ROOT/'incoming'/name, OUT/name)
    shutil.copyfile(ROOT/'incoming'/NAME, OUT/NAME)
    firmware_sha = verify_firmware(OUT/NAME, FIRMWARE_COMMIT)
    shutil.copyfile(ROOT/f'docs/releases/v{VERSION}.md', OUT/'README.md')
    shutil.copyfile(ROOT/'docs/FLEET-STATION.md', OUT/'FIRMWARE-COMPATIBILITY.md')
    with zipfile.ZipFile(OUT/'test-evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in ('frozen-ui-check.json','windows-tests.xml','frozen-stdout.txt','frozen-stderr.txt'):
            z.write(ROOT/'incoming'/name, name)
    (OUT/'RELEASE_STATUS.json').write_text(json.dumps(dict(version=VERSION,source_commit=commit,
        channel='candidate',hardware_validation='NOT_TESTED',windows_build_gates='PASS',
        firmware_source_commit=FIRMWARE_COMMIT,firmware_sha256=firmware_sha,
        firmware_target_builds=11,private_keys_included=False,integrated_fpv=False,
        mission_rover_ids='1..20; measured radio capacity admission',normal_pc_arm=True),indent=2)+'\n')
    (OUT/'SHA256SUMS.txt').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in sorted(OUT.iterdir())))
    validate(OUT, commit)
    releases = json.loads(gh('api',f'repos/{repo}/releases?per_page=100'))
    if any(r['tag_name']==TAG for r in releases):
        raise ValueError('Refusing to replace an existing release')
    gh('release','create',TAG,'--repo',repo,'--target',commit,'--draft','--prerelease','--latest=false',
       '--title',f'PC TeleRC v{VERSION} — Map drag and coordinate correction','--notes-file',str(OUT/'README.md'),
       *[str(p) for p in sorted(OUT.iterdir())])
    release = next(r for r in json.loads(gh('api',f'repos/{repo}/releases?per_page=100')) if r['tag_name']==TAG)
    expected = {p.name:sha(p) for p in OUT.iterdir()}
    if not release['draft'] or release['target_commitish'] != commit or {a['name'] for a in release['assets']} != set(expected) or len(release['assets']) != len(expected):
        raise ValueError('Uploaded draft identity/assets mismatch')
    with tempfile.TemporaryDirectory() as tmp:
        for asset in release['assets']:
            if asset['state'] != 'uploaded' or asset.get('digest') != 'sha256:'+expected[asset['name']]:
                raise ValueError('Uploaded asset hash mismatch')
            path = Path(tmp)/asset['name']
            with path.open('wb') as stream:
                subprocess.run(['gh','api',f'repos/{repo}/releases/assets/{asset["id"]}','-H','Accept: application/octet-stream'],stdout=stream,check=True)
            if sha(path) != expected[asset['name']]:
                raise ValueError('Downloaded asset hash mismatch')
        validate(tmp, commit)
    gh('api','--method','PATCH',f'repos/{repo}/releases/{release["id"]}',
       '-F','draft=false','-F','prerelease=true','-f','make_latest=false')
    published = json.loads(gh('api',f'repos/{repo}/releases/{release["id"]}'))
    if published['draft'] or not published['prerelease'] or published['target_commitish'] != commit:
        raise ValueError('Published release identity mismatch')
    print('Published verified Windows candidate:',published['html_url'])

if __name__ == '__main__':
    main()

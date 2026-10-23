"""Stage, download-verify and publish the exact reviewed v1.0.1 build."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

from manual_companion import DIGEST, NAME, verify as verify_manual
from mission_release_support import REQUIRED_CHECKS
from release_safety import check_directory

VERSION = '1.0.1'
TAG = 'v' + VERSION
ROOT = Path(__file__).resolve().parents[1]
ROLES = {'manual-' + role for role in ('BASE','ROVER','NODE1','NODE2')} | {
    'TeleRCMission_' + role for role in ('BASE','ROVER_001','NODE_1','NODE_2')}
REQUIRED = {f'PC-TeleRC-portable-v{VERSION}.zip', f'PC-TeleRC-Setup-v{VERSION}.exe',
    f'PC-TeleRC-Mission-v{VERSION}-source.zip', f'PC-TeleRC-v{VERSION}-firmware.zip',
    'TeleRC-LoRa-Mission-v0.2.0rc1-sketches.zip', NAME,
    'FIRMWARE-COMPATIBILITY.md', 'START_HERE.md', 'RELEASE_STATUS.json',
    'PC-TeleRC-v1.0.1-test-evidence.zip', 'SHA256SUMS.txt'}


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def checksums(folder):
    return {p.name: digest(p) for p in sorted(Path(folder).iterdir())
            if p.is_file() and p.name != 'SHA256SUMS.txt'}


def validate(folder, commit):
    folder = Path(folder)
    check_directory(folder)
    names = {p.name for p in folder.iterdir() if p.is_file() and p.stat().st_size > 0}
    if not REQUIRED.issubset(names):
        raise ValueError('Missing release assets: ' + ', '.join(sorted(REQUIRED - names)))
    lines = (folder / 'SHA256SUMS.txt').read_text().splitlines()
    listed = {}
    for line in lines:
        match = re.fullmatch(r'([a-f0-9]{64})  ([^/\\]+)', line)
        if not match or match[2] in listed:
            raise ValueError('Invalid final checksum manifest')
        listed[match[2]] = match[1]
    if listed != checksums(folder):
        raise ValueError('Release checksum mismatch')
    status = json.loads((folder / 'RELEASE_STATUS.json').read_text())
    if (status['source_commit'] != commit or status['version'] != VERSION
            or status['software_build_gates'] != 'PASS'
            or status['hardware_validation'] != 'NOT_TESTED'):
        raise ValueError('Release provenance/qualification mismatch')
    if digest(folder / NAME) != DIGEST:
        raise ValueError('Manual companion changed')
    with zipfile.ZipFile(folder / f'PC-TeleRC-portable-v{VERSION}.zip') as archive:
        report = json.loads(archive.read('frozen-ui-check.json'))
        checks = report.get('checks', {})
        if (report.get('version') != VERSION or report.get('passed') is not True
                or not REQUIRED_CHECKS.issubset(checks)
                or any(value is not True for value in checks.values())):
            raise ValueError('Frozen Windows verification failed')
        provenance = json.loads(archive.read('build-provenance.json'))
        if provenance['source_commit'] != commit or provenance['version'] != VERSION:
            raise ValueError('Portable provenance mismatch')
        if hashlib.sha256(archive.read('Manual-firmware/' + NAME)).hexdigest() != DIGEST:
            raise ValueError('Portable manual companion mismatch')
    with zipfile.ZipFile(folder / f'PC-TeleRC-Mission-v{VERSION}-source.zip') as archive:
        if archive.read(f'PC-TeleRC-v{VERSION}/SOURCE_COMMIT.txt').decode().strip() != commit:
            raise ValueError('Source snapshot provenance mismatch')
    with zipfile.ZipFile(folder / f'PC-TeleRC-v{VERSION}-firmware.zip') as archive:
        manifest = json.loads(archive.read('FIRMWARE_MANIFEST.json'))
        if (manifest['source_commit'] != commit or manifest['mission_examples_rf_enabled'] is not False
                or len(manifest['builds']) != 8 or {b['role'] for b in manifest['builds']} != ROLES):
            raise ValueError('Incomplete or mismatched firmware builds')
        for build in manifest['builds']:
            if {i['offset'] for i in build['images']} != {'0x0','0x8000','0xe000','0x10000'} or len(build['images']) != 4:
                raise ValueError('Incomplete separate-image role set')
            for image in build['images']:
                data = archive.read(image['file'])
                if len(data) != image['bytes'] or hashlib.sha256(data).hexdigest() != image['sha256']:
                    raise ValueError('Firmware image checksum mismatch')
    return listed


def stage(incoming, out, commit):
    out = Path(out)
    if out.exists():
        raise ValueError('Refusing to reuse an existing final staging directory')
    out.mkdir()
    for source in sorted(Path(incoming).rglob('*')):
        if source.is_file() and (source.parent.name == 'release-dist'
                or source.parent.name == 'firmware-dist' and source.suffix == '.zip'):
            if source.name in ('SHA256SUMS.txt','SOURCE_COMMIT.txt'):
                continue
            target = out / source.name
            if target.exists() and digest(target) != digest(source):
                raise ValueError('Conflicting release asset names')
            shutil.copyfile(source, target)
    shutil.copyfile(verify_manual(), out / NAME)
    shutil.copyfile(ROOT / 'docs/FIRMWARE-COMPATIBILITY-v1.0.1.md', out / 'FIRMWARE-COMPATIBILITY.md')
    shutil.copyfile(ROOT / 'START-HERE.md', out / 'START_HERE.md')
    with zipfile.ZipFile(out / 'PC-TeleRC-v1.0.1-test-evidence.zip','w',zipfile.ZIP_DEFLATED) as writer:
        for source in sorted(Path(incoming).rglob('*')):
            if source.is_file() and source.suffix in ('.xml','.json','.log','.txt'):
                writer.write(source,source.relative_to(incoming).as_posix())
    (out / 'RELEASE_STATUS.json').write_text(json.dumps(dict(version=VERSION,
        source_commit=commit, workflow_run=os.environ['GITHUB_RUN_ID'],
        software_build_gates='PASS', channel='stable', hardware_validation='NOT_TESTED',
        manual_firmware='1.0.1', mission_firmware='0.2.0rc1',
        mission_example_rf='OFF; privately provision matching roles before use'),indent=2)+'\n')
    (out / 'SHA256SUMS.txt').write_text(''.join(h+'  '+n+'\n' for n,h in checksums(out).items()))
    validate(out, commit)


def gh(*args):
    return subprocess.check_output(['gh', *args], text=True)


def publish(folder, commit, *, resume=False):
    validate(folder, commit)
    repo = os.environ['GITHUB_REPOSITORY']
    # A published tag is immutable here; never replace earlier release assets.
    releases = json.loads(gh('api',f'repos/{repo}/releases?per_page=100'))
    existing = next((item for item in releases if item['tag_name'] == TAG), None)
    if existing is not None and (not resume or not existing['draft'] or existing['target_commitish'] != commit):
        raise ValueError('Cannot replace or resume a different/published release')
    refs = json.loads(gh('api', f'repos/{repo}/git/matching-refs/tags/{TAG}'))
    for ref in refs:
        if ref['ref'] == 'refs/tags/' + TAG and (ref['object']['type'] != 'commit' or ref['object']['sha'] != commit):
            raise ValueError('Existing release tag points at another source revision')
    if existing is None:
        gh('release','create',TAG,'--repo',repo,'--target',commit,'--draft',
           '--title','PC TeleRC v1.0.1 — FPV cockpit and matched firmware',
           '--notes-file',str(ROOT / 'docs/releases/v1.0.1.md'),
           *[str(p) for p in sorted(Path(folder).iterdir()) if p.is_file()])
    # Draft releases are not reliably returned by the published-by-tag endpoint.
    drafts = json.loads(gh('api', f'repos/{repo}/releases?per_page=100'))
    release = next((item for item in drafts if item['tag_name'] == TAG), None)
    if release is None or not release['draft'] or release['target_commitish'] != commit:
        raise ValueError('Uploaded draft provenance mismatch')
    expected = {p.name: digest(p) for p in Path(folder).iterdir() if p.is_file()}
    assets = release['assets']
    if len(assets) != len(expected) or {a['name'] for a in assets} != set(expected):
        raise ValueError('Incomplete uploaded release')
    for asset in assets:
        if asset['state'] != 'uploaded' or asset.get('digest') != 'sha256:' + expected[asset['name']]:
            raise ValueError('Uploaded asset mismatch')
    with tempfile.TemporaryDirectory() as temp:
        for asset in assets:
            with (Path(temp) / asset['name']).open('wb') as output:
                subprocess.run(['gh','api',f'repos/{repo}/releases/assets/{asset["id"]}',
                    '-H','Accept: application/octet-stream'], stdout=output, check=True)
        if {p.name:digest(p) for p in Path(temp).iterdir()} != expected:
            raise ValueError('Downloaded asset mismatch')
        validate(temp, commit)
    gh('api','--method','PATCH',f'repos/{repo}/releases/{release["id"]}',
       '-F','draft=false','-F','prerelease=false','-f','make_latest=true',
       '-f','target_commitish=' + commit)
    final = json.loads(gh('api',f'repos/{repo}/releases/tags/{TAG}'))
    if final['draft'] or final['prerelease'] or final['target_commitish'] != commit:
        raise ValueError('Final release state differs from verified build')
    tag = json.loads(gh('api', f'repos/{repo}/git/ref/tags/{TAG}'))
    if tag['object']['type'] != 'commit' or tag['object']['sha'] != commit:
        raise ValueError('Published tag does not identify the tested source revision')
    print('Published stable:', final['html_url'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--incoming')
    source.add_argument('--existing', help='Resume verification of an unchanged saved final asset set')
    parser.add_argument('--out', default='stable-release')
    parser.add_argument('--commit', required=True)
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--resume-draft', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch('[0-9a-f]{40}', args.commit):
        parser.error('Exact committed source SHA required')
    if args.existing:
        args.out = args.existing
        validate(args.out, args.commit)
    else:
        stage(args.incoming, args.out, args.commit)
    if args.publish:
        publish(args.out, args.commit, resume=args.resume_draft)

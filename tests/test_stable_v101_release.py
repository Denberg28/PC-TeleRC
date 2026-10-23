"""Stable publication must reject stale, incomplete or tampered packages."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import publish_v1_release as release

COMMIT = 'a' * 40


def zip_file(path, entries):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as writer:
        for name, data in entries.items():
            writer.writestr(name, data)


def seal(folder):
    (folder / 'SHA256SUMS.txt').write_text(''.join(h+'  '+n+'\n'
        for n,h in release.checksums(folder).items()))


@pytest.fixture
def bundle(tmp_path):
    for name in release.REQUIRED - {'SHA256SUMS.txt'}:
        (tmp_path / name).write_text('test fixture')
    shutil.copyfile(release.verify_manual(), tmp_path / release.NAME)
    report = dict(version='1.0.1', passed=True, checks=dict.fromkeys(release.REQUIRED_CHECKS, True))
    zip_file(tmp_path / 'PC-TeleRC-portable-v1.0.1.zip', {
        'frozen-ui-check.json': json.dumps(report),
        'build-provenance.json': json.dumps(dict(version='1.0.1', source_commit=COMMIT)),
        'Manual-firmware/' + release.NAME: (tmp_path / release.NAME).read_bytes()})
    zip_file(tmp_path / 'PC-TeleRC-Mission-v1.0.1-source.zip', {'PC-TeleRC-v1.0.1/SOURCE_COMMIT.txt': COMMIT})
    entries, builds = {}, []
    for role in sorted(release.ROLES):
        images = []
        for kind, offset in [('bootloader','0x0'), ('partitions','0x8000'), ('boot_app0','0xe000'), ('application','0x10000')]:
            name, data = role+'/'+kind+'.bin', (role+kind).encode()
            entries[name] = data
            images.append(dict(file=name, offset=offset, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
        builds.append(dict(role=role, images=images))
    entries['FIRMWARE_MANIFEST.json'] = json.dumps(dict(source_commit=COMMIT,
        mission_examples_rf_enabled=False, builds=builds))
    zip_file(tmp_path / 'PC-TeleRC-v1.0.1-firmware.zip', entries)
    zip_file(tmp_path / 'TeleRC-LoRa-Mission-v0.2.0rc1-sketches.zip', {'README.md':'public RF-OFF example fixture'})
    zip_file(tmp_path / 'PC-TeleRC-v1.0.1-test-evidence.zip', {'test.txt':'fixture'})
    (tmp_path / 'RELEASE_STATUS.json').write_text(json.dumps(dict(source_commit=COMMIT,
        version='1.0.1',software_build_gates='PASS',hardware_validation='NOT_TESTED')))
    seal(tmp_path)
    return tmp_path


def edit_zip(path, name, mutate):
    with zipfile.ZipFile(path) as reader:
        entries = {n:reader.read(n) for n in reader.namelist()}
    entries[name] = mutate(entries[name])
    zip_file(path, entries)


def test_complete_matching_bundle_passes(bundle):
    assert release.validate(bundle, COMMIT) == release.checksums(bundle)


def test_missing_installer_cannot_publish(bundle, monkeypatch):
    (bundle / 'PC-TeleRC-Setup-v1.0.1.exe').unlink()
    monkeypatch.setattr(release,'gh',lambda *_: pytest.fail('Must not contact publication API'))
    with pytest.raises(ValueError, match='Missing release'):
        release.publish(bundle, COMMIT)


def test_tampered_asset_cannot_publish(bundle, monkeypatch):
    (bundle / 'PC-TeleRC-Setup-v1.0.1.exe').write_bytes(b'changed installer fixture')
    monkeypatch.setattr(release,'gh',lambda *_: pytest.fail('Must not contact publication API'))
    with pytest.raises(ValueError, match='checksum mismatch'):
        release.publish(bundle, COMMIT)


def test_existing_tag_cannot_be_moved_to_a_different_build(bundle, monkeypatch):
    monkeypatch.setenv('GITHUB_REPOSITORY', 'example/project')
    def api(*args):
        if args == ('api', 'repos/example/project/releases?per_page=100'):
            return '[]'
        if args == ('api', 'repos/example/project/git/matching-refs/tags/v1.0.1'):
            return json.dumps([dict(ref='refs/tags/v1.0.1',object=dict(type='commit',sha='b'*40))])
        pytest.fail('Must not upload or publish after detecting a different tag')
    monkeypatch.setattr(release,'gh',api)
    with pytest.raises(ValueError, match='another source'):
        release.publish(bundle, COMMIT)


def test_incomplete_remote_assets_leave_the_release_unpublished(bundle, monkeypatch):
    monkeypatch.setenv('GITHUB_REPOSITORY', 'example/project')
    def api(*args):
        if args[0] == 'api' and ('releases?' in args[1] or 'matching-refs' in args[1]):
            return '[]'
        if args[:2] == ('release','create'):
            return ''
        if args == ('api','repos/example/project/releases/tags/v1.0.1'):
            return json.dumps(dict(assets=[]))
        pytest.fail('Must not publish incomplete remote assets')
    monkeypatch.setattr(release,'gh',api)
    with pytest.raises(ValueError, match='Incomplete uploaded'):
        release.publish(bundle, COMMIT)


@pytest.mark.parametrize('variant', ['wrong_source','frozen_false','missing_check','missing_role','image_tamper'])
def test_internal_build_evidence_is_required_even_with_updated_outer_hashes(bundle, variant):
    if variant in ('wrong_source','frozen_false','missing_check'):
        name = 'build-provenance.json' if variant == 'wrong_source' else 'frozen-ui-check.json'
        def mutate(data):
            record = json.loads(data)
            if variant == 'wrong_source': record['source_commit'] = 'b'*40
            elif variant == 'frozen_false': record['passed'] = False
            else: record['checks'].pop('fpv_overlay')
            return json.dumps(record)
        edit_zip(bundle/'PC-TeleRC-portable-v1.0.1.zip',name,mutate)
    elif variant == 'missing_role':
        def mutate(data):
            record=json.loads(data);record['builds'].pop();return json.dumps(record)
        edit_zip(bundle/'PC-TeleRC-v1.0.1-firmware.zip','FIRMWARE_MANIFEST.json',mutate)
    else:
        edit_zip(bundle/'PC-TeleRC-v1.0.1-firmware.zip','manual-BASE/application.bin',lambda _:b'altered firmware fixture')
    seal(bundle)
    with pytest.raises(ValueError):
        release.validate(bundle, COMMIT)

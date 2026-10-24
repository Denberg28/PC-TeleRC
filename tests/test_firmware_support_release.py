"""Publication must reject mismatched Windows and nested firmware evidence."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import firmware_baseline as baseline
import publish_firmware_support as release

COMMIT = 'a'*40


def make_zip(path, entries):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            z.writestr(name, data)


def seal(folder):
    (folder/'SHA256SUMS.txt').write_text(''.join(release.sha(p)+'  '+p.name+'\n'
        for p in sorted(folder.iterdir()) if p.name != 'SHA256SUMS.txt'))


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    for name in release.REQUIRED-{'SHA256SUMS.txt'}:
        (tmp_path/name).write_bytes(b'fixture')
    make_zip(tmp_path/baseline.NAME, {baseline.NAME[:-4]+'/BUILD_REPORT.json':json.dumps(
        dict(source_commit=baseline.SOURCE, builds=[{'result':'PASS'}]*11))})
    data = (tmp_path/baseline.NAME).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    monkeypatch.setattr(baseline, 'SHA256', digest)
    monkeypatch.setattr(release, 'SHA256', digest)
    report = dict(version=release.VERSION, passed=True,
        checks=dict.fromkeys(release.REQUIRED_CHECKS|{'firmware_baseline_identity'}, True))
    make_zip(tmp_path/f'PC-TeleRC-portable-v{release.VERSION}.zip', {
        'frozen-ui-check.json':json.dumps(report),
        'build-provenance.json':json.dumps(dict(version=release.VERSION,
            source_commit=COMMIT,firmware_baseline_sha256=digest)),
        'Firmware-baseline/'+baseline.NAME:data})
    make_zip(tmp_path/f'PC-TeleRC-Mission-v{release.VERSION}-source.zip',
        {f'PC-TeleRC-v{release.VERSION}/SOURCE_COMMIT.txt':COMMIT})
    make_zip(tmp_path/'test-evidence.zip', {'windows-tests.xml':
        '<testsuites><testsuite tests="20" errors="0" failures="0"/></testsuites>'})
    (tmp_path/'RELEASE_STATUS.json').write_text(json.dumps(dict(version=release.VERSION,
        source_commit=COMMIT,firmware_baseline_sha256=digest)))
    seal(tmp_path)
    return tmp_path


def test_matching_windows_and_baseline_bundle_passes(bundle):
    release.validate(bundle, COMMIT)


def test_missing_installer_rejected_before_publication(bundle):
    (bundle/f'PC-TeleRC-Setup-v{release.VERSION}.exe').unlink()
    with pytest.raises(ValueError, match='Missing'):
        release.validate(bundle, COMMIT)


@pytest.mark.parametrize('entry,data,match', [
    ('frozen-ui-check.json',json.dumps(dict(version=release.VERSION,passed=True,checks={})), 'Frozen'),
    ('Firmware-baseline/'+baseline.NAME,b'wrong firmware set', 'baseline changed'),
    ('build-provenance.json',json.dumps(dict(version=release.VERSION,source_commit='b'*40,firmware_baseline_sha256='wrong')), 'provenance')])
def test_resealed_portable_with_wrong_evidence_rejected(bundle, entry, data, match):
    path = bundle/f'PC-TeleRC-portable-v{release.VERSION}.zip'
    with zipfile.ZipFile(path) as z:
        entries = {n:z.read(n) for n in z.namelist()}
    if entry.startswith('Firmware-baseline/'):
        import io
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as z:
            z.writestr('README.md', data)
        data = stream.getvalue()
    entries[entry] = data
    make_zip(path, entries)
    seal(bundle)
    with pytest.raises(ValueError, match=match):
        release.validate(bundle, COMMIT)


def test_resealed_failed_windows_tests_rejected(bundle):
    make_zip(bundle/'test-evidence.zip', {'windows-tests.xml':
        '<testsuites><testsuite tests="20" errors="0" failures="1"/></testsuites>'})
    seal(bundle)
    with pytest.raises(ValueError, match='regression'):
        release.validate(bundle, COMMIT)

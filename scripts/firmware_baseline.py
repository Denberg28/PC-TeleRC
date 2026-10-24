"""Reuse the exact public board-qualified baseline; never download private profiles."""
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile
from release_safety import check_archive

NAME = 'TeleRC-ArduRover-Baseline-v1.1.0rc1.zip'
SHA256 = '68fb0525b4ba9e9756f9575f09fb5db699e22f417ee559e0a8e24ed38fb8b783'
SOURCE = '7cf6c9ecf81d65a84b07d7d1a5018adf901dfa55'
URL = 'https://github.com/Denberg28/telerc_ardurover/releases/download/firmware-baseline-v1.1.0rc1/' + NAME


def verify(path):
    path = Path(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != SHA256:
        raise ValueError('Firmware baseline checksum mismatch')
    check_archive(path)
    with zipfile.ZipFile(path) as z:
        prefix = NAME[:-4]+'/'
        report = json.loads(z.read(prefix+'BUILD_REPORT.json'))
        if report['source_commit'] != SOURCE or len(report['builds']) != 11 or any(b['result'] != 'PASS' for b in report['builds']):
            raise ValueError('Firmware baseline build evidence mismatch')
    return path


def obtain(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder/NAME
    if not path.exists():
        temporary = path.with_suffix('.zip.partial')
        try:
            with urllib.request.urlopen(URL, timeout=60) as response:
                data = response.read(5*1024*1024+1)
            if len(data) > 5*1024*1024:
                raise ValueError('Unexpected firmware baseline download size')
            temporary.write_bytes(data)
            verify(temporary)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    return verify(path)

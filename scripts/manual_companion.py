"""Verify the unchanged manual radio set before bundling or rebuilding it."""
import hashlib
import json
from pathlib import Path
import zipfile

from release_safety import check_archive

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'release_addons/TeleRC-LoRa-v1.0.1'
NAME = 'TeleRC-LoRa-v1.0.1-node-fix-firmware.zip'
DIGEST = '729cbdb0d1d7afd53c57c67c986ec462d841175c0815ec74198b2193ad779ec6'


def verify():
    archive = FOLDER / NAME
    if hashlib.sha256(archive.read_bytes()).hexdigest() != DIGEST:
        raise ValueError('Manual firmware companion hash mismatch')
    check_archive(archive)
    with zipfile.ZipFile(archive) as reader:
        prefix = 'TeleRC-LoRa-v1.0.1/'
        entries = {}
        for line in reader.read(prefix + 'SHA256SUMS.txt').decode().splitlines():
            digest, name = line.split('  ', 1)
            if name in entries:
                raise ValueError('Duplicate manual firmware manifest entry')
            entries[name] = digest
            if hashlib.sha256(reader.read(prefix + name)).hexdigest() != digest:
                raise ValueError('Manual firmware member hash mismatch: ' + name)
        if set(reader.namelist()) != {prefix + n for n in entries} | {prefix + 'SHA256SUMS.txt'}:
            raise ValueError('Uncatalogued manual firmware member')
        evidence = json.loads(reader.read(prefix + 'VALIDATION.json'))
        if evidence != json.loads((FOLDER / 'VALIDATION.json').read_text()):
            raise ValueError('Manual firmware validation record mismatch')
        if {b['role'] for b in evidence['builds'] if b['status'] == 'PASS'} != {'BASE','ROVER','NODE1','NODE2'}:
            raise ValueError('Incomplete manual firmware role set')
    return archive


def extract(destination):
    archive = verify()
    with zipfile.ZipFile(archive) as reader:
        reader.extractall(destination)  # All names/content were checked above.
    return Path(destination) / 'TeleRC-LoRa-v1.0.1'


if __name__ == '__main__':
    print('PASS:', verify().name)

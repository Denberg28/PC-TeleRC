"""Create a reproducible source checkpoint and focused sketch package."""
from pathlib import Path
import hashlib
import zipfile

root = Path(__file__).resolve().parents[1]
output = root / 'release-dist'
output.mkdir(exist_ok=True)
excluded = {'__pycache__', '.git', '.pytest_cache', 'release-dist', 'dist', 'build',
            'installer-dist', 'firmware-build', 'windows-release', 'pc_telerc.egg-info'}
files = sorted(p for p in root.rglob('*') if p.is_file() and not excluded.intersection(p.relative_to(root).parts))
files = [p for p in files if p.suffix not in {'.pyc', '.pyo'}]


def archive(name, selected):
    path = output / name
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as writer:
        for source in selected:
            entry = zipfile.ZipInfo('PC-TeleRC-v0.1.1rc6/' + source.relative_to(root).as_posix(), (2026, 10, 14, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            writer.writestr(entry, source.read_bytes())
    return path


source = archive('PC-TeleRC-source-v0.1.1rc6.zip', files)
sketches = archive('TeleRC-LilyGO-T3S3-SX1262-v0.2.0-sketches.zip',
                  [p for p in files if 'TeleRCLoRa_' in str(p) or p.name == 'LILYGO-SX1262-ARDUROVER.md'])
lines = [f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}' for p in (source, sketches)]
(output / 'SHA256-source-sketches.txt').write_text('\n'.join(lines) + '\n')
print('\n'.join(lines))


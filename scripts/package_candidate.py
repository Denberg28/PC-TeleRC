"""Create a reproducible source checkpoint and focused sketch package."""
from pathlib import Path
import hashlib
import zipfile

root = Path(__file__).resolve().parents[1]
output = root / 'release-dist'
output.mkdir(exist_ok=True)
excluded = {'__pycache__', '.git', '.pytest_cache', 'release-dist', 'dist', 'build',
            'installer-dist', 'firmware-build', 'firmware-build-input', 'windows-release', 'pc_telerc.egg-info'}
files = sorted(p for p in root.rglob('*') if p.is_file() and not excluded.intersection(p.relative_to(root).parts))
files = [p for p in files if p.suffix not in {'.pyc', '.pyo'}]


def archive(name, selected):
    path = output / name
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as writer:
        for source in selected:
            entry = zipfile.ZipInfo('PC-TeleRC-v0.1.1/' + source.relative_to(root).as_posix(), (2026, 10, 14, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            writer.writestr(entry, source.read_bytes())
    return path


source = archive('PC-TeleRC-source-v0.1.1.zip', files)
sketches = archive('TeleRC-Firmware-v0.1.1-sketches.zip',
                  [p for p in files if (p.relative_to(root).parts[0] == 'firmware' and p.relative_to(root).parts[1].startswith('TeleRC')) or p.name in {'FIRMWARE-RECOVERY-rc7.md', 'LILYGO-SX1262-ARDUROVER.md', 'LILYGO-WIFI-LORA.md', 'STABLE-v0.1.1.md'}])
lines = [f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}' for p in (source, sketches)]
(output / 'SHA256-source-sketches.txt').write_text('\n'.join(lines) + '\n')
print('\n'.join(lines))


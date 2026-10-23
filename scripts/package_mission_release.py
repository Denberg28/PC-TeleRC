"""Build deterministic mission source/sketch bundles, excluding private profiles."""

from pathlib import Path
import hashlib
import argparse
import re
import zipfile
from mission_release_support import check_public_config, public_mission_files
from release_safety import check_file

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "release-dist"
OUT.mkdir(exist_ok=True)
APP = "1.0.1"
FW = "0.2.0rc1"
EXCLUDE = {
    "__pycache__",
    ".pytest_cache",
    ".git",
    ".venv",
    "venv",
    "release-dist",
    "build",
    "dist",
    "installer-dist",
    "stable-release",
    "incoming",
    "firmware-dist",
    "firmware-v1-evidence",
    "pc_telerc.egg-info",
    ".ruff_cache",
}


def files(root):
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file() or EXCLUDE.intersection(relative.parts):
            continue
        if path.is_symlink():
            raise ValueError("Refusing symlink in source package")
        check_file(path, relative.as_posix())
        if relative.as_posix() == 'release_addons/TeleRC-LoRa-v1.0.1/TeleRC-LoRa-v1.0.1-node-fix-firmware.zip':
            from manual_companion import verify
            verify()
            yield path
            continue
        if path.suffix.lower() in {
            ".zip",
            ".apk",
            ".pyc",
            ".pyo",
            ".bin",
            ".elf",
            ".map",
            ".log",
            ".exe",
            ".dll",
            ".pdb",
            ".so",
            ".key",
            ".pem",
            ".pfx",
            ".p12",
        }:
            continue
        if path.name in {".env", "Config.private.h"}:
            continue
        if relative.parts[:2] == ("bridge", "releases"):
            continue
        if path.name == "SOURCE_COMMIT.txt":
            continue
        if path.suffix == ".h":
            text = path.read_text(encoding="utf-8")
            if re.search(r"^\s*#\s*define\s+PROVISIONED\b", text, re.M):
                check_public_config(text)
        yield path


def archive(filename, root, prefix):
    destination = OUT / filename
    selected = list(files(root))
    temporary = destination.with_suffix(".zip.partial")
    with zipfile.ZipFile(
        temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9
    ) as writer:
        for path in selected:
            relative = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(prefix + "/" + relative, (2026, 10, 20, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            writer.writestr(info, path.read_bytes())
        info = zipfile.ZipInfo(prefix + "/SOURCE_COMMIT.txt", (2026, 10, 20, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        writer.writestr(info, (OUT / "SOURCE_COMMIT.txt").read_text())
    with zipfile.ZipFile(temporary) as reader:
        if reader.testzip() is not None:
            raise RuntimeError("Archive integrity failure")
    temporary.replace(destination)
    return destination


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source-commit", required=True)
args = parser.parse_args()
if not re.fullmatch("[0-9a-f]{40}", args.source_commit):
    parser.error("Use the exact committed source revision")
(OUT / "SOURCE_COMMIT.txt").write_text(args.source_commit + "\n")
public_mission_files(ROOT / "firmware/mission")
source = archive(f"PC-TeleRC-Mission-v{APP}-source.zip", ROOT, f"PC-TeleRC-v{APP}")
sketches = archive(
    f"TeleRC-LoRa-Mission-v{FW}-sketches.zip",
    ROOT / "firmware/mission",
    f"TeleRC-LoRa-Mission-v{FW}",
)
(OUT / "SHA256-mission.txt").write_text(
    "".join(
        hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
        for p in (source, sketches)
    )
)
print(source)
print(sketches)

"""Build deterministic mission source/sketch bundles, excluding private profiles."""

from pathlib import Path
import hashlib
import argparse
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "release-dist"
OUT.mkdir(exist_ok=True)
APP = "0.1.5rc2"
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
    "pc_telerc.egg-info",
}


def files(root):
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file() or EXCLUDE.intersection(relative.parts):
            continue
        if path.suffix in {".pyc", ".pyo", ".bin", ".elf", ".map", ".log"}:
            continue
        if path.name in {".env", "Config.private.h"}:
            continue
        if relative.parts[:2] == ("bridge", "releases"):
            continue
        yield path


def archive(filename, root, prefix):
    destination = OUT / filename
    with zipfile.ZipFile(
        destination, "w", zipfile.ZIP_DEFLATED, compresslevel=9
    ) as writer:
        for path in files(root):
            relative = path.relative_to(root).as_posix()
            if path.name == "Config.h" and "/mission/" in str(path):
                if "#define PROVISIONED 0" not in path.read_text():
                    raise RuntimeError(
                        "Refusing to package a provisioned private Config.h"
                    )
            info = zipfile.ZipInfo(prefix + "/" + relative, (2026, 10, 20, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            writer.writestr(info, path.read_bytes())
        info = zipfile.ZipInfo(prefix + "/SOURCE_COMMIT.txt", (2026, 10, 20, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        writer.writestr(info, (OUT / "SOURCE_COMMIT.txt").read_text())
    with zipfile.ZipFile(destination) as reader:
        if reader.testzip() is not None:
            raise RuntimeError("Archive integrity failure")
    return destination


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source-commit", required=True)
args = parser.parse_args()
if not re.fullmatch("[0-9a-f]{40}", args.source_commit):
    parser.error("Use the exact committed source revision")
(OUT / "SOURCE_COMMIT.txt").write_text(args.source_commit + "\n")
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

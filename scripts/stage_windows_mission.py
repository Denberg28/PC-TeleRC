"""Stage only a verified Windows application and allowlisted public mission sketches."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib
import zipfile

from mission_release_support import public_mission_files, validate_frozen_report
from manual_companion import verify as verify_manual

ROOT = Path(__file__).resolve().parents[1]


def stage(commit):
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Exact source commit required")
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    desktop = ROOT / "dist/PC-TeleRC"
    report_path = ROOT / "frozen-ui-check.json"
    validate_frozen_report(report_path, version, desktop / "PC-TeleRC.exe")
    subprocess.run(
        [sys.executable, "scripts/verify_desktop_package.py"], cwd=ROOT, check=True
    )
    firmware = ROOT / "firmware/mission"
    selected = public_mission_files(firmware)
    # Build output may contain an older staging directory. Replace it completely.
    destination = desktop / "Mission-firmware"
    if destination.exists():
        shutil.rmtree(destination)
    for source in selected:
        target = destination / source.relative_to(firmware)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    manual = desktop / 'Manual-firmware'
    manual.mkdir(exist_ok=True)
    companion = verify_manual()
    shutil.copyfile(companion, manual / companion.name)
    shutil.copyfile(ROOT / 'docs/FIRMWARE-COMPATIBILITY-v1.0.1.md', desktop / 'FIRMWARE-COMPATIBILITY.md')
    shutil.copyfile(ROOT / "START-HERE.md", desktop / "START-HERE.md")
    for name in (
        "OFFLINE-MAPS",
        "CAMERA-DESKTOP",
        "KEYBOARD",
        "LORA-USB-SETUP",
        "THIRD-PARTY",
        "MISSION-PLANNING",
    ):
        shutil.copyfile(ROOT / f"docs/{name}.md", desktop / f"{name}.md")
    shutil.copyfile(ROOT / f"docs/releases/v{version}.md", desktop / "RELEASE.md")
    shutil.copyfile(report_path, desktop / "frozen-ui-check.json")
    (desktop / "build-provenance.json").write_text(
        json.dumps(
            {
                "version": version,
                "source_commit": commit,
                "firmware": "0.2.0rc1",
                "qualification": "Windows frozen UI/media passed; physical hardware pending",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    output = ROOT / "release-dist"
    output.mkdir(exist_ok=True)
    archive = output / f"PC-TeleRC-portable-v{version}.zip"
    temporary = archive.with_suffix(".zip.partial")
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as writer:
            for source in sorted(desktop.rglob("*")):
                if source.is_symlink():
                    raise ValueError("Symlink in desktop build output")
                if source.is_file():
                    writer.write(source, source.relative_to(desktop).as_posix())
        with zipfile.ZipFile(temporary) as reader:
            if reader.testzip() is not None:
                raise ValueError("Portable archive integrity failure")
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)
    (output / "SHA256-windows-portable.txt").write_text(
        f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n",
        encoding="ascii",
    )
    print(archive)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True)
    stage(parser.parse_args().source_commit)

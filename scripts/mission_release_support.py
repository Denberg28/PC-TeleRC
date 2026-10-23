"""Shared fail-closed checks for public mission release packages."""

import hashlib
import json
from pathlib import Path, PurePosixPath
import re


REQUIRED_CHECKS = frozenset(
    """
camera_layout lower_left_map logo control_disabled sliders map_minimize
fpv_overlay connection_control_labels balanced_selectors
map_restore_anchor map_restore map_swap swap_no_media_restart
backpack_commands_locked offline_map_load offline_tile_decode offline_no_network
offline_no_fake_gps mission_plan_codec mission_planning_no_authority
mission_close_cleans_session video_fixture camera_start actual_video_decode
media_no_control_side_effect camera_stop
""".split()
)
CACHE_PARTS = {"__pycache__", ".pytest_cache", ".ruff_cache"}


def public_mission_files(root):
    """Use the shipped hash allowlist; never recursively copy private profiles."""
    root = Path(root)
    manifest = root / "SHA256SUMS.txt"
    entries = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        relative = PurePosixPath(name)
        if (
            not re.fullmatch(r"[0-9a-f]{64}", digest)
            or relative.is_absolute()
            or ".." in relative.parts
            or "\\" in name
            or ":" in name
            or name in entries
            or name == "SHA256SUMS.txt"
        ):
            raise ValueError("Invalid mission firmware manifest entry")
        entries[name] = digest
    if not entries:
        raise ValueError("Empty mission firmware manifest")
    selected = []
    for name, digest in entries.items():
        path = root / name
        if any(part.is_symlink() for part in [path, *path.parents]):
            raise ValueError("Symlinks are not permitted in mission firmware")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f"Mission firmware differs from public manifest: {name}")
        if path.name in ("Config.h", "Config.example.h"):
            check_public_config(data.decode("utf-8"))
        selected.append(path)
    actual = {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if (p.is_file() or p.is_symlink())
        and not CACHE_PARTS.intersection(p.relative_to(root).parts)
    }
    if actual != set(entries) | {"SHA256SUMS.txt"}:
        raise ValueError(
            "Unexpected or missing firmware files; keep private fleet output outside the source tree"
        )
    return sorted([manifest, *selected])


def check_public_config(text):
    # Strip comments before interpreting the define; a comment cannot authorize RF.
    text = re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)
    values = re.findall(r"^\s*#\s*define\s+PROVISIONED\s+(.*?)\s*$", text, re.M)
    if values != ["0"]:
        raise ValueError(
            "Refusing to distribute a private or ambiguous mission Config.h"
        )


def validate_frozen_report(path, version, executable):
    path, executable = Path(path), Path(executable)
    report = json.loads(path.read_text(encoding="utf-8"))
    checks = report.get("checks", {})
    if (
        report.get("version") != version
        or report.get("passed") is not True
        or not isinstance(checks, dict)
        or not REQUIRED_CHECKS.issubset(checks)
        or any(value is not True for value in checks.values())
        or path.stat().st_mtime_ns < executable.stat().st_mtime_ns
    ):
        raise ValueError(
            "Frozen UI/media report is missing, stale, incomplete or failed"
        )
    return report

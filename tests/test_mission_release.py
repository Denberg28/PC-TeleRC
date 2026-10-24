"""Release gates must reject private firmware and misleading frozen reports."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

spec = importlib.util.spec_from_file_location(
    "mission_release_support", Path("scripts/mission_release_support.py")
)
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)


def public_tree(tmp_path):
    config = tmp_path / "Config.h"
    config.write_text("#define PROVISIONED 0\n")
    (tmp_path / "SHA256SUMS.txt").write_text(
        hashlib.sha256(config.read_bytes()).hexdigest() + "  Config.h\n"
    )
    return tmp_path


def test_shipped_firmware_passes_allowlist():
    files = support.public_mission_files(Path("firmware/mission"))
    assert len([p for p in files if p.name == "Config.h"]) == 4


def test_private_added_profile_is_rejected(tmp_path):
    root = public_tree(tmp_path)
    (root / "private-key.txt").write_text("private test data")
    with pytest.raises(ValueError, match="Unexpected"):
        support.public_mission_files(root)


def test_modified_public_sketch_is_rejected(tmp_path):
    root = public_tree(tmp_path)
    (root / "Config.h").write_text("#define PROVISIONED 1\n")
    with pytest.raises(ValueError, match="differs"):
        support.public_mission_files(root)


@pytest.mark.parametrize(
    "text",
    [
        "// #define PROVISIONED 0\n#define PROVISIONED 1\n",
        "#define PROVISIONED 0\n#define PROVISIONED 1\n",
        "#define PROVISIONED 1\n",
        "#define PROVISIONED (0)\n",
    ],
)
def test_comment_or_ambiguous_define_cannot_authorize_distribution(text):
    with pytest.raises(ValueError, match="private or ambiguous"):
        support.check_public_config(text)


def test_cached_python_files_are_omitted(tmp_path):
    root = public_tree(tmp_path)
    (root / "__pycache__").mkdir()
    (root / "__pycache__/generated.pyc").write_bytes(b"test")
    assert len(support.public_mission_files(root)) == 2


def test_manifest_cannot_escape_firmware_root(tmp_path):
    (tmp_path / "SHA256SUMS.txt").write_text("0" * 64 + "  ../private.key\n")
    with pytest.raises(ValueError, match="Invalid"):
        support.public_mission_files(tmp_path)


def test_source_package_rejects_private_fleet_outside_firmware(tmp_path):
    # A generated fleet may accidentally be placed anywhere inside the source tree.
    root = tmp_path / "source"
    root.mkdir()
    shutil.copyfile("pyproject.toml", root / "pyproject.toml")
    shutil.copytree(
        "scripts", root / "scripts", ignore=shutil.ignore_patterns("__pycache__")
    )
    shutil.copytree(
        "firmware/mission",
        root / "firmware/mission",
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"),
    )
    private = root / "my-fleet/TeleRCMission_BASE"
    private.mkdir(parents=True)
    (private / "Config.h").write_text(
        "// #define PROVISIONED 0\n#define PROVISIONED 1\n"
    )
    result = subprocess.run(
        [
            sys.executable,
            "scripts/package_mission_release.py",
            "--source-commit",
            "0" * 40,
        ],
        cwd=root,
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0 and "private or ambiguous" in result.stderr
    assert not list((root / "release-dist").glob("*.zip"))


@pytest.mark.parametrize(
    "variant", ["pass", "missing", "false", "truthy", "wrong_version", "stale"]
)
def test_report_gate_requires_every_current_check(tmp_path, variant):
    exe, report = tmp_path / "app.exe", tmp_path / "report.json"
    exe.write_bytes(b"test executable placeholder")
    data = {
        "version": "test",
        "passed": True,
        "checks": dict.fromkeys(support.REQUIRED_CHECKS, True),
    }
    if variant == "missing":
        data["checks"].pop("mission_planning_no_authority")
    elif variant == "false":
        data["checks"]["control_disabled"] = False
    elif variant == "truthy":
        data["checks"]["control_disabled"] = "true"
    elif variant == "wrong_version":
        data["version"] = "old"
    report.write_text(json.dumps(data))
    if variant == "stale":
        os.utime(report, ns=(1, 1))
    if variant == "pass":
        support.validate_frozen_report(report, "test", exe)
    else:
        with pytest.raises(ValueError, match="Frozen"):
            support.validate_frozen_report(report, "test", exe)

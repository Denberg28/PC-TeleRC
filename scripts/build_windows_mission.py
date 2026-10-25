"""Build the Windows candidate with checked subprocesses and a fresh frozen report."""

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def build(commit=None):
    if sys.platform != "win32":
        raise RuntimeError("Run this build on Windows with Python 3.12")
    if commit is None:
        source_commit = ROOT / "SOURCE_COMMIT.txt"
        commit = (
            source_commit.read_text().strip()
            if source_commit.exists()
            else subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip()
        )
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Exact source commit required")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")

    def run(*args, **kwargs):
        return subprocess.run(args, cwd=ROOT, env=env, check=True, **kwargs)

    run(sys.executable, "-m", "venv", ".venv")
    python = str(ROOT / ".venv/Scripts/python.exe")
    run(python, "-m", "pip", "install", "-e", ".[dev]")
    run(python, "-m", "pip", "check")
    run(python, "-m", "compileall", "-q", "src", "tests", "main.py")
    # Qt/QtMultimedia retain process-wide native resources. A fresh process
    # per module prevents cross-module teardown from corrupting later windows.
    # Every module still runs; any subprocess/evidence failure stops packaging.
    run(python, "scripts/run_regressions.py")
    # The immutable firmware CLI uses upstream pymavlink's Windows udpout bind.
    # Its real UDP simulations run in the required Linux firmware job, together
    # with native runtime/sanitizer and actual-board builds. The Windows app's
    # own real UDP peer regressions above exercise its corrected endpoint path.
    # Both jobs remain mandatory dependencies of release publication.
    run(python, "-m", "PyInstaller", "--noconfirm", "--clean", "PC-TeleRC.spec")
    report = ROOT / "frozen-ui-check.json"
    report.unlink(missing_ok=True)
    with (
        (ROOT / "frozen-stdout.txt").open("w") as out,
        (ROOT / "frozen-stderr.txt").open("w") as err,
    ):
        # subprocess.run waits even for a GUI-subsystem executable on Windows.
        run(
            str(ROOT / "dist/PC-TeleRC/PC-TeleRC.exe"),
            "--self-test-ui",
            str(report),
            stdout=out,
            stderr=err,
            timeout=90,
        )
    run(python, "scripts/stage_windows_mission.py", "--source-commit", commit)
    run(python, "scripts/package_mission_release.py", "--source-commit", commit)
    print(
        "Verified Windows portable candidate built. Physical qualification remains pending."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit")
    build(parser.parse_args().source_commit)

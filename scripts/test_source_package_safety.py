"""Exercise the actual source packager with accidental private build inputs."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile


SCRIPTS = Path(__file__).resolve().parent
PC = (SCRIPTS / "package_mission_release.py").exists()


class SourcePackageSafetyTests(unittest.TestCase):
    def fixture(self, root):
        (root / "scripts").mkdir()
        names = ["release_safety.py"]
        names += (["package_mission_release.py", "mission_release_support.py"]
                  if PC else ["package_v1_source.py"])
        for name in names:
            shutil.copyfile(SCRIPTS / name, root / "scripts" / name)
        (root / "docs").mkdir()
        (root / "docs/REALIGNMENT_V1.md").write_text("Public release notes")
        (root / "ecosystem-release.json").write_text(json.dumps(
            dict(product="test", application_version="1.0.4")))
        (root / ".env.example").write_text("EXAMPLE=replace-me\n")
        (root / "old.zip").write_bytes(b"legacy output must not enter source")
        (root / "old.apk").write_bytes(b"legacy output must not enter source")
        if PC:
            import hashlib
            mission = root / "firmware/mission"
            mission.mkdir(parents=True)
            config = b"#define PROVISIONED 0\n"
            (mission / "Config.h").write_bytes(config)
            (mission / "SHA256SUMS.txt").write_text(
                hashlib.sha256(config).hexdigest() + "  Config.h\n")
        else:
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)

    def package(self, root):
        if not PC:
            subprocess.run(["git", "add", "."], cwd=root, check=True)
        command = [sys.executable, "scripts/" +
                   ("package_mission_release.py" if PC else "package_v1_source.py")]
        if PC:
            command += ["--source-commit", "a" * 40]
        return subprocess.run(command, cwd=root,
                              env=dict(os.environ, GITHUB_SHA="a" * 40),
                              capture_output=True, text=True)

    def test_public_snapshot_omits_legacy_binary_archives(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            result = self.package(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            source = next((root / "release-dist").glob("*-source.zip"))
            with zipfile.ZipFile(source) as reader:
                self.assertFalse(any(Path(n).name in {"old.zip", "old.apk"}
                                     for n in reader.namelist()))
                self.assertTrue(any(n.endswith("SOURCE_COMMIT.txt") for n in reader.namelist()))

    def test_private_environment_blocks_package(self):
        self.reject(".env.production", "TEST_ONLY=not-a-real-secret")

    def test_private_signing_file_blocks_package(self):
        self.reject("signing.jks", "not-a-real-keystore")

    def test_private_fleet_outside_firmware_blocks_package(self):
        self.reject("private-fleet/Config.h", "#define PROVISIONED 1\n")

    def reject(self, name, content):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            result = self.package(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("private", result.stderr.lower())
            self.assertFalse(list((root / "release-dist").glob("*.zip")))


if __name__ == "__main__":
    unittest.main()

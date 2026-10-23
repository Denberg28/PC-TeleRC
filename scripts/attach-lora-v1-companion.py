"""Validate and attach the exact manual-control companion to PC TeleRC v1.0.0."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "release_addons/TeleRC-LoRa-v1.0.0"
REPO = "Denberg28/PC-TeleRC"
RELEASE_ID = 421523284
TAG = "v1.0.0"
PACKAGE = "TeleRC-LoRa-v1.0.0-firmware.zip"
CHECKSUM = "SHA256-TeleRC-LoRa-v1.0.0.txt"
GUIDE = "TeleRC-LoRa-v1.0.0-COMPATIBILITY.md"
EXPECTED_HASH = "f6e43280ce6374a2ca216ad70cee77aff66e359c6ba02cc51597d7061d9ad880"
API = "https://api.github.com/repos/" + REPO
MARKER = "<!-- TELERC_MANUAL_LORA_V1_COMPANION -->"
NOTE = """
<!-- TELERC_MANUAL_LORA_V1_COMPANION -->
## Optional manual-control firmware — TeleRC LoRa v1.0.0

[Download TeleRC-LoRa-v1.0.0-firmware.zip](https://github.com/Denberg28/PC-TeleRC/releases/download/v1.0.0/TeleRC-LoRa-v1.0.0-firmware.zip). Includes source and compiled images for a selectable Wi-Fi/LoRa ROVER, LoRa-only BASE, NODE1 and NODE2. Automatic routing supports direct, either node, or the ordered two-node chain. Defaults: 915 MHz, public test password `telerc123`, 2 dBm.

**Manual single-rover control only: no mission upload/start, waypoint/servo commands or fleet support.** This companion is a separate protocol family from the mission firmware above. Use one matching set of BASE/ROVER/NODE images. Flash all participating manual-link boards together: radio protocol v3 is incompatible with the earlier v0.1.3 manual-link v2 boards. The app must still open its COM/UDP connection; auto connection never arms the rover.

Four real LilyGO T3-S3 SX1262 target builds and 318 host checks passed. Physical RF, app interoperability and motor-failsafe qualification remain pending. Read the included READ-ME-FIRST.md and binaries/FLASHING.md: factory images overwrite the full 4 MB flash including NVS. A separate SHA256-TeleRC-LoRa-v1.0.0.txt and TeleRC-LoRa-v1.0.0-COMPATIBILITY.md accompany this add-on. The published Windows and mission assets, tag and prerelease status are retained.
"""

def validate_package():
    data = (FOLDER / PACKAGE).read_bytes()
    if hashlib.sha256(data).hexdigest() != EXPECTED_HASH:
        raise ValueError("Companion ZIP hash differs from reviewed package")
    with zipfile.ZipFile(FOLDER / PACKAGE) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP paths")
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or not name.startswith("TeleRC-LoRa-v1.0.0/"):
                raise ValueError("Unexpected ZIP path: " + name)
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC failure")
        prefix = "TeleRC-LoRa-v1.0.0/"
        manifest = archive.read(prefix + "SHA256SUMS.txt").decode()
        expected_files = set()
        for line in manifest.splitlines():
            expected, name = line.split("  ", 1)
            if hashlib.sha256(archive.read(prefix + name)).hexdigest() != expected:
                raise ValueError("Manifest hash mismatch: " + name)
            expected_files.add(prefix + name)
        if set(names) != expected_files | {prefix + "SHA256SUMS.txt"}:
            raise ValueError("ZIP has uncatalogued files")
        validation = json.loads(archive.read(prefix + "VALIDATION.json"))
        if validation["version"] != "1.0.0" or validation["radio_protocol"] != 3:
            raise ValueError("Unexpected firmware version/protocol")
        if {item["role"] for item in validation["builds"] if item["status"] == "PASS"} != {"BASE", "ROVER", "NODE1", "NODE2"}:
            raise ValueError("Missing real-target build evidence")
        if validation["host_checks"]["total"] != 318 or validation["host_checks"]["status"] != "PASS":
            raise ValueError("Missing host-test evidence")
        if json.loads((FOLDER / "VALIDATION.json").read_text()) != validation:
            raise ValueError("External validation differs from reviewed ZIP")
    print("Reviewed ZIP, every member, all four target records and 318 host checks verified")
    return data

def request(url, method="GET", data=None, content_type="application/json"):
    headers = {"Authorization": "Bearer " + os.environ["GH_TOKEN"],
               "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28",
               "Content-Type": content_type}
    if isinstance(data, dict):
        data = json.dumps(data).encode()
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.load(response)

def verify_original(release):
    original = json.loads((FOLDER / "release-snapshot.json").read_text())
    if release["id"] != RELEASE_ID or release["tag_name"] != TAG or release["draft"] or release["prerelease"] != original["prerelease"]:
        raise ValueError("Target release identity/state changed")
    actual = {asset["id"]: asset for asset in release["assets"]}
    for expected in original["assets"]:
        item = actual.get(expected["id"], {})
        if any(item.get(key) != expected[key] for key in ("name", "digest", "size")):
            raise ValueError("Original release asset changed: " + expected["name"])

def upload(release, name, data, mime):
    digest = "sha256:" + hashlib.sha256(data).hexdigest()
    existing = next((a for a in release["assets"] if a["name"] == name), None)
    if existing:
        if existing["digest"] != digest or existing["size"] != len(data):
            raise ValueError("Refusing to replace existing asset: " + name)
        print("Verified existing companion: " + name)
        return
    url = release["upload_url"].split("{")[0] + "?" + urllib.parse.urlencode({"name": name})
    result = request(url, "POST", data, mime)
    if result["state"] != "uploaded" or result["digest"] != digest or result["size"] != len(data):
        raise ValueError("Upload validation failed: " + name)
    print("Attached " + name)

def publish(data):
    release = request(API + "/releases/" + str(RELEASE_ID))
    verify_original(release)
    upload(release, PACKAGE, data, "application/zip")
    upload(release, CHECKSUM, (EXPECTED_HASH + "  " + PACKAGE + "\n").encode(), "text/plain")
    upload(release, GUIDE, (FOLDER / "README.md").read_bytes(), "text/markdown")
    release = request(API + "/releases/" + str(RELEASE_ID))
    verify_original(release)
    if MARKER not in (release.get("body") or ""):
        request(API + "/releases/" + str(RELEASE_ID), "PATCH",
                {"body": (release.get("body") or "").rstrip() + "\n\n" + NOTE.strip() + "\n"})
    final = request(API + "/releases/" + str(RELEASE_ID))
    verify_original(final)
    if not {PACKAGE, CHECKSUM, GUIDE}.issubset({a["name"] for a in final["assets"]}) or MARKER not in final["body"]:
        raise ValueError("Final companion release verification failed")
    print("Published manual-control companion to " + final["html_url"])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    data = validate_package()
    if not args.validate_only:
        publish(data)

if __name__ == "__main__":
    main()

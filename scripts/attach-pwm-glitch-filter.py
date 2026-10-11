"""Attach only the authorized PWM companion to existing stable release a10."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import urllib.request

REPO = "Denberg28/PC-TeleRC"
RELEASE_ID = 401732682
TAG = "v0.1.0a10"
PACKAGE = "TeleRC-PWM-GlitchFilter-v1.0.1-test-candidate.zip"
CHECKSUM = "SHA256-PWM-GlitchFilter-v1.0.1.txt"
EXPECTED_HASH = "58ad0ca359d10c3203022d358535bb74c79c5c6286af241771c3bd1334a6b96a"
ORIGINAL_ASSETS = json.loads("[{\"id\":605386879,\"name\":\"PC-TeleRC-portable-v0.1.0a10.zip\",\"digest\":\"sha256:c76471bbbcdc8584d3b8945331e1d136ec7ce8f383ce6838552cb2df361d40c2\",\"size\":95776592},{\"id\":605386880,\"name\":\"PC-TeleRC-Setup-v0.1.0a10.exe\",\"digest\":\"sha256:c393fc07c27f839d362fae33dac596b1af4e0b82e97123a344d2261d56de34e8\",\"size\":64778530},{\"id\":605386876,\"name\":\"SHA256-installer.txt\",\"digest\":\"sha256:9e41ed67f566989284569937836819afc6093fefe75ee683100f85e5dbbc8196\",\"size\":97},{\"id\":605386875,\"name\":\"SHA256.txt\",\"digest\":\"sha256:689407aec0b1ac51f7c8add1dd577e4009f38be4cafa50e3d0c31e2826f433a8\",\"size\":100}]")
ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PATH = ROOT / "stable_config/PWM_GlitchFilter_v1.0.1" / PACKAGE
API = "https://api.github.com/repos/" + REPO
MARKER = "<!-- PWM_GLITCH_FILTER_1_0_1 -->"
NOTE = """
<!-- PWM_GLITCH_FILTER_1_0_1 -->
## Optional PWM-converter companion — glitch-filter test candidate 1.0.1
Added at the maintainer's request on 2026-10-11 (Asia/Manila).
[Download the source package](https://github.com/Denberg28/PC-TeleRC/releases/download/v0.1.0a10/TeleRC-PWM-GlitchFilter-v1.0.1-test-candidate.zip) and its separate SHA256-PWM-GlitchFilter-v1.0.1.txt checksum.

For the separate ESP32-S3 PWM converter between FC M5-M8 and four BTS7960 drivers. Do not flash this onto the Wi-Fi/MAVLink bridge.
- Isolated out-of-range PWM samples are rejected without clearing the last valid input.
- Any channel without valid PWM for 150 ms still stops all motors at the next control update; invalid samples cannot refresh that timeout.
- The 300 ms neutral recovery requirement remains.
- Diagnostics include rejected-pulse counters, stop count, uptime and boot reset reason.
- 20 host checks passed across Arduino API branches 2 and 3; ESP32 target compilation and hardware validation remain pending.
- Read the included motor-mapping warning and raised-wheel bench instructions before flashing.

This is an optional firmware test candidate accompanying the stable Windows app, not a hardware-validated stable firmware claim. The original a10 tag, installer, portable ZIP and app checksums are preserved.
"""

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
    assert release["id"] == RELEASE_ID and release["tag_name"] == TAG
    assert not release["draft"] and not release["prerelease"]
    actual = {a["id"]: a for a in release["assets"]}
    for expected in ORIGINAL_ASSETS:
        current = actual[expected["id"]]
        for key in ("name", "digest", "size"):
            assert current[key] == expected[key], "Original asset changed: " + expected["name"]

def upload(release, name, data, mime):
    digest = "sha256:" + hashlib.sha256(data).hexdigest()
    existing = next((a for a in release["assets"] if a["name"] == name), None)
    if existing:
        assert existing["digest"] == digest, "Refusing to overwrite existing asset " + name
        print("Verified existing companion: " + name)
        return
    url = release["upload_url"].split("{")[0] + "?name=" + name
    result = request(url, "POST", data, mime)
    assert result["state"] == "uploaded" and result["digest"] == digest
    print("Attached " + name)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    data = PACKAGE_PATH.read_bytes()
    assert hashlib.sha256(data).hexdigest() == EXPECTED_HASH
    checksum = (EXPECTED_HASH + "  " + PACKAGE + "\n").encode()
    if args.validate_only:
        print("Package SHA-256 verified; host checks run in the next workflow step.")
        return
    release = request(API + "/releases/" + str(RELEASE_ID))
    verify_original(release)
    upload(release, PACKAGE, data, "application/zip")
    upload(release, CHECKSUM, checksum, "text/plain")
    # Re-read before appending to preserve intervening release-note edits.
    release = request(API + "/releases/" + str(RELEASE_ID))
    verify_original(release)
    if MARKER not in (release.get("body") or ""):
        request(API + "/releases/" + str(RELEASE_ID), "PATCH",
                {"body": (release.get("body") or "").rstrip() + "\n\n" + NOTE.strip() + "\n"})
    final = request(API + "/releases/" + str(RELEASE_ID))
    verify_original(final)
    names = {a["name"] for a in final["assets"]}
    assert PACKAGE in names and CHECKSUM in names and MARKER in final["body"]
    print("Stable a10 companion published; original Windows assets preserved.")

if __name__ == "__main__":
    main()


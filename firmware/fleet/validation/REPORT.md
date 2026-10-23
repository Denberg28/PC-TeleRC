# Validation — 1.1.0-dev1

Validated 23 October 2026. Development candidate; no radio/vehicle qualification.
Linux, Python 3.12.14, GCC 13.3.0, OpenSSL test adapter, Arduino CLI 1.5.2-rc.1.
Exact ESP32 Arduino 3.3.2 and RadioLib 7.2.1.

## Results

| Check | Result |
|---|---|
| Python host/tool/protocol tests | 19 passed (8.85 s) |
| Provisioned C++ role builds/execution with ASan + UBSan | BASE, ROVER1, ROVER20, NODE1, NODE200 passed |
| Public keyless examples | BASE, ROVER1, NODE1, NODE2 keep RF OFF and send no FC command |
| TF2 addressing/routing | IDs 1..20 × routes 0..4 = 100 combinations per runtime binary |
| Tamper/security checks | Every packet byte altered, truncated frames, wrong keys, forged ciphertext/route, one-use/expired challenges rejected |
| Runtime behavior | Idle node HELLO/ACK, replay suppression, new ID20 without base rebuild, WATCH without command authority, duplicate-ID quarantine, writer exclusivity, HOLD queue priority |
| Radio failure paths (host adapter) | CAD busy backoff, queue expiry, real TX_DONE polling, timeout recovery without command replay |
| Mission behavior | Disarmed complete upload, full readback, exact ID/digest start, one-shot START, ACK/NACK, host/FC stale/reboot, no RC/arm/parameter-write, deliberate verified detach, fresh read-only auxiliary FC function/PWM-limit checks |
| New-board provisioning | Exact same base/rover network config reused for ID1/20; node profile contains no ENDPOINT_ROOT; existing files unchanged |
| Public archive | Reproducible ZIP, exact example header copies, per-file SHA256 manifest; no credentials or provisioned binaries |

The original Mission Gate/parser code is byte-for-byte preserved in the new
Protocol.h except MAX_PLAIN increases by 8 bytes for the hardware fingerprint.
Existing firmware/mission and manual sources are not edited.

## Actual target compilation of final firmware

FQBN:
`esp32:esp32:lilygo_t3s3:Revision=Radio_SX1262,PSRAM=disabled,USBMode=hwcdc,CDCOnBoot=cdc`

| Final source profile | Flash bytes / 1,310,720 | RAM bytes / 327,680 | Result |
|---|---:|---:|---|
| BASE | 408,987 | 30,088 | PASS |
| NODE200 | 406,063 | 26,464 | PASS |
| ROVER20 | 418,827 | 27,560 | PASS |

These builds used generated throwaway private credentials. No compiled binaries
or private configurations are shipped. The generic ROVER1/NODE1/NODE2 profiles
also compiled in the preliminary six-profile target pass; boundary profiles above
were rebuilt after the final TX_DONE recovery change. Host runtime tests cover
the final source at both ID boundaries.

Final Runtime.h SHA256:
`8a438881c97d8ca36b60e6addd3f971f18199a6008050fcd9e781b561833fb4d`

Final Crypto.h SHA256:
`cc0751428a686a94060b6d03c07b2560393124ac689c4f6fa4141eea153ec8da`

The archive's MANIFEST.sha256.json records every shipped source file.

## Reproduce

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q tests
python tests/run_native.py --sanitize
python tools/network.py init --out ../TeleRC-test-private
python tools/network.py add --network ../TeleRC-test-private/FleetCredentials.json --role rover --id 20 --out ../TeleRC-test-private/TeleRCFleet_ROVER_020
python tools/network.py add --network ../TeleRC-test-private/FleetCredentials.json --role node --id 200 --out ../TeleRC-test-private/TeleRCFleet_NODE_200
python tools/compile_profiles.py ../TeleRC-test-private
python tools/package.py --out ../fleet-dist
```

Native sanitizer tests require g++/OpenSSL development headers on Linux. Target
compilation requires the pinned board core and RadioLib. None of these commands
flashes hardware. Never commit/distribute TeleRC-test-private or its binaries.
The repository's separate fleet development workflow repeats host checks and all
six target profiles before staging a separate DRAFT release.

## Outstanding qualification

No real radios, UART/FC hardware, ArduRover SITL/HIL, Windows/frozen application,
real RF interference/airtime/regulatory profile, measured failover/failsafe timing,
auxiliary physical OFF, or concurrent fleet capacity were tested. Python UDP
simulation is a protocol peer, not an ArduRover simulator. The released Windows
Mission panel remains incompatible with TFM1. Address/path bounds do not imply
20 simultaneously controlled vehicles or 200 simultaneous relays.

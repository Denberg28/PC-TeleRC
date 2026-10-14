# Mini sub-release v0.1.0-test-candidate

Recorded 2026-10-15, Asia/Manila. Documentation/package registration of the
previously created mini rover candidate; no new firmware or Windows EXE build.

| Item | Value |
|---|---|
| Release ID | `rover-mini-v0.1.0-test-candidate` |
| Controller | ESP32-S3 DevKitC-1 |
| Actuators | 4 TT geared motors, 2 MX1508 dual modules |
| Architecture | Four-wheel drive, differential/skid steering |
| Link | ESP32 Wi-Fi AP, MAVLink UDP 14550, direct PC connection |
| Runtime version string | `0.1.0-test-candidate` |
| Maturity | Host-tested candidate; target compile and hardware validation pending |
| PC application version | Unchanged by this documentation commit |

## Package

[Original ZIP](archives/TeleRC-MiniRover-v0.1.0-sketch-and-wiring.zip) and its
matching [extracted contents](package/README.md) are preserved byte-for-byte.

ZIP SHA-256:
`2847eded8ff1ed0142cefeed0f530e4d0409e0d3390f446abac4cd98074bd25f`

The extracted package's `SHA256.txt` covers its original members. `release.json`
records package identity separately from this documentation wrapper.

## Included behavior

CH1 steering / CH2 drive; explicit ARM/DISARM; neutral-first enable; 500 ms RC
watchdog; single endpoint lease; disconnect and BOOT stop; 30 ms reversal coast.
No SpeedyBee flight controller is used by this mini architecture.

## Compatibility and limits

The PC wire contract was inspected from repository main at commit
`dff03ccc989c9a0d2826e6a48ee02f762b83fdcc`: MAVLink source 255/190,
discovery/disconnect strings, RC override and ARM commands. This is source
inspection, not a verified matrix of portable EXE versions.

| Input / feature | Evidence |
|---|---|
| Wheel/pedals | Matching PC wire format inspected; physical PC-to-rover test pending |
| Keyboard | Requires PC implementation; not added or verified here |
| Steering/drive safety | Host simulations pass with both Arduino-ESP32 API branches |
| Actual ESP32 build/upload | Pending; no compiled `.bin` included |
| Wi-Fi range / stopping distance / driver thermals | Pending hardware measurement |
| Navigation, camera, balancing, four-wheel steering | Not provided by this mini candidate |

The source uses a 250 ms centered-control interlock before ARM. Enable PC
Control while centered first, wait at least 0.3 s, then ARM. The stop policy
removes drive torque and coasts; it does not hold the rover on a slope.

Read the [bench checklist](package/BENCH_TEST.md) before powered ground tests.
Future fixes get a new mini candidate version; they do not silently replace
the source represented by this record.

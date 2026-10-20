# TeleRC LoRa Mission 0.2.0rc1

Matching LilyGO T3-S3 SX1262 firmware for PC TeleRC 0.1.5rc2.
BASE USB → fixed NODE route (0, 1 or 2 nodes) → addressed ROVER UART → ArduRover.
One active rover session; IDs 1–20. Not Meshtastic or the manual LoRa protocol.

## Make the matching sketches

Run **MAKE-MATCHING-SKETCHES.cmd** with Python 3.12, or:

```powershell
python tools/provision.py --out ../TeleRC-private --rovers 1 --relays 0
```

For twenty rovers with two fixed nodes, use `--rovers 20 --relays 2`.
Generate once and flash every participating board from that same folder. Each
contains its .ino and headers. Public examples are keyless and keep RF OFF.
Random per-rover keys are preferred. Optional `--password` prompts for a 16+
character passphrase; there is no shared default. Never publish generated Config.h.
Default: 915 MHz, 2 dBm, SF7, BW250, CR4:5. Keep permitted local RF settings and
matching antennas. `--frequency` / `--power` apply to the whole generated set.

Use ESP32 Arduino 3.3.2 and RadioLib 7.2.1. Board: LilyGO T3-S3, SX1262 revision,
4 MB flash, PSRAM disabled, USB hardware CDC/JTAG and CDC on boot enabled.
Compile with Arduino IDE or `python tools/compile_profiles.py <private-folder>`.
Compilation does not flash hardware. Do not distribute test binaries containing keys.

## Wiring

| Role | Connection |
|---|---|
| BASE | USB data cable to PC; select its COM port in Mission |
| ROVER GPIO43 TX | FC R3 / RX |
| ROVER GPIO44 RX | FC T3 / TX |
| ROVER GND | FC GND |
| NODE_1, NODE_2 | Stable regulated board power and antenna; no FC UART |

UART is 115200, 8N1, 3.3 V. On the FC, SERIAL3_PROTOCOL=2, SERIAL3_BAUD=115,
SYSID_THISMAV=rover ID and autopilot component 1. GCS ID is 255, component 190.
Do not use the bare ESP32-S3 GPIO17/18 mapping for this LilyGO connection.

## Mission safety

The default client policy requires FS_GCS_ENABLE=1, FS_ACTION=2 and a verified
GCS timeout of at least 3/5/7 seconds for direct/one/two-node routes, at most 10 s.
Use an appropriate deliberately configured FC value and measure real stopping
behavior. The firmware does not change FC parameters. Explicit AUTO continuation
requires FS_GCS_ENABLE=2 and FS_ACTION=2; the PC option must match.

Upload disarmed in MANUAL/HOLD. Require accepted upload plus full readback, then
arm through RC and separately confirm START. START is sent once, never retried.
An unknown START/HOLD outcome is not a stopped vehicle. Retain independent RC.

F outputs are disabled by default. Only opt in to dedicated safe outputs after
wiring/FC-function/limits/cutoff review. Example permission for outputs 9/10/11 is
`--servo-mask 0x0700`; M5–M8 are always denied. Initial/final OFF rows do not
ensure OFF after HOLD, loss, reset or skipped items. Independent cutoff is required.

BOOT wakes the display; it sleeps after 30 seconds without changing communications.
No radio ARM, RC override, parameter write or immediate accessory command is enabled.

## Changes from 0.1.0-dev

TM2 local capability handshake; safe relative delay/condition mission commands;
actual host heartbeat fairness; bounded four-frame telemetry responses; rotating
navigation slots; motor-output mask denial; updated PC/CLI validators. Flash the
complete new set together. No older BASE/ROVER mixing is supported.

The standalone gateway/client are commissioning tools. The client requires
`--relays` matching the generated route. Prefer the integrated PC Mission workflow.
See ../../docs/MISSION-PLANNING.md, VALIDATION.md and HARDWARE_TEST.md.

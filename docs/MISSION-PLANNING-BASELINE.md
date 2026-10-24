# Mission-planning base build — PC TeleRC v1.2.0rc1

Designated on 24 October 2026 as the starting baseline for future PC TeleRC mission-planning development.

| Component | Locked baseline |
| --- | --- |
| Windows application | 1.2.0rc1 |
| Application source | `9f113241a7bad88f89b9da96e448489e85cda3d7` |
| Fleet BASE / ROVER / NODE | 0.5.0rc1 |
| Firmware source | `6ba272867165eee31e21792ea259fce7225579f7` |
| ESP32-S3 four-BTS7960 converter | 1.0.5, unchanged |
| Board toolchain | Arduino CLI 1.3.1; ESP32 core 3.3.2; RadioLib 7.2.1 |
| Release channel | Candidate; physical qualification pending |

[Download the baseline release](https://github.com/Denberg28/PC-TeleRC/releases/tag/v1.2.0rc1).
[Read the fleet setup guide](FLEET-STATION.md).
The root `mission-planning-baseline.json` pins all nine published assets by size and SHA-256.

## Starting point for development

Create future feature or fix branches from `baseline/mission-planning-v1.2.0rc1`.
The baseline branch adds designation documentation and the lock manifest to the exact tested release source; application and firmware bytes remain unchanged.

Use a new version for changed application or firmware behavior. Keep this baseline and its published assets available for rollback. Update matching compatibility notes, manifests and affected checks with each subsequent release. Do not replace the baseline assets or treat documentation-only baseline designation as new binary-build evidence.

## Baseline behavior

The central map monitors independently identified rovers and shows fresh/stale Rover N labels. Each rover has Connect, Arm, Mission start, Disarm and HOLD controls, plus its own mission draft. Upload/control transactions run one at a time while other admitted sessions remain monitored. FPV uses external monitors.

Preserve deliberate normal FC arming in stationary HOLD, FC arming checks, verified mission readback, isolated rover identities, real host heartbeats, stale telemetry handling, unknown/no-retry ARM/START/DISARM behavior, RC takeover and the independent cutoff. Reconnection must not arm or replay a mission.

Rover IDs 1–20 are addresses, not an assurance of 20 simultaneous links. Measured radio admission and the maximum-two-relay-hop profile continue to apply.

## Installation

1. Install `PC-TeleRC-Setup-v1.2.0rc1.exe`, or extract the portable archive and launch its executable.
2. Use matching fleet BASE/ROVER 0.5.0rc1. Existing TU2 0.4.0 nodes and PWM converter 1.0.5 need no re-upload for this update.
3. For the existing network, use the preserved private `TeleRC-Private-Fleet-v0.5.0rc1.zip` sketches. Retain existing pairing keys and radio settings; do not initialize a replacement network. Match each FC `SYSID_THISMAV` to its rover number.
4. Follow the fleet guide to connect, upload/read back, deliberately arm and explicitly start each rover.

Public LoRa example images are keyless with RF OFF. Private network files and provisioned binaries must stay out of public source and release archives. The older TM2 mission set is not the fleet BASE/ROVER firmware for this interface.

## Accepted software evidence

The release passed 355 Windows regressions, all 18 frozen-app checks, native firmware ASan/UBSan guards, two encrypted multi-rover graph tests and 11 actual board-build profiles. Publication verified the complete public asset boundary and downloaded checksums. See the published `test-evidence.zip` and firmware `BUILD_REPORT.json`.

The earlier firmware build evidence is reused only because firmware bytes are unchanged. This designation adds no physical qualification. Real RF capacity, range, motor stopping, power/EMI behavior, FC mission operation, failsafe timing and RC takeover still need physical acceptance tests. The Windows app remains unsigned.


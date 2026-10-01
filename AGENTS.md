# PC TeleRC continuation brief

## Mission
Build a reliable Windows operator bridge between the TeleRC-style ESP32-S3 MAVLink Wi-Fi link and a PXN steering wheel for ArduRover.

## Current milestone
0.1.0a3 — guided calibration + read-only diagnostics + audited controls + strict controller identity.

## Non-negotiable safety behavior
- Never auto-arm.
- Never auto-enable control after startup, calibration, controller reconnect, or MAVLink reconnect.
- Require fresh controller input and neutral throttle before enabling control or ARM.
- Pending settings must be explicitly applied before ARM/PC Control.
- On stale controller/MAVLink, latch PC control OFF.
- On disable/exit, send neutral then release RC override if the link is available.
- If a selected controller disappears, do not fall back to a different joystick.
- Configure ArduRover GCS fail-safe independently.

## Calibration design
- Capture neutral + full steering left/right.
- Separate pedals: capture full throttle + full brake.
- Combined pedals: capture full forward + full reverse.
- Infer axis and inversion only when movement exceeds validation thresholds.
- Calibration modifies mapping only; it never arms or enables MAVLink control.

## Diagnostics
- Diagnostics must remain read-only: no arm/disarm/control-enable side effects.
- Copyable report may include controller GUID and local endpoint configuration, but never credentials.
- Duplicate steering/throttle RC channel mapping is a hard failure for ARM and PC Control.

## Known limitations
- Exact PXN behavior still depends on Windows driver/mode.
- No force feedback or map/mission planner.
- Unsigned Windows test executable.
- Hardware fail-safe timing remains unverified.

## Next milestone
Hardware validation: PXN GUID/axis confirmation, ESP32 routing, Rover channel mapping, measured controller/Wi-Fi fail-safe timing, then lock a first tagged test release.

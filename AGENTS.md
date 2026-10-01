# PC TeleRC continuation brief

## Mission
Build a reliable Windows operator bridge between the TeleRC-style ESP32-S3 MAVLink Wi-Fi link and a PXN steering wheel for ArduRover.

## Current milestone
0.1.0a5 — modeless targeted diagnostics + persisted steering sensitivity on the field-hardening baseline.

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
- Diagnostics must remain read-only and modeless: no ARM/DISARM/control-enable side effects and no blocking of the main operator window.
- Live diagnostics are limited to Link, Controller, Mapping, Safety at 2-second refresh.
- Build the detailed report only on Copy Report.
- Copyable report may include controller GUID and local endpoint configuration, but never credentials.
- Duplicate steering/throttle RC channel mapping is a hard failure for ARM and PC Control.

## Controller sensitivity
- Range 25–100%; default 100%.
- Applies only to steering after deadzone/expo shaping.
- Preserve 0 and ±1 endpoints; lower values soften midrange response.
- Throttle limit remains independent.

## Field-hardening rules
- First accepted vehicle system ID is locked for the session; foreign heartbeat sources are ignored.
- Invalid calibrated axis indices fail closed.
- Any configuration/controller edit disables PC Control immediately.
- Override transmission failure latches PC Control OFF.
- Neutral/release is retried while transport remains available.
- A fixed ESP32 target IP is preferred for field deployment; dynamic UDP reply routing is diagnostic WARN.

## Known limitations
- Exact PXN behavior still depends on Windows driver/mode.
- No force feedback or map/mission planner.
- Unsigned Windows test executable.
- Hardware fail-safe timing remains unverified.

## Next milestone
Hardware validation: PXN GUID/axis confirmation, ESP32 routing, Rover channel mapping, measured controller/Wi-Fi fail-safe timing, then lock a first tagged test release.

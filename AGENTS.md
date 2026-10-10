# PC TeleRC continuation brief

## Mission
Build a reliable Windows operator bridge between the TeleRC-style ESP32-S3 MAVLink Wi-Fi link and a PXN steering wheel for ArduRover.

## Current milestone
0.1.1rc1 — radio dropdown candidate built directly on stable v0.1.0a10.

Preserve the a10 wheel/controller and UDP code paths. New modes: telerc_udp, lora_usb, elrs_serial. Separate saved lora_port/elrs_port; no pairing credentials in AppSettings. Publish candidates as drafts; v0.1.0a10 remains stable/Latest.

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
- Acts as steering gain: lower values proportionally reduce steering authority.
- Steering expo remains the independent nonlinear response control.
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

## Radio profiles
- LoRa uses CRC-framed native CDC compatible with TeleRC firmware commit 67b2cf5137989c1a6a65a4b02af960105d04afa3. Verify active SX1262 BASE, 115200, DTR high/RTS low, CH1/CH2. DIRECT motor profile only. Initial FAILSAFE sends neutral only, with a bounded DIRECT acquisition window.
- ELRS uses raw MAVLink USB at 460800, DTR/RTS low, 5 Hz overrides. No ordinary CRSF, automatic firmware flashing, or validated T ONE/Pocket arbitration.
- Apply Settings must not redirect a live session. Apply & Reconnect releases/closes the old profile before configuring/opening the new profile. Disconnect cancels pending restart callbacks.
- Physical radio range, failsafe latency, and named hardware are unverified until HIL evidence exists.

# PC TeleRC continuation brief

## Mission
Build a reliable Windows operator bridge between the TeleRC-style ESP32-S3 MAVLink Wi-Fi link and a PXN steering wheel for ArduRover.

## Current milestone
0.1.0a1 — connectivity + wheel input + bounded RC override + safety interlocks + Windows CI build.

## Non-negotiable safety behavior
- Never auto-arm.
- Never auto-enable control after startup, controller reconnect, or MAVLink reconnect.
- Require fresh controller input and neutral throttle before enabling control or ARM.
- On stale controller/MAVLink, latch PC control OFF.
- On disable/exit, send neutral then release RC override if the link is available.
- Configure ArduRover GCS fail-safe independently.

## Known limitations
- Exact PXN axis mapping is model/driver dependent.
- No force feedback or map/mission planner.
- Unsigned Windows test executable.
- Hardware fail-safe behavior remains unverified.

## Next milestone
0.1.0a2 hardware validation: exact PXN GUID/axis layout, ESP32 routing, Rover channel mapping, calibration wizard, measured fail-safe timings.

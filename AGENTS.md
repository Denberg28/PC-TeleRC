# PC TeleRC continuation brief

## Mission
Build a reliable Windows operator bridge between the TeleRC-style ESP32-S3 MAVLink Wi-Fi link and a PXN steering wheel for ArduRover.

## Current milestone
0.1.0a14 — native TeleRC LoRa USB, local board setup, dropdown navigation.

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
- Steering and drive gains are separate; drive is applied before the independent throttle limit. Neutral prerequisites use unscaled drive input.
- Acts as steering gain: lower values proportionally reduce steering authority.
- Steering expo remains the independent nonlinear response control.
- Throttle limit remains independent.

## Field-hardening rules
- First accepted ArduRover autopilot heartbeat locks system/component and UDP source endpoint. Other peers are rejected before parsing. Network changes require disconnect/reconnect.
- Invalid calibrated axis indices fail closed.
- Any configuration/controller edit disables PC Control immediately.
- Override transmission failure latches PC Control OFF.
- Neutral/release is retried when PC control owns the overrides. Monitor-only disconnect must not interrupt another controller.
- Disconnect stops GCS heartbeat and closes UDP; it does not disarm. Reconnect must wait for new heartbeat and fresh input.
- Preserve the send-lock serialization around tick/disable/configuration transitions; no drive write may occur after completed disable.
- Control-worker deadline misses must latch OFF even if newly sampled input is fresh.
- ARM/DISARM reports rejection, timeout, or heartbeat confirmation without automatic retry.
- A fixed ESP32 target IP is preferred for field deployment; dynamic UDP reply routing is diagnostic WARN.

## Known limitations
- Exact PXN behavior still depends on Windows driver/mode.
- No force feedback or map/mission planner.
- Unsigned Windows test executable.
- Hardware fail-safe timing remains unverified.

## Next milestone
Hardware validation: PXN GUID/axis confirmation, ESP32 routing, Rover channel mapping, measured controller/Wi-Fi fail-safe timing, then lock a first tagged test release.

ELRS mode is USB MAVLink only, 460800 baud, DTR/RTS low, 5 Hz PC overrides. No raw CRSF bay input or verified Pocket/PC arbitration. Named T ONE/GEPRC hardware requires physical validation.

## Native LoRa requirements
- Match TeleRC v0.8.53 framed USB protocol; base role/active radio must be read before driving.
- Motor identity is system 1/component 1; wheel commands are CH1 steer / CH2 drive only.
- Native USB 115200, DTR true/RTS false. Bound queue waiting and fail closed on partial/backed-up writes.
- No auto source switching. Page changes stop control; STOP stays visible on every page.
- Provisioning closes the driving session; no control packets from the setup page.
- Key is masked and RAM-only; never save/log/report it. Read inactive board before save, serialize exchanges, require USB reopen after timeout or board restart after successful save.
- Enable neutral control, wait for DIRECT, then explicit ARM with a preceding neutral packet. Physical HIL remains required.

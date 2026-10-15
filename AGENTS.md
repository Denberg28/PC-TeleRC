# PC TeleRC continuation brief

## Mission
Build a reliable Windows operator bridge between the TeleRC-style ESP32-S3 MAVLink Wi-Fi link and a PXN steering wheel for ArduRover.

## Current milestone
0.1.3 — stable offline maps, compact map minimize/restore and LoRa USB fixes. User explicitly authorized the stable release and offline/minimize additions on 15 October 2026 after confirming the direct 915 MHz LoRa link works. Publish only after automated/frozen Windows checks and packaged preset target compilation pass. Preserve earlier stable rollback releases.

The PC map uses native raster rendering, supports raster MBTiles and persistent cached tiles in offline mode. Vector PBF/Android MapLibre caches are unsupported. Keep local maps read-only, validate failures without replacing a working map, bound tile decoding/SQL work, and never fabricate GPS from map metadata or cached view. Map minimize/restore and preferences are display-only. Preserve LoRa 8–32 ASCII password support and compiled-pairing behavior. The exact tested preset is under stable_config/LoRa-915-PnP-v1; do not silently change its password, frequency or wire protocol.

User explicitly authorized stable v0.1.2 publication on 15 October 2026 after UI optimization. The stable-desktop workflow validates application/frozen media, firmware host checks and unchanged-source target provenance, then verifies complete draft assets before publishing Latest. Preserve v0.1.1 and v0.1.0a10 rollback downloads.

Camera/tiles/telemetry are display-only. No media operation may arm, enable, redirect the radio or fabricate input/heartbeat/GPS. Camera starts manually; lost/stalled video is indicated independently of control. Read telemetry only from the locked autopilot. Map requires confirmed fresh GPS and labels stale/waiting states. Keep camera credentials/tokens out of saved settings and diagnostics. Use the exact original TeleRC logo. Keyboard focus is now the central camera area. Sliders still require Apply and manual re-enable. Never route wheel snapshots through the GUI timer.

Keyboard requires focus in its driving area, all keys released for enable/ARM, and manual enable after focus loss or a GUI stall. Space has neutral priority and blocks held directions until release/repress. Never refresh keyboard timestamps in snapshot reads. The dedicated keyboard event-loop timer intentionally expires if the GUI stalls; recovered acquisition changes session. Wheel input still comes directly from WheelService.snapshot through InputService without GUI polling. Source/settings changes disable control. The keyboard candidate workflow builds application packages only; firmware is unchanged and remains the rc2 baseline.

Preserve the wheel connection session in ControlFrame; new instances require manual enable. Wi-Fi enable/ARM requires centered steering and CH1–CH4, matching bridge firmware. Firmware diagnostics preserve the last stop; do not increase watchdog thresholds to conceal electrical faults. See REVIEW-DROPOUTS.md and the conditional motor-side parameter patch.

The control worker reads WheelService.snapshot directly; never route control input through the GUI timer. Preserve sample acquisition timestamps and keep real stale-input stops. Recovered heartbeats preserve a latched stop reason until manual re-enable.

Preserve the a10 wheel/controller and UDP code paths. New modes: telerc_udp, lora_usb, elrs_serial. Separate saved lora_port/elrs_port; no pairing credentials in AppSettings. The user explicitly requested the next stable release on 14 October 2026. Publish v0.1.1 only after all application/firmware/target builds and download checks pass; mark it Latest. Keep v0.1.0a10 available as the previous stable rollback. Future unpromoted candidates remain drafts.

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
- Steering sensitivity applies after deadzone/expo shaping.
- Throttle sensitivity applies in the send path before throttle limit. Neutral checks use unscaled pedal input; never scale the safety frame.
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
- No force feedback or mission upload/planner; map is display-only.
- Unsigned Windows test executable.
- Hardware fail-safe timing remains unverified.

## Next milestone
Hardware validation: PXN GUID/axis confirmation, ESP32 routing, Rover channel mapping, measured controller/Wi-Fi fail-safe timing, then lock a first tagged test release.

## Radio profiles
- LoRa uses CRC-framed native CDC compatible with TeleRC firmware commit 67b2cf5137989c1a6a65a4b02af960105d04afa3. Verify active SX1262 BASE, 115200, DTR high/RTS low, CH1/CH2. INFO_V2 advertises the ARDUROVER backend; retain legacy INFO_V1 DIRECT support with neutral-only acquisition.
- ELRS uses raw MAVLink USB at 460800, DTR/RTS low, 5 Hz overrides. No ordinary CRSF, automatic firmware flashing, or validated T ONE/Pocket arbitration.
- Apply Settings must not redirect a live session. Apply & Reconnect releases/closes the old profile before configuring/opening the new profile. Disconnect cancels pending restart callbacks.
- Physical radio range, failsafe latency, and named hardware are unverified until HIL evidence exists.

ELRS reliability: 20 Hz safety checks separate from 5 Hz drive sends; monitor-only sessions never release RC. Serialize enable/disable/configure/ARM with sends. Fresh ArduRover autopilot heartbeat and input required. Missed watchdog deadlines and USB failures latch OFF. Purge the local output queue before owned neutral/release; USB write success never proves RF delivery. Reconnect timers carry a generation token and frozen applied settings; edits cancel them. Preserve original Wi-Fi/LoRa control rates and protocol frames.

LoRa ARDUROVER backend is advertised only by INFO_V2. Require real ArduRover sys1/comp1 heartbeat, MANUAL mode, fresh remote status and neutral acquisition. Remote stop counter/boot changes latch PC control OFF. Legacy INFO_V1 remains DIRECT-only. Current LilyGO firmware 0.5.0 selects saved Wi-Fi or SX1262 LoRa via BOOT; compiled nonempty password overrides NVS; relay count 0/1/2 must match all roles. NODE indices are ordered from BASE. Screen sleep/wake never interrupts control; first asleep BOOT gesture is consumed; runtime setup pauses all driving and restarts only after pending stop completes and at least 16 seconds of link silence; preserve old mesh development separately. Never fabricate an FC heartbeat or skip receiver takeover.


PWM capture confirms the falling edge after 30 us of stable low, preserving the original rise across shorter notches. Keep lastValidPulseUs at the physical falling-edge time; noise never renews input age. USB CDC diagnostic waits are bounded to 1 ms, not zero. Retain 150 ms PWM loss, 500 ms bridge loss and 300 ms neutral recovery.



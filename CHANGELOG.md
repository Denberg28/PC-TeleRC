## 0.1.5rc1 — LoRa mission planning

- Add map route/F1–F3 event editing and QGC WPL 110 import/export.
- Integrate addressed LoRa Mission v0.1.0 USB sessions, rover IDs 1–20, full readback,
  explicit one-shot start, policy validation and confirmed HOLD.
- Lock manual/mission ownership, purge cancelled jobs, stop on stale telemetry/GUI
  lease/USB failure, and block reconnect replay.
- Require auxiliary-output opt-in and FC function/limits checks; document independent
  OFF/cutoff and AUTO timing limits. Firmware and manual transports unchanged.

# 0.1.4rc1 — 18 October 2026

TeleRC operator workflow migration: persistent camera/map swap and collapse, cockpit telemetry tiles, selected-camera retry, native ELRS Backpack telemetry with handset authority and PING-only output, GPS fix freshness and recovered-heartbeat expiry. App-only candidate; firmware unchanged. See docs/releases/v0.1.4rc1.md.

## 0.1.3 — 2026-10-15

- Offline raster MBTiles, retained stale cache in offline mode, drag/zoom/follow and saved map view.
- Lower-left map minimize/restore with persisted preference.
- LoRa USB/password fixes from 0.1.3rc1 and exact user-confirmed 915 MHz direct preset.
- Automated regression, packaged Windows media/offline-map checks and preset target compilation.

# v0.1.2 — live camera desktop stable

- Central live camera with USB, RTSP/HTTP and HTTP MJPEG sources; explicit start/stop and stale/error indication.
- Lower-left GPS map, measured route/heading, optional cached online tiles and read-only battery/speed telemetry.
- Compact camera-oriented layout, collapsible Link/Input/Camera settings and percentage sliders.
- Exact TeleRC Android logo for title bar and Windows executable/installer.
- Existing wheel/keyboard input, brake priority, ownership, neutral acquisition and deadlines retained.
- Actual media decoding, layout, source isolation and locked telemetry tests; packaged Windows media/UI verification.
- Stable package includes unchanged source-matched firmware and SHA256-verified existing target builds.

# v0.1.2rc3 — keyboard driving

- Added selectable keyboard input: WASD / arrows, simultaneous steer/drive, and Space brake priority.
- Brake sends neutral; held directions require release/repress after braking.
- Dedicated driving focus prevents accidental input in settings; focus loss stops control with manual re-enable.
- Fresh acquisition timestamps, session changes after GUI stalls, and all-keys-released ARM/control gates.
- Existing independent sensitivities, wheel input, RC mapping and radio protocols retained.
- Added keyboard and Qt focus regression tests and a dedicated Windows application candidate build.

# v0.1.2rc2 — sketch pairing and relays

- LilyGO 0.5.0 adds sketch-level eight-character password/frequency, overriding old NVS when set.
- OLED turns off after 30 seconds; BOOT wakes without entering setup or stopping control.
- Standalone NODE sketch supports one/two ordered relays with matching key/frequency/count.
- Latest-command selection at TX, bounded forwarding, and response-driven relay cadence reduce avoidable delay.
- Existing 500 ms watchdog, neutral/ARM gates, receiver takeover and PWM glitch fix retained.
- Added display, sketch-pairing and actual-driver chain/outage/latency tests; target builds grouped by role.

# v0.1.2rc1 — runtime setup candidate

- LilyGO BOOT/OLED menu selects saved Wi-Fi/LoRa without reflashing; BASE remains USB-to-LoRa.
- Local setup AP and PC setup accept identical eight-character passwords, preserving advanced hex keys.
- Setup stops control, retries pending release and delays restart beyond PC heartbeat timeout.
- Incremental OLED output avoids blocking radio deadlines; existing watchdogs and PWM glitch fix retained.
- New runtime and password regression checks; six target builds and Windows packages retained.

# v0.1.1 — stable

- Consolidates LilyGO Wi-Fi/LoRa 0.3.1 with link indication and PWM converter 1.0.5 glitch filtering.
- Independent steering and throttle sensitivity retained.
- Bounded USB diagnostics retained across all current board roles.
- Separate compiled LilyGO rover Wi-Fi/LoRa targets and BASE, plus PWM and original ESP32 Wi-Fi/ELRS bridge builds.
- Stable publication follows successful regression, target-build and download checks.

# v0.1.1rc7

- PWM converter 1.0.5 confirms falling edges after 30 us of low level; short in-pulse noise no longer splits valid commands.
- USB CDC waits bounded to 1 ms on converter, Wi-Fi/ELRS bridge 0.1.5 and SX1262 pair 0.2.1.
- Retains existing watchdogs, 300 ms neutral recovery, takeover and independent sensitivity controls.
- CI builds all five ESP32-S3 firmware targets plus Windows installer/portable.

# v0.1.1rc6

- Separate steering and throttle sensitivity controls, persistence, and diagnostic values.
- Scale throttle before the independent throttle limit; retain unscaled neutral checks.
- Retain rc5 Wi-Fi, LoRa, ELRS, takeover, and disconnect behavior.

# 0.1.1rc5

- Retain rc3 direct wheel sampling and rc4 wheel-session/neutral/mapping fixes.
- Add two native-USB SX1262 sketches for BASE and ArduRover ROVER, firmware 0.2.0.
- Recognize INFO_V2 ARDUROVER separately from legacy DIRECT.
- Require real MANUAL heartbeat, neutral acquisition and authenticated rover status.
- Latch PC control off on remote stop, boot change, stale status or ownership loss.
- Surface rover stop cause in diagnostic reports. Preserve Wi-Fi bridge 0.1.4 and converter 1.0.4.
- Build current standalone Windows ZIP/installer and both ESP32 targets with pinned dependencies.

# Changelog

## 0.1.1rc2 — ELRS reliability candidate
- Separate 20 Hz ELRS safety checks from 5 Hz drive transmission; newest input only, no catch-up burst.
- Latch OFF on USB removal/stall/write failure and missed worker deadlines; reject stale/non-rover heartbeat for ARM/enable.
- Clear the local USB output queue before owned neutral/release; monitor-only ELRS sessions leave RC overrides alone.
- Serialize control transitions; DISARM releases PC control first.
- Cancel reconnect on edits and reject old delayed callbacks; settings-save errors remain visible and pending.
- Preserve COM selection on refresh and distinguish USB open from rover connected.
- Add ELRS fault injection and operator regression checks; named hardware still requires bench validation.


## 0.1.1rc1 — Radio dropdown candidate from stable a10
- Add ESP32-S3 Wi-Fi, LilyGO T3S3 SX1262 LoRa USB, and HGLRC T ONE 900 MHz ELRS USB MAVLink profiles.
- Preserve stable a10 controller and Wi-Fi implementation. Add independent COM ports, LoRa setup, and explicit connection handover.
- Hardware radio validation pending; stable a10 remains Latest.

## 0.1.0a10 — 2026-10-02
### Android-aligned rover channel mapping
- Changed the default rover mapping from CH1 steering / CH3 throttle to CH1 steering / CH2 drive, matching Android TeleRC.
- Added a settings schema version and one-time migration for the untouched legacy CH1/CH3 default.
- Existing custom mappings are preserved.
- Explicit current CH1/CH3 mappings remain valid after migration.
- Added regression tests for default and migration behavior.

## 0.1.0a9 — 2026-10-02
### ESP32 bridge control compatibility
- Fixed a bench-confirmed mismatch where pymavlink automatically switched PC TeleRC's outbound control packets to MAVLink 2 after receiving MAVLink 2 telemetry from ArduRover.
- PC TeleRC now keeps MAVLink 1/2 receive auto-detection but explicitly encodes bridge-facing GCS heartbeat, ARM/DISARM, RC override, neutral and release packets as MAVLink 1.
- Preserves source system 255 / component 190 required by the TeleRC ESP32 command filter.
- Added explicit wire-format regression tests for sparse RC override and sparse release packets.

## 0.1.0a8 — 2026-10-02
### MAVLink transport architecture
- Replaced separate receive/transmit MAVLink connections with one persistent bidirectional UDP socket.
- ESP32 target IP/port changes now update the live socket without restarting the UDP listener.
- UDP listener restarts only when listen address/port changes.
- Added lifecycle locking and idempotent start behavior.
- Added send serialization for command/control/heartbeat and live target updates.
- Added listener lifecycle regression tests.

### Windows packaging
- Switched from PyInstaller one-file to onedir inside the installer.
- Installed PC TeleRC now runs as one normal application process rather than the one-file bootloader/child pair.
- Portable distribution is now a ZIP of the onedir application.

## 0.1.0a7 — 2026-10-02
- Single-instance guard, targeted WinError 10048/10013 diagnostics, and safer reconnect sequencing.

## 0.1.0a6 — 2026-10-01
- Full code-review baseline with dependency integrity and UI symmetry checks.





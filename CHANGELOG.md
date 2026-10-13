# 0.1.0a14

- Native TeleRC v0.8.53 LoRa USB base-board transport and local board provisioning.
- Compact centered dropdown pages with persistent STOP and stop on navigation.
- CH1/CH2 motor compatibility, base role/radio checks, neutral/DIRECT ARM sequencing, pairing timeout isolation and RAM-only keys.
- Retain independent sensitivities, calibration, Wi-Fi and experimental ELRS.
- Hardware validation remains pending; see docs/LORA.md.

# 0.1.0a13 — 2026-10-03

- Separate saved steering and drive sensitivity sliders (25–100%); drive gain applies before the throttle limit.
- Retain raw pedal neutral checks so lowered drive sensitivity cannot bypass ARM/control prerequisites.
- Add experimental external ELRS TX USB MAVLink connection (460800 baud, DTR/RTS low, bounded serial I/O, 5 Hz RC override).
- Retain manual-enable/watchdog/identity protections and exclude TeleRC bridge ASCII from serial links.
- Document HGLRC T ONE + GEPRC PA500 hardware verification and unresolved Pocket/PC arbitration.

# 0.1.0a12 — 2026-10-03

- Fix repeated wheel disconnects caused by an unavailable pygame-ce method; use instance-matched removal events.
- Accept generic/boat autopilot heartbeats while preserving first vehicle identity and UDP endpoint locks.
- Send TeleRC discovery every second from the shared socket; retry explicit bridge Disconnect after neutral/release and before closing the socket.
- Reject wrong-port traffic for fixed targets before parsing; bound receive work so malformed traffic cannot starve the control watchdog.
- Block ARM/PC Control for channels 5–8, which the ESP32 command filter rejects.
- Add controller-runtime, pairing, repeated reconnect, heartbeat recovery, malformed traffic, endpoint filtering and bridge-channel tests.

# 0.1.0a11 — 2026-10-03

- Add explicit Disconnect and Connect/Reconnect workflows; close the old socket before applying network changes and require fresh heartbeat/input after reconnect.
- Serialize control ticks and Disable/configuration transitions, release old channel mapping before applying edits, and stop overrides before DISARM.
- Restrict UDP to one accepted ArduRover peer, expose send errors, exclusively bind the Windows UDP port, and prevent monitor-only RC release.
- Block control/ARM on pending network changes; report ARM/DISARM rejection, confirmation, and timeout.
- Reject nonfinite settings/controller input, overlapping axes, invalid calibration ranges, and stale calibration samples; detect controller reconnect generations and delayed workers.
- Make settings-write failures recoverable and diagnostics Copy Report timer safe on window close.

- Replace the steering sensitivity numeric field with a TeleRC-style horizontal slider and percentage label below the bar. Preserve the 25–100% range, saved settings, and explicit apply/manual control re-enable behavior.

# Changelog

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

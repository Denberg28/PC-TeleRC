# Changelog

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

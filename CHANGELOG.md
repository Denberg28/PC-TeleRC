# Changelog

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

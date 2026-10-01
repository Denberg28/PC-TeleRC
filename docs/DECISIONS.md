# Engineering decisions and assumptions

## 2026-10-01 — alpha architecture
- Platform: Windows 10/11 x64.
- Python 3.12 + PySide6 + pygame-ce + pymavlink.
- Control transport: MAVLink RC_CHANNELS_OVERRIDE at 20 Hz, default steering CH1 and throttle CH3.
- Safety: starts control-disabled, never auto-arms, requires neutral throttle, latches OFF on stale controller/heartbeat, neutral then release on shutdown.
- Throttle authority: 25% default for bench testing.
- Persistence: local JSON. No server database; use SQLite later only if session history is needed.
- Distribution: CI artifact for alpha; tags publish GitHub Releases.
- Repository was already public when work began.

## Hardware assumptions to validate
- PXN appears to SDL as a joystick/game controller.
- ESP32-S3 bridge is bidirectional UDP MAVLink on 14550.
- Rover uses 1500 us neutral and accepts RC overrides on configured channels.

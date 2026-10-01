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

## 2026-10-01 — calibration and UI audit
- Calibration is capture-based instead of relying on PXN model-specific hard-coded axis numbers.
- Axis selection requires significant movement; ambiguous/small movement is rejected.
- Calibration only changes local controller mapping and never sends arm/control commands.
- Once a controller GUID is selected, disappearance is treated as a disconnect rather than falling back to another attached joystick.
- Settings are explicit: Apply Settings updates controller/safety configuration; Apply & Reconnect restarts the MAVLink socket for address/port changes.
- ARM and PC Control are blocked while edited settings remain unapplied.

## Hardware assumptions to validate
- PXN appears to SDL as a joystick/game controller.
- ESP32-S3 bridge is bidirectional UDP MAVLink on 14550.
- Rover uses 1500 us neutral and accepts RC overrides on configured channels.


## 2026-10-01 — field hardening simulation
- Runtime ARM/control decisions use the same deterministic safety module as automated workflow simulations.
- The first accepted MAVLink vehicle system ID is locked until the MAVLink service is restarted.
- Missing/out-of-range controller axes are safety faults, not neutral defaults.
- Live configuration changes force PC Control OFF and require explicit manual recovery.
- RC override send failure is treated as a control-path failure and latches control OFF.
- Shutdown/fail-safe neutral/release is retried three times when a transport object remains available.
- A fixed ESP32 target IP is preferred in the field to avoid relying on last-peer UDP reply routing.


## 2026-10-01 — minimal diagnostics and sensitivity
- Diagnostics is modeless and kept off the control path.
- The live diagnostic surface is intentionally limited to four checks: Link, Controller, Mapping, Safety.
- Live diagnostics refresh every 2 seconds from existing snapshots; no network reads, controller reads, or command sends are initiated by diagnostics.
- Full support-report formatting is generated only on explicit Copy Report.
- Controller sensitivity applies only to steering and uses a bounded response curve that preserves full-scale endpoints.


## 2026-10-01 — full code-review cleanup
- Steering Expo owns nonlinear response shaping; Steering Sensitivity owns proportional steering gain. Avoid overlapping controls with ambiguous behavior.
- The main three operator cards use equal grid stretch and minimum widths for deterministic horizontal symmetry.
- Safety label state colors are applied explicitly because changing Qt objectName at runtime does not guarantee immediate stylesheet repolish.
- CI includes dependency integrity, headless UI construction, feature-contract tests, version consistency, and Windows packaging.

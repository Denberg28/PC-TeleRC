# Changelog

## 0.1.0a2 — 2026-10-01
### Added
- Guided wheel/pedal calibration with movement validation, automatic axis detection and inversion.
- Explicit Apply Settings and Apply & Reconnect workflow.
- Button-action audit documentation and operator tooltips.

### Changed
- UI reorganized into ordered MAVLink, controller, and safety/control sections.
- ARM, DISARM, PC Control, calibration and controller-selection availability now follow actual link/controller state.
- Selected controller GUID is now strict; if it disappears, another joystick is not silently substituted.
- Pending settings block ARM/PC Control until explicitly applied.

### Sanitized
- Removed implicit multi-signal auto-save behavior in favor of deterministic operator actions.
- Kept calibration out of the MAVLink control path.
- Reduced SDL initialization to display/event + joystick subsystems.

## 0.1.0a1 — 2026-10-01
### Added
- Windows PySide6 operator UI.
- UDP MAVLink heartbeat/link monitoring via pymavlink.
- PXN/SDL controller discovery and live axis diagnostics.
- Separate/combined pedal modes with inversion, deadzone, steering expo, throttle limit.
- Configurable steering/throttle RC channels.
- Explicit ARM/DISARM and gated PC Control.
- Stale-link and stale-controller fail-safe latch.
- Neutral-then-release RC override shutdown behavior.
- Local atomic JSON settings persistence.
- Windows GitHub Actions tests, PyInstaller EXE build, SHA-256 artifact, tag-based release workflow.

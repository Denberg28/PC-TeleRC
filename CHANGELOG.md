# Changelog

## 0.1.0a5 — 2026-10-01
### Diagnostics
- Replaced modal diagnostics with a modeless, non-blocking field-status window.
- Reduced live diagnostics to four targeted checks: Link, Controller, Mapping, Safety.
- Reduced refresh rate to 2 seconds and removed continuous full-report rendering.
- Full technical details are generated only when Copy Report is pressed.

### Controller
- Added Controller Sensitivity (25–100%) for steering.
- 100% is linear; lower settings soften center response while preserving full steering endpoints.
- Sensitivity is independent from throttle limit and persists in local settings.

### Verification
- Added sensitivity endpoint/midrange/clamping tests.
- Added targeted-diagnostics regression tests.

## 0.1.0a4 — 2026-10-01
- Field-hardening simulation baseline with centralized safety rules, vehicle-source lock, repeated neutral/release, transport simulation and field logging.

## 0.1.0a3 — 2026-10-01
- Read-only Diagnostics panel and duplicate RC-channel protection.

## 0.1.0a2 — 2026-10-01
- Guided wheel/pedal calibration, explicit settings workflow, strict selected-controller identity, and UI action audit.

## 0.1.0a1 — 2026-10-01
- Initial Windows MAVLink/PXN alpha with bounded RC override, watchdogs, local settings, and CI build.

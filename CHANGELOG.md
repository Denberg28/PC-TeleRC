# Changelog

## 0.1.0a7 — 2026-10-02
### Windows UDP reliability
- Added a process-wide single-instance lock so two PC TeleRC windows cannot compete for UDP 14550.
- Added targeted operator messages for WinError 10048 (UDP port already in use) and WinError 10013 (Windows denied access / excluded port range).
- Diagnostics Link status now shows the targeted socket failure directly.
- Apply & Reconnect now waits for the previous MAVLink worker to stop and adds a short socket-release delay before rebinding.
- MAVLink stop now reports failure if the worker thread does not terminate within the shutdown timeout.
- Added regression tests for Windows UDP error translation and targeted diagnostics.

## 0.1.0a6 — 2026-10-01
### Full code review
- Fixed a diagnostics report syntax regression introduced during the minimal-diagnostics refactor.
- Updated diagnostics tests to the current four-check feature contract.
- Added a headless PySide6 UI smoke test covering main-window construction, equal three-column geometry, and modeless diagnostics.
- Added package/pyproject version-consistency testing.
- Changed Steering Sensitivity to a clear gain/authority control so it no longer duplicates Steering Expo behavior.
- Normalized the three primary UI cards with equal column stretch/minimum widths and expanding size policy.
- Made safety-state colors deterministic instead of relying on runtime objectName stylesheet repolishing.
- Removed an unused network-field constant.
- Added `pip check` to CI.
- Updated checkout, setup-python, upload-artifact and release actions to current major versions.

## 0.1.0a5 — 2026-10-01
- Modeless targeted diagnostics and persisted steering sensitivity.

## 0.1.0a4 — 2026-10-01
- Field-hardening simulation baseline with centralized safety rules, vehicle-source lock, repeated neutral/release, transport simulation and field logging.

## 0.1.0a3 — 2026-10-01
- Read-only Diagnostics panel and duplicate RC-channel protection.

## 0.1.0a2 — 2026-10-01
- Guided wheel/pedal calibration, explicit settings workflow, strict selected-controller identity, and UI action audit.

## 0.1.0a1 — 2026-10-01
- Initial Windows MAVLink/PXN alpha with bounded RC override, watchdogs, local settings, and CI build.

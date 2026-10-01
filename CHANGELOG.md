# Changelog

## 0.1.0a4 — 2026-10-01
### Field hardening
- Centralized ARM/control-enable safety decisions into one deterministic module used by runtime and simulations.
- Added full operator workflow simulations for startup, preflight, controller loss, reconnect, Wi-Fi loss, invalid axes, and invalid RC mapping.
- Locked each MAVLink session to the first accepted vehicle system ID; foreign vehicle heartbeats are ignored and counted.
- Controller axis count is now passed into the runtime safety gate; unavailable calibrated axes fail closed.
- Any configuration edit, settings apply, or controller change disables active PC Control and requires manual re-enable.
- RC override send failure now latches fail-safe and disables PC Control.
- Neutral/release is retried multiple times when the transport remains available.
- Diagnostics warns when no fixed ESP32 target IP is configured for field use.

## 0.1.0a3 — 2026-10-01
### Added
- Read-only Diagnostics panel for troubleshooting MAVLink, heartbeat, controller identity/freshness, axes, mapping, settings state, fail-safe state, and traffic counters.
- Copy Diagnostic Report action for support/troubleshooting.
- Diagnostic unit tests for healthy state, missing controller, and duplicate RC-channel faults.

### Fixed
- Steering and throttle can no longer enable PC Control or ARM when mapped to the same RC channel.

## 0.1.0a2 — 2026-10-01
- Guided wheel/pedal calibration, explicit settings workflow, strict selected-controller identity, and UI action audit.

## 0.1.0a1 — 2026-10-01
- Initial Windows MAVLink/PXN alpha with bounded RC override, watchdogs, local settings, and CI build.

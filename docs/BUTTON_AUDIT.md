# Button and action audit — 0.1.0a2

| UI control | Handler | Preconditions | Result / safety behavior |
| --- | --- | --- | --- |
| Apply & Reconnect | `_apply_and_reconnect` | none | Disables PC control, saves settings, restarts MAVLink, leaves control OFF. |
| Use selected | `_select_controller` | detected controller | Persists exact GUID and selects only that controller. |
| Calibrate wheel & pedals | `_calibrate_controller` | controller connected | Disables PC control if active, opens capture wizard, changes only mapping. |
| Apply Settings | `_apply_settings` | none | Persists controller/safety settings. Network edits remain marked pending restart. |
| ARM | `_vehicle_command(mav.arm)` | link connected, disarmed, no pending settings; MAVLink layer also requires fresh controller + neutral throttle | Sends explicit MAV_CMD_COMPONENT_ARM_DISARM arm request. |
| DISARM | `_vehicle_command(mav.disarm)` | link connected, armed, no pending settings | Sends explicit disarm request. |
| Diagnostics | `_open_diagnostics` | none | Opens read-only diagnostics; sends no ARM/DISARM/control commands. |\n| Enable PC Control | `_toggle_control` | link + controller healthy, no pending settings; MAVLink layer also checks freshness + neutral throttle | Enables 20 Hz RC override. Never automatic. |
| Disable PC Control | `_toggle_control` | currently enabled | Sends neutral then releases steering/throttle override where link permits. |

## Review findings
- Removed the original implicit auto-save fan-out from multiple signals.
- Network settings are now visibly distinct from settings that can be applied without a socket restart.
- Controller identity is strict after selection; no silent fallback to a different joystick.
- Calibration and reconnect paths explicitly disable PC control.
- ARM and PC Control are blocked when edited settings are pending.
- UI enable/disable state is advisory; the MAVLink service still independently enforces link, freshness, and neutral-throttle checks.

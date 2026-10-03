# a12 link and reliability review

2026-10-03. Scope: controller polling, UDP transport/parser, MAVLink worker lifecycle, command serialization, UI connect/disconnect/settings, channel mapping, watchdogs, persisted settings, single-instance guard and Windows packaging. Includes the a11 comparative regression analysis.

## Corrections

1. Replace the nonexistent pygame-ce get_attached() API with instance-matched JOYDEVICEREMOVED events. Repeated sampling stays connected; removal invalidates input/generation.
2. Restore heartbeat compatibility for generic/boat and nonstandard components while rejecting GCS/invalid autopilot and reserved system IDs. Preserve accepted system/component and source endpoint for the session.
3. Send exact bridge discovery bytes every second from the bound UDP socket. This bootstraps unicast routing even if broadcast telemetry is unavailable, and refreshes the bridge lease while monitoring.
4. Send explicit bridge disconnect three times after owned neutral/sparse release and before closing UDP, only for sessions that sent discovery. The bridge independently validates source ownership. UDP send success is not delivery acknowledgement.
5. Fixed targets now require source IP and source port to match. Dynamic targets retain first accepted peer lock. Unrelated traffic is rejected before parsing and cannot inherit commands; parser buffers are reset across sender changes.
6. Use one recv_msg per loop instead of recv_match's internal skip loop. BAD_DATA does not count as valid telemetry and cannot postpone watchdog checks indefinitely. Real UDP malformed/ASCII traffic followed by heartbeat recovers without stopping the worker.
7. Block ARM/control for CH5–8, whose nonignored values fail the current bridge RC command filter. Existing saved mappings are retained and flagged, not silently remapped.

## Workflow and safety checks

- Exclusive Windows bind, recoverable port conflict, one source socket for discovery/commands/reception, no broadcast command fanout.
- Disable/configure/tick serialized; no drive write follows completed disable. Release old mapping before applying edits.
- Monitor-only disable sends no RC override. Bridge Disconnect relinquishes the current PC session lease; another IP's active pairing is rejected by firmware.
- Stop closes the socket and clears vehicle, input and pending-command state. Repeated sessions reuse the port, require new heartbeat and remain control OFF.
- Stale input/heartbeat, send failure and delayed worker latch control OFF; healthy recovery does not auto-resume.
- ARM requires neutral/fresh input and accepted heartbeat; DISARM stops override first. ACK rejection and heartbeat confirmation remain explicit.
- Settings validate finite input/IPs and writes use replacement; invalid mappings fail closed. UI rejects unapplied network settings and waits for old worker exit before reconnect.
- No remote code execution, shell command execution, credential storage or downloaded update execution was found in the app source inspected. This statement is not a dependency vulnerability audit.

## Verification

88 local tests pass. New tests cover runtime wheel API/removal, heartbeat variants, GCS exclusion, discovery-driven UDP acquisition/refresh, three connect/disconnect cycles with explicit lease release, wrong-port filtering, malformed traffic and stale-to-healthy recovery, and unsupported channel mapping. Existing tests cover drive PWM/wire format, neutral/release, send failures, worker delay, concurrent disable, calibration, diagnostics, UI workflow, settings and single-instance behavior. Windows release workflow repeats the suite, pip check, compileall, PyInstaller and Inno Setup packaging.

## Remaining operational limits

- No PXN/ESP32/flight-controller hardware was available here. Exact cause of the user's missing heartbeat is not proven without received headers/logs; the wheel regression is confirmed.
- Current bridge requires local AP client source port 14550, discovery/disconnect support, and only one active client. Configure standard target 192.168.4.1:14550 and listen 0.0.0.0:14550. Fixed-target source-port strictness intentionally requires matching firmware telemetry port.
- Bridge GCS heartbeat is rejected rather than forwarded; GCS failsafe assumptions must be validated on the rover. PC neutral/release cannot guarantee a stop across a dead radio link.
- UDP has no delivery acknowledgement; unsigned/unencrypted MAVLink and source filtering do not authenticate a hostile peer. Treat the AP as a trusted control network.
- Windows firewall/network routing, driver hot-plug behavior, physical stop timing and transmitter takeover need bench validation. Installer is unsigned.

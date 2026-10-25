# FC Mission Inspection and Replacement Safety (development candidate)

Scope: PC TeleRC v1.2.0rc1 mission baseline. This branch adds read-only **Load from FC** support. It does **not** change radio firmware or declare flight/field readiness.

## Operating sequence
1. Connect to the intended addressed rover, validate the fresh FC heartbeat and SYSID.
2. Select **Load from FC** to retrieve the onboard mission using MAVLink MISSION_REQUEST_LIST / MISSION_COUNT / MISSION_REQUEST_INT, with bounded attempts. A returned zero count is explicitly represented as empty. Incomplete reads are errors, never a valid empty plan.
3. Show the readback separately as immutable mission rows. Do not overwrite a dirty PC draft or treat inspection as a verified upload.
4. For replacement, review the rover ID, route coordinates, action commands, auxiliary-off protections and loss policy. Require DISARMED MANUAL/HOLD and explicit digest/rover confirmation.
5. Upload a complete new mission via MAVLink mission protocol, then download it again and compare all rows. Only a matching complete readback enables the existing start workflow. Upload is replacement, not append.
6. Any timeout, unexpected ACK, FC reboot, heartbeat loss, relay route interruption, HOLD or session change invalidates verification. The actual FC mission state then is UNKNOWN; reconnect and inspect from FC before trying again.
7. Keep ARM/START/DISARM one-shot commands non-replayed. Never auto-arm, auto-start or auto-resume based on restored route files.

## Network reliability and fleet isolation criteria (not yet implemented/qualified here)
- Preserve per-rover SYSID identity and network addressing; reject other rover mission messages.
- Only one mission transaction in the fleet radio budget at once. Prioritize time-critical HOLD, telemetry liveness and fleet heartbeats.
- Use sequenced, integrity-checked LoRa frames with replay rejection, bounded retransmission/backoff and explicit session identity. Do not treat a LoRa packet ACK as an FC mission ACK.
- Verify an entire FC mission after transfer rather than trusting intermediate radio frame acknowledgment.
- Never rely on the LoRa radio or PC app alone for stopping or accessory cutoff; configure and test independent FC failsafes and handheld takeover.
- Test with direct and multi-hop links, injected loss/duplicates/out-of-order delivery, relay reboot, brownout, disconnect mid-upload, FC reboot, wrong SYSID and 20-rover loading before hardware release.

## Release gates
- Unit tests: empty FC, complete FC, incomplete rows, reordered/duplicate replies, unexpected MAVLink source, interrupted upload, replacement readback mismatch.
- Qt UI tests: Load from FC only when connected; draft unaffected; START still gated; HOLD pre-empts in-flight operations.
- Real LilyGO SX1262 BASE/NODE/ROVER target builds and Windows frozen integration tests.
- Restraint-first physical verification of LoRa dropouts, RC takeover, FC failsafe, stationary HOLD, motor cutoff, auxiliary OFF.
- Do not publish as stable or assert long-range reliability before these tests pass.

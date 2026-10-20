# Mission release review — PC TeleRC 0.1.5rc2 / LoRa Mission 0.2.0rc1

## Findings and fixes

| Finding | Change | Verification |
| --- | --- | --- |
| DO events could overlap a travel leg | Each F block begins a settling condition while the next active NAV command is a stopped relative delay. Action points also request a one-second waypoint stop. Unsafe legacy servo plans are rejected. | Pinned Rover 4.6.3 AP_Mission/ModeAuto source review, sequence tests and a real SITL ON/OFF arrival-window acceptance pass. |
| Busy transfer could starve a real GCS heartbeat | BASE alternates the actual host heartbeat with queued mission work. ROVER packs up to four complete MAVLink frames in a bounded 100-byte response, including genuine FC heartbeat. | Actual Runtime native tests and sanitizer runs for direct/one/two-node profiles. |
| HOLD could wait behind queued START work at BASE | Purge unsent BASE commands/pending DATA on HOLD and prioritize the confirmed HOLD frame before heartbeat/mission work. On-air frames remain non-recallable. | Actual BASE Runtime purge/priority regression. |
| Repeated navigation slots could starve other streams | Critical/navigation slots use rotating cursors. | Bounded batch and cursor tests. |
| Old/manual BASE could be mistaken for mission firmware | Require a local TM2 capability handshake for firmware 0.2.0, route length and auxiliary mask. | USB session tests; hardware capability confirmation remains a bench check. |
| Empty/unfinished draft prevented a recovery connection | Connect is independent of plan validity. HOLD remains available; upload/start retain validation gates. | UI recovery test. |
| ArduRover normalizes non-position readback frames | Normalize only GLOBAL/MISSION action frames while preserving coordinate, command and parameter comparison; unsafe frames still reject. | Found with actual Rover 4.6.3 SITL; targeted regression. |
| Legacy mission requests induced coordinate rounding | Always reply with MISSION_ITEM_INT, including deprecated MISSION_REQUEST. Keep exact integer-coordinate readback comparison. | Found with actual Rover 4.6.3 SITL; integer-request regression. |
| START stayed available after a start attempt | Consume verification before the one-shot START. No reconnect or replay. | Client ACK-loss/one-shot and desktop session tests. |
| In-flight policy/readback work could sustain heartbeats after telemetry loss | Five-second FC heartbeat limit also applies inside transactions; repeated position timestamps do not refresh stationary samples. | Stale/duplicate-source tests. |
| RC takeover could leave an incorrect AUTO label | FC mode/disarm telemetry changes the persistent mission phase without sending a competing mode command. | Heartbeat state test and code review. |
| Long text displaced the map and hid important state | Collapsible plan panel, on-demand Help/log, compact output settings and persistent phase/telemetry rows. | Offscreen normal/expanded layout inspection and display-only toggle tests. |
| Read-only review was disabled with editing | Freeze editing/identity/profile controls while connected, retain route scrolling/export and display controls. | UI/manual ownership regressions. |
| Closing/Escape could leave ownership unclear | All dialog completion paths close the worker; shutdown remains blocked if it has not stopped. | Escape/close and session exclusion tests. |
| Drafts were lost on close | Bound, validated atomic draft persistence restores planning only. Permissions, connection and START readiness are never restored. | Draft restoration test. |
| UI self-test could read an operator draft | Self-test uses a temporary draft path in addition to temporary map data. | UI self-test. |

## Boundaries

The existing wheel/keyboard control worker, manual Wi-Fi/LoRa/ELRS/Backpack,
FPV, existing offline map implementation and motor converter are preserved.
There are no production ARM, PARAM_SET, direct servo, RC override or forced-mode
commands in the new mission transport. ArduRover remains responsible for arming,
navigation, RC takeover and onboard failsafes.

The radio protocol retains separate per-rover AES-GCM keys, routing HMAC,
challenge freshness and consumption, addressing, bounded queues and narrow command
permissions. All BASE/ROVER/NODE boards must be from one newly generated 0.2.0 set.
One active selected rover is supported, with zero to two fixed relay nodes.

Planned OFF commands, stopped delays and FC PWM settings are not physical actuator
feedback. HOLD, link loss or app termination can skip OFF mission rows. The
independent accessory cutoff and physical RC stop remain necessary.

## Qualification

See the release evidence for actual test/build results. Host simulation is not
RF/physical qualification. The pre-existing GitHub Windows build failed before
executing steps. A local Wine fallback cannot start its required Unix socket in
this runtime; no unverified executable is presented as a Windows release.
Native Windows/frozen acceptance and restrained hardware testing remain gates
before stable promotion.

## Primary references inspected

- ArduPilot Rover-4.6.3: `libraries/AP_Mission/AP_Mission.cpp`,
  `Rover/mode_auto.cpp` (mission scheduling, waypoint stop and relative NAV_DELAY).
- https://ardupilot.org/rover/docs/common-mavlink-mission-command-messages-mav_cmd.html
- https://ardupilot.org/rover/docs/rover-failsafes.html
- https://mavlink.io/en/services/mission.html

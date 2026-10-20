# Mission planning — PC TeleRC 0.1.5rc2

Use the dedicated **Mission** window with the complete **LoRa Mission 0.2.0rc1**
BASE/ROVER/NODE set under `firmware/mission`. The manual Link profiles remain
separate. Existing stable/manual firmware is preserved for rollback.

## Operator flow

1. **Plan.** Import QGC WPL 110, or enter a reviewed latitude/longitude and Center
   map, then tap numbered points. Choose an F1/F2/F3 ON/OFF event for its next map
   tap; normal waypoint placement resumes automatically. Reorder/remove rows as
   needed. Output settings assign each used F function to a unique dedicated output
   and reviewed OFF/ON PWM. Every used function needs a final OFF event. Speed starts
   at 0.5 m/s. The editor accepts 1–60 points within the 200-row FC mission limit.
2. **Connect.** Select the BASE COM port and rover ID 1–20, matching SYSID_THISMAV.
   The app closes manual radio ownership, confirms BASE 0.2.0 capabilities and waits
   for a genuine addressed FC heartbeat. Connecting also works without a valid plan
   so you can request HOLD on an existing mission. Editing, identity and loss-policy
   choices stay locked until disconnect; map/panel display and route review remain available.
3. **Upload & verify.** Requires fresh DISARMED MANUAL/HOLD telemetry. Review the
   exact ordered coordinates/actions and type the requested rover/digest phrase.
   The client checks the configured FC loss policy, uploads, requires an accepted
   ACK and compares every actionable row from full readback. Upload never starts.
4. **Start mission.** Arm using the independent RC transmitter and FC pre-arm checks.
   The button requires fresh ARMED MANUAL/HOLD and verified upload. Review and type
   the new exact target/digest phrase. The app repeats readback and policy/output
   checks, requires fresh real 3D GPS and stationary reports, and sends START once.
   Accepted ACK plus a subsequent ARMED AUTO heartbeat confirms it. No ARM command,
   parameter write, direct servo action or RC override is sent by the mission app.
5. **HOLD.** Cancels pending mission jobs and requests HOLD. Only a fresh FC HOLD
   heartbeat confirms mode. HOLD remains available during transaction processing
   and confirmation. RC/FC takeover updates the status without competing commands.

## F-event timing and limits

Rover 4.6.3 processes DO/CONDITION commands alongside a NAV command. The generated
sequence places a settling condition and F actions before a relative stopped
NAV_DELAY, so the stopped NAV command is active while that action block runs.
Action waypoints also request a one-second arrival stop. An initial stopped block
sets speed and used functions OFF; a final stopped block repeats OFF.

Legacy servo WPL plans without these windows are rejected. Imported plans remain
read-only and retain their exact rows; Clear starts a new editable route. WPL row 0
is FC home metadata, not an actionable target or a live GPS fix. Position accuracy
and arrival behavior depend on FC navigation settings and sensors. A planned delay
is not physical stationarity/output feedback. No SERVO_OUTPUT_RAW confirmation or
independent auxiliary watchdog is supplied by this firmware.

Auxiliary execution is opt-in. Before connecting, verify the dedicated wiring,
OFF PWM, independent cutoff and generated firmware permission mask, then check
**Auxiliary cutoff verified**. The app reads SERVOx_FUNCTION=0 and MIN/MAX containing
all requested values before upload/start. M5–M8 are always reserved for motors;
other actual steering/motor outputs must also be excluded. Initial/final OFF rows
can be skipped after HOLD, loss, reset or interruption. HOLD does not guarantee OFF.

## Loss and recovery

Default profile requires FS_GCS_ENABLE=1, FS_ACTION=2 and GCS ID 255. The confirmed
route sets a minimum verified GCS timeout of 3/5/7 seconds for direct/one/two-node
links, with a 10-second ceiling. These are commissioning limits, not measured
stopping guarantees. Configure an appropriate FC value deliberately and measure
actual loss response and stopping distance. The app never writes these parameters.

**Continue AUTO on link loss** is an explicit connection-time choice requiring
FS_GCS_ENABLE=2 and FS_ACTION=2. It permits onboard AUTO continuation on GCS loss;
RC, fence, battery, EKF and other FC failsafes remain independent. Radio delay still
affects upload, START and HOLD delivery. Onboard execution follows FC timing after
START is accepted; no simultaneous fleet scheduling or collision avoidance is provided.

USB failure, stale FC telemetry, transaction failure, GUI lease expiry (2 s), or
closing the mission window stops the link and host heartbeats, clears readiness
and discards pending local work. There is no automatic reconnect, START retry or
resume. An already transmitted radio command cannot be recalled. A missing START
ACK or unconfirmed HOLD is **state unknown**, never a confirmed stop. Use independent
RC takeover and a physical cutoff. Wait at least 5 seconds between rover sessions;
this interval does not establish that the previous rover stopped.

## Display and saved plans

**Plan panel**, **Output settings** and **Help** expand/collapse without changing
authority or restarting the radio. The normal mission phase and FC state remain
visible; detailed messages are in Help. System minimization retains the same
monitoring session while the GUI remains responsive. Closing ends the session.

Drafts are saved atomically and restored as planning only. Connection, auxiliary
permission, continuation choice and START readiness are never restored. Export WPL
for a portable copy. Existing offline raster MBTiles and cached tiles work in the
mission map. Vector PBF/Android MapLibre caches remain unsupported.

## Firmware setup and qualification

Run `firmware/mission/MAKE-MATCHING-SKETCHES.cmd`, or use its provisioning command.
Flash every board from that one private generated set; do not mix 0.1.0-dev and 0.2.0
roles. Prefer random per-rover keys. No password or private key is saved in app
settings or distributed in the release. See the firmware README for board setup,
GPIO43/44 UART wiring, optional fixed nodes and loss-profile parameters.

This is a release candidate. Host/protocol tests and compilation do not establish
RF reliability, physical stopping distance or accessory OFF. The included BUILD-WINDOWS-MISSION.cmd produces a portable package only after
native Windows tests and frozen checks pass. Native Windows/frozen qualification
and the restrained acceptance procedure remain required before stable
promotion. See MISSION-REVIEW-015.md and the release evidence for actual results.

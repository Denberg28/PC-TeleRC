# PC TeleRC 1.2.0rc1 — map-only fleet station

The central map displays genuine GPS positions labelled Rover 1, Rover 2, etc.
Select a rover to edit its separate mission on the right. Each rover has Connect,
Arm, Mission start, Disarm and HOLD controls. FPV video uses external monitors;
this Windows build contains no integrated camera controls or video decoder.

## Matching firmware and migration

Install the included fleet **BASE and ROVER 0.5.0rc1** sketches before using this
fleet interface. The previous scalable 0.4.0 BASE supports one session and cannot
provide the new concurrent sessions or addressed PC arming. The fleet app rejects
that BASE, and the fleet BASE rejects older ROVER firmware before admitting work.

The separate private upgrade bundle preserves your existing pairing project,
frequency, power and all 20 rover identities. Upload its matching BASE once and
its corresponding ROVER sketch to each rover. The FC's SYSID_THISMAV must match
its rover ID. Existing TU2 0.4.0 relay nodes remain wire-compatible; the node-only
compatibility graph is tested. The four-BTS7960 PWM converter remains 1.0.5 and
does not need re-upload for this update. Do not initialize another network project.
Never share private Config.h files or NETWORK.private.json.

## Workflow

1. Choose the BASE native USB COM port and Open BASE. This only identifies the
   fleet interface; it does not arm or start any rover.
2. Select a rover and plan its route offline. Each ID has a separate saved draft.
3. Connect that rover. Wait for addressed FC telemetry and route qualification
   before connecting another rover. Connected rovers remain monitored together.
4. Upload & verify the selected rover's mission while disarmed. Confirm its exact
   rover number and mission digest. One upload/control transaction runs at a time;
   background telemetry and actual PC heartbeats continue for the other rovers.
5. Arm: confirm `ARM ROVER N`. The app requests HOLD, verifies stationary fresh
   GPS, the uploaded plan, the FC's arming requirements and full pre-arm-check
   configuration, then sends one normal arming command. It never uses force arm.
6. Mission start: review and confirm that rover and exact mission. START is sent
   once and requires its ACK and a fresh ARMED AUTO heartbeat.
7. Disarm: confirm `DISARM ROVER N`. This cancels that rover's pending work,
   requests HOLD, confirms fresh stationary GPS, and sends normal disarm once.
   HOLD remains independently available while another rover's upload is running.

Missing ARM/START/DISARM acknowledgments mean UNKNOWN and never trigger an
automatic retry. Inspect the actual vehicle/RC state. Reconnect and re-upload
before another mission start. The app never changes FC parameters or arms,
starts, reconnects or resumes automatically.

Use the verified GCS loss profile (7–10 seconds for the maximum-two-hop mission
profile). Default is HOLD on loss. Continue AUTO on loss is a separate deliberate
option and requires its matching FC configuration. Disconnecting one rover stops
its PC heartbeats; the other sessions continue. Closing BASE or a stalled UI stops
all PC heartbeats. FC loss policy, RC takeover and physical cutoff are independent.
HOLD does not confirm accessory OFF. Disarm requires fresh stationary evidence;
use the independent local controls if telemetry is unavailable.

## Map and radio capacity

The fleet map does not interpolate missing fixes or copy coordinates between IDs.
Fresh fixes move the labelled marker; a stale link retains a grey last-known label
with its sample age. Selecting a rover or tapping the map does not acquire control.
Pan/zoom, saved raster MBTiles and the existing bounded tile cache remain available.

There are 20 supported rover identities and at most two active relay hops.
Concurrent connections are admitted against measured RTT/airtime, with a failed
reply and foreground-command allowance. This is **not a guarantee that 20 rovers
can be monitored simultaneously** on every topology. A full or slow network
rejects additional work explicitly; no stale position is presented as live.
Discovery is globally paced. One missing rover does not own the whole BASE queue.

This candidate adds monitoring and individual deployment, not collision avoidance,
synchronized fleet starts, path deconfliction or automatic fleet coordination.

## Evidence and rollback

Current Windows regressions, a frozen map-only executable check, native guard
sanitizers, actual encrypted three-rover graph tests and actual board builds gate
publication. Graph tests do not model RF collisions, range or electrical behavior.
Physical fleet capacity, failsafe timing and motor/RC qualification remain pending.
Keep PC TeleRC 1.1.0rc1 and its matching baseline for rollback. Do not mix BASE /
ROVER protocols. Public example binaries are RF-OFF; use private matching sketches.

References: ArduPilot [normal arming commands](https://ardupilot.org/dev/docs/mavlink-arming-and-disarming.html)
and [Rover arming](https://ardupilot.org/rover/docs/arming-your-rover.html).

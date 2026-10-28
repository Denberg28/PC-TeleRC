# PC TeleRC v1.2.0rc8 — final feature and function review

Date: 28 October 2026. Review type: source self-review, automated regression,
native sanitizer, addressed graph simulation and rendered Qt inspection.
This is a Windows **release candidate**. It is not a physical field qualification.

## Scope and baseline

Published rc7 source: `9e6ed22dd78ce680962a74ba3e69639064cabff0`.
Compact layout proposal: `22f73624b4deccf9efdc067363852ed32905873f`.
The designated mission-planning base remains rc6. rc8 changes presentation,
icon resources, an online-map preference save, verification and delivery metadata.
The mission worker, shared transaction client, native USB framing, radio firmware,
private pairing and saved route formats are retained.

The packaged application starts `FleetWindow`. The earlier camera/manual-driving
window remains historical source and regression coverage, and is excluded from
the frozen fleet executable together with pygame and QtMultimedia. A passed legacy
source test does not add wheel, keyboard, Wi-Fi/manual-LoRa, ELRS or FPV controls
to this release. The source includes those histories for compatibility review.

## Complete operator feature inventory

| Feature / function | Reviewed behavior and limits | Automated evidence |
| --- | --- | --- |
| Startup and single instance | One operator process; startup has no BASE, rover or command authority | single_instance, fleet_frozen_contract |
| Compact dark UI | Segoe UI 12 px base, clear hierarchy, charcoal panels, restrained teal, visible focus/selection/disabled states | fleet_ui_resize, standalone/frozen checks |
| App and installer icon | Native rover/radio SVG; 512 px PNG; ICO 16/24/32/48/64/128/256 px; common asset used by header, executable and installer | cockpit_ui_update, frozen icon resolutions |
| Display disclosures | Connection details, coordinates, output settings and Help change visibility only | fleet_ui_resize, frozen optional-panels check |
| BASE USB selection and refresh | One shared native CDC owner; 115200; capability identification before subscriptions; incompatible BASE rejected | fleet, fleet_station, serial_setup |
| Per-rover Connect/Disconnect | Addressed sessions; 1–20 identities; no automatic reconnect, arm, start or resume | fleet_station, mission_session |
| Shared transport | Serialized bounded writes, partial/backlog failure, bounded input and per-rover buffers; cross-rover writes rejected | fleet, fleet_station |
| Roster Add/Remove | Lowest unused ID; separate saved roster/drafts; cannot remove last, busy or connected rover; failed draft save blocks removal | fleet_ui_resize |
| Rover selection | Changes displayed draft/map only; cancels route gestures and closes stale FC snapshot windows | route_editor, fc_readback, fleet_ui_resize |
| Fleet telemetry | Genuine addressed FC/GPS samples; mode, armed state, heading, speed and age; expired/invalid positions never become live | display_telemetry, clock_freshness, fleet_station, route_workflow |
| Moving rover map labels | Independent positions/trails and age-labelled stale markers; no interpolated fixes or synthetic heartbeat/GPS | fleet_station, fleet_frozen_contract |
| Map pan/zoom, Fit fleet, Follow | Correct geographic projection and dateline handling; manual view survives telemetry; cancelled gestures do not add points | map_drag, route_editor, fleet_ui_resize |
| Online maps and cache | Bounded asynchronous raster requests and tile cache; Online tiles choice now persists; failed preference write is reported | cockpit_ui_update, fleet_ui_resize |
| Offline map selection | Read-only raster MBTiles, decoded size checks, replacement validated before discarding working source; no map-derived GPS | offline_maps, fleet_ui_resize |
| Point/action editing | Go here/Waypoint, Hold on arrival 2–10 s, Set planned home, final Return home waypoint | route_editor, route_workflow |
| Planning home | Planning metadata; return is a waypoint at that home, not an FC RTL command or FC-home mutation | route_editor, route_recovery |
| Drag points and route lines | Move waypoint or insert on segment; selection/session/revision guards cancel stale gestures | map_drag, route_editor |
| Manual coordinates and event selector | Reviewed latitude/longitude and F1–F3 events; connected plans remain locked | mission_planning, route_editor |
| Route list operations | Reorder, Remove, Clear; bounded per-rover Undo/Redo (50 edits); selection/scroll retained | route_recovery, route_workflow |
| Native plan files | Editable .telerc.json includes home, actions, hold, outputs and speed; bounded atomic decoding; restoration never grants command authority | route_recovery, route_workflow |
| WPL import/export | WPL imports remain read-only; native/WPL format selection, extension handling, real popup→file→import coverage | route_workflow, fleet_ui_resize |
| Legacy draft recovery | Earlier zero unused hold durations recover without moving coordinates; active invalid hold values are rejected | route_workflow, route_recovery |
| Cruise speed | 0.1–3 m/s planning value; staged into reviewed onboard mission; never a direct live-drive slider | mission_planning, route_workflow |
| F1–F3 auxiliary outputs | Explicit cutoff acceptance, firmware mask, FC servo function/range and reviewed safe start/end checks; motor channels excluded | mission_planning, fleet_station |
| Link-loss policy | HOLD-on-loss default; Continue AUTO is explicit and requires matching read-back FC policy; no parameter writes | fleet_station, mission_planning |
| Upload & verify | Typed rover/digest confirmation; disarmed MANUAL/HOLD; complete upload/readback comparison; interrupted result is UNKNOWN | mission_protocol_peer, mission_planning, route_workflow |
| Normal Arm | Typed rover confirmation; verified exact plan, stationary fresh GPS/HOLD, full FC pre-arm requirements; no force-arm or retry | fleet_station, route_workflow |
| Mission start | Exact plan/digest/session; fresh armed state and GPS; verification consumed before one START attempt; ACK + fresh AUTO evidence | fleet_station, route_workflow |
| Disarm | Explicit confirmation; cancels work, requests HOLD, verifies stationary fresh GPS, sends normal disarm once | fleet_station, route_workflow |
| HOLD | Cancels queued/in-flight mission work; fresh FC confirmation required; does not disarm or prove accessory OFF | mission_session, fleet_station, fc_readback |
| Load from FC | Modeless read-only snapshot; empty/home-only handling; bounded retries/deadline; incomplete/changed/retired results rejected | fc_readback, fleet_frozen_contract |
| FC snapshot isolation | Draft unchanged; loading clears verification; no arm/start authority; closes on selection/disconnect/replacement upload | fc_readback |
| Watchdogs and loss recovery | 2 s GUI lease, fresh FC heartbeat requirement, route/USB errors cancel verification and queued work; deliberate recovery | mission_session, fleet_station, clock_freshness |
| Radio admission/fairness | Measured airtime/RTT admission, one foreground transaction, independent admitted background sessions; 20 IDs is not 20 guaranteed simultaneous vehicles | fleet, encrypted firmware graph |
| Protocol and firmware parity | Shared client/CLI transaction parity; all firmware paths unchanged; original firmware archive and image checksums verified | mission_protocol_peer, release_safety, fleet_release |
| Shutdown and persistence | Stop workers/heartbeats, close readers/USB, save drafts; no automatic ARM/DISARM/HOLD/START on shutdown | fleet_frozen_contract, fleet_ui_resize |
| Installer/portable/source delivery | Same installer identity; new version/resources; exact source provenance; sanitation and downloaded-asset hashes gate publication | build_windows_mission, stage_windows_mission, publish_fleet |

Test names in the last column refer to `tests/test_<name>.py`, except the native
firmware/graph checks under `firmware/fleet/tests` and the named build scripts.
These are software/simulation checks, not measured RF or stopping performance.

## Findings and corrections

1. The light proposal was coherent but did not meet the requested dark appearance.
   Updated shared theme, menus, dialogs, table headers, map chrome and indicators;
   retained compact sizes, disclosure structure and persistent command areas.
2. The generic power symbol did not communicate rover/radio technology. Replaced
   it with a native scalable connected-rover mark and seven Windows ICO sizes.
3. Numeric step arrows could be hard to see under a dark native palette. Bundled
   explicit up/down indicators and require their decode in the frozen verifier.
4. Online tiles changed the current map but did not save the choice. Save that
   display preference with a visible disk-error message. Regression confirms no
   transport acquisition or control side effect.
5. README mixed current fleet features with older manual-driving documentation.
   Added an explicit current/legacy boundary and updated rollback/firmware notes.

No command protocol, radio pairing or firmware correction was needed for this UI
scope. All existing authorization/freshness/verification gates were retained.

## Evidence and release gates

| Check | Result / boundary |
| --- | --- |
| Linux Python 3.12.14 / PySide6 6.11.2 full isolated regression | PASS — 52 modules, 480 checks |
| Actual native role guards under ASan/UBSan | PASS — BASE, ROVER_001, ROVER_003, NODE_1, NODE_200 |
| Actual encrypted three-rover/relay graph | PASS — 2 graph scenarios; simulated timing, not RF |
| Qt render inspection | Reviewed at 1500×860, 1366×768 and 1080×660, with expanded coordinates/outputs |
| Firmware difference | No firmware changes against pinned `6ba272867165eee31e21792ea259fce7225579f7` |
| Paired archive | Fleet 0.5.0rc1 SHA-256 `2c674f7278220a12287550532fa5a8b274455fc227c93e7042d9a42ed64a4751`; original eleven real board-build records/images reused |
| Windows regression/build/frozen executable | Mandatory current-source CI gate; final results ship in test-evidence.zip |
| Public-source/private-config boundaries | Mandatory existing source/firmware allowlist and recursive archive checks before staging/publication |
| Downloaded release assets | Mandatory SHA-256 and complete asset-set verification before the draft becomes public |
| Real Windows install/upgrade and display scaling | NOT TESTED manually; installer identity retained and installer is compiled in CI |
| Physical RF, motor stopping, RC takeover, auxiliary OFF and fleet capacity | NOT TESTED; candidate status retained |

Raster map colours are supplied by the selected online/offline tiles. The dark
UI preserves those data colours rather than inverting geographic labels.
The screenshot uses an offline planning draft at the app's public default view,
with cached OpenStreetMap tiles and zero connected/live GPS positions.

## Operational limits and rollback

- No integrated FPV, manual wheel/keyboard driving or raw CRSF module-bay control
  in this fleet executable. Use a compatible earlier manual release when needed.
- No collision avoidance, automatic fleet coordination or synchronized starts.
- Lost ACKs and unconfirmed HOLD/ARM/START/DISARM remain UNKNOWN; commands are not
  automatically replayed. Real FC loss policy and independent cutoff remain vital.
- Auxiliary outputs have no verified physical OFF feedback. HOLD does not prove
  their state. A read-only FC snapshot is not a live database or start permit.
- Operator confirmations are deliberate; native OS file pickers follow OS theming.
  Automated offscreen checks do not establish real display scaling or installed
  upgrade experience on every Windows machine.
- Public example firmware remains RF-OFF; private paired configurations/binaries
  are excluded. Existing correctly paired rc7 fleet firmware needs no reflash.
- Roll back the application to published rc7 with the same 0.5.0rc1/1.0.5 pairing.
  rc6 remains the mission-planning base. No draft/settings schema migration occurs.

The final release commit is recorded in SOURCE_COMMIT.txt, portable provenance,
RELEASE_STATUS.json and GitHub's release target. Publication is permitted only
when all automated candidate gates pass on that exact commit.

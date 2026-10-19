# PC TeleRC 0.1.5rc1 — LoRa mission planning

Development candidate. Physical BASE/ROVER, RF loss, Windows frozen package and
ArduRover SITL qualification must be recorded before stable promotion.

## Inputs and compatibility

- Desktop baseline: `172bcf9ba78c9710b4871110802979c4f992c1fa` (0.1.4rc1).
- Phone interaction reference: TeleRC `0b94da3`, mission-functions 0.8.86.
- Mission wire/client reference: TeleRC-LoRa-Mission-v0.1.0-dev.zip,
  SHA256 `204127c329b85bfd92011686294fb264b90546b5294718fd9a19e514fedf6fdb`. The UI integrates that exact addressed
  USB envelope and guarded client, adding cancellation, a UI lease and one-shot enforcement.
- Existing Wi-Fi/manual LoRa/ELRS/Backpack, wheel/keyboard, map/camera transports are
  retained. Mission execution uses a dedicated **Mission planning** window and the
  new **TeleRCMission_BASE/ROVER/NODE** generation, not the manual LoRa Link profile.
- One selected rover per session, IDs 1–20 matching `SYSID_THISMAV`. No simultaneous
  fleet dispatch, mesh discovery, dynamic rerouting or automatic mission resume.

## Planning and execution

1. Open **Mission planning**. Import a QGC WPL 110 file or enter reviewed latitude/
   longitude, Center map, and tap locations. Map clicks edit a plan only. Normal taps
   append numbered points; choose F1/F2/F3 ON or OFF for the next point. It returns
   to Waypoint after the tap. Drag to pan; use the wheel to zoom. Reorder/remove rows.
2. Assign each used function a dedicated output, OFF PWM and ON PWM. Unset, duplicate,
   M5–M8 outputs, invalid coordinates and unbalanced final ON events are rejected.
   Other actual motor/steering outputs are also prohibited: verify the physical wiring.
   New routes default to 0.5 m/s and accept 1–60 points, with 200 total FC rows.
3. Export WPL to retain the plan, including ordered PWM actions. Imports are shown
   exactly and remain read-only; Clear begins a new editable plan. Row 0 is an FC
   home placeholder, excluded from actionable verification; it is never displayed
   as a live GPS fix. Existing offline raster MBTiles/map preferences apply.
4. Select BASE COM port and rover ID. Connect mission BASE releases/closes the manual
   session first. While connected, the plan/profile/ID are locked. Manual ARM/control,
   reconnect and LoRa setup are guarded. No mission connection is opened automatically.
5. Review **Upload & verify** and type its rover/digest phrase. The client requires
   DISARMED MANUAL/HOLD, verifies FC GCS failsafe parameters, uploads, then compares
   every actionable row from full FC readback. Accepted ACK alone is insufficient.
6. Arm using the independent RC transmitter and ArduRover pre-arm checks. Review
   **Confirm START**, type its exact phrase, and keep the mission window open. The
   app repeats readback and failsafe/output checks, requires fresh real 3D GPS,
   stationary position reports and an ARMED MANUAL/HOLD heartbeat. START is transmitted
   once; accepted ACK plus subsequent ARMED AUTO heartbeat confirms it. No ARM,
   PARAM_SET, RC override or direct accessory command is sent through this path.
7. **Request HOLD** cancels pending work and purges pending mission jobs before a
   bounded HOLD request. Only a fresh FC HOLD heartbeat confirms the mode. HOLD
   does not disarm or prove the wheels or accessories are physically stopped.

## Loss, reconnection and auxiliary outputs

Default profile requires `FS_GCS_ENABLE=1`, `FS_ACTION=2`, GCS ID 255 and a verified
1–10 second timeout (`FS_GCS_TIMEOUT`, or legacy `FS_TIMEOUT`). The app does not
write these parameters. Test actual behavior and stop distance on your FC.

**Continue onboard AUTO after link loss** is an explicit connection-time choice
requiring `FS_GCS_ENABLE=2`, `FS_ACTION=2`. It permits FC AUTO continuation on GCS
loss; it is not a guarantee about every other failsafe. RC/fence/battery/EKF checks
remain independent. Onboard timing begins after the FC accepts the mission start;
RF delay still affects upload, START and HOLD delivery.

The worker stops if the GUI lease expires after 2 seconds, the USB link fails,
telemetry goes stale, a mission transaction fails, or the window closes. It stops sending heartbeats, discards
local pending output, clears readiness and never reconnects/replays START. The FC's
verified profile then governs GCS loss. An already transmitted radio command cannot
be recalled. Missing START ACK, failed upload/readback, stale link or unconfirmed
HOLD is **UNKNOWN**, not stopped. Use independent RC takeover and a physical cutoff.
A radio outage can prevent HOLD entirely. Wait at least 5 seconds after closing
before selecting/reconnecting another rover; this is not proof the previous rover stopped.

F events use **onboard AUTO DO_SET_SERVO mission semantics**, which differ from the
phone's stationary Guided action/feedback sequence. This firmware does not return
SERVO_OUTPUT_RAW or provide direct OFF commands. The editor adds initial/final OFF
rows and requires each used function's final event OFF, but HOLD/abort/link loss
can skip those rows and cannot guarantee OFF. Auxiliary execution is locked until
the operator explicitly acknowledges the dedicated output mapping, firmware servo
permission mask, OFF PWM and independent accessory cutoff. Before upload and START,
read-only checks require `SERVOx_FUNCTION=0` and MIN/MAX containing all PWM values.
Imported servo rows must begin/end at the same reviewed safe PWM. Use only safe
bench loads until independent OFF/end-state behavior is verified. No phone-style
stationary action or physical-output feedback guarantee is claimed.

## Firmware and security

Use the complete original `TeleRC-LoRa-Mission-v0.1.0-dev.zip` package for BASE,
ROVER and NODE provisioning and target build instructions. Every participating
board must come from the same generated set. Random per-rover keys are preferred;
the optional long passphrase is entered into its offline provisioning tool. No
password or key is entered/saved by PC TeleRC. The app does not re-provision boards
or weaken the encrypted radio protocol. Legacy manual pairing remains separate.
The USB operator is locally trusted; radio authentication does not protect a
compromised PC, physical flash extraction or RF jamming.

References: https://mavlink.io/en/services/mission.html and
https://ardupilot.org/rover/docs/rover-failsafes.html.

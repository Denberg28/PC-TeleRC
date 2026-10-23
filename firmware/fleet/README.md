# TeleRC LoRa Fleet 1.1.0-dev1

Development successor to the v1.0.1 reconnect fix, for addressed ArduRover missions
and fleet observation. The new **TF2** radio protocol discovers relay paths; it
has no compiled fleet list, relay count, or ordered node index. BASE, ROVER and
NODE are LoRa only. LilyGO T3-S3 ESP32-S3 / SX1262, 915 MHz default.

**Adding a board does not require rebuilding the other boards.** Generate private
fleet credentials once. Copy an existing same-role private sketch into a new
parent directory, keep its Arduino folder/.ino names together, and edit only:

```cpp
#define ROVER_ID 3  // in the rover .ino, valid 1..20
```

or:

```cpp
#define NODE_ID 7   // in the node .ino, valid 1..200
```

Upload to the new board. IDs must be unique within their role. A rover's FC must
also have `SYSID_THISMAV` equal to its `ROVER_ID`, component 1. Changing this FC
parameter is a local commissioning step; these tools never write FC parameters.
Node IDs are independent of physical order: node 7 can be nearer BASE than node 2.
Adding rover 3 does not require editing BASE, rover 1, or any relay.

This is a **development candidate**, not a flight/vehicle-qualified release.
It is a new protocol: upgrade every participating BASE/ROVER/NODE once for this
fleet. It does not interoperate with manual v1.0.1/v4 or Mission 0.2.0rc1/TM1.
Original PC TeleRC/manual/Mission releases remain available unchanged. The current
Windows Mission panel expects TM2 and does not support this TFM1 development BASE;
use the matching gateway and CLI in this package. There is no Wi-Fi or wheel/RC
control path in this mission firmware.

## First fleet: make private sketches once

Install Python 3.12+, then:

```powershell
python -m pip install -r requirements.txt
python tools/network.py init --out ../TeleRC-private
```

This creates BASE, ROVER_001, NODE_001 and NODE_002 plus `FleetCredentials.json`.
Compile/upload these private sketches. Public `sketches/` are keyless examples
and deliberately keep RF OFF. Back up the private folder. Do not run `init` again
to add boards: it creates a different network, even if the fleet number matches.

A convenient alternative to copying/editing is:

```powershell
python tools/network.py add --network ../TeleRC-private/FleetCredentials.json --role rover --id 3 --out ../TeleRC-private/TeleRCFleet_ROVER_003
python tools/network.py add --network ../TeleRC-private/FleetCredentials.json --role node --id 7 --out ../TeleRC-private/TeleRCFleet_NODE_007
```

`add` reuses the exact RF settings and keys; it does not touch any existing file.
RF settings and fleet keys are one-time network settings, not per-board ID knobs.
Changing those settings later requires updating the participating fleet.
Default RF: 915 MHz, 2 dBm, SF7, BW250, CR4:5, sync 0x12. Choose permitted local
frequency/power with matching antennas during initial provisioning.

## Compile and wire

Use ESP32 Arduino **3.3.2** and RadioLib **7.2.1**. Arduino board: LilyGO T3-S3,
SX1262 revision, 4 MB flash, PSRAM disabled, hardware CDC/JTAG, USB CDC on boot.
Install those exact dependencies; then Arduino IDE upload or:

```powershell
python tools/compile_profiles.py ../TeleRC-private
```

The helper compiles only; it never flashes a board. Flash the sketch for that role
using Arduino IDE. No provisioned binaries or credentials are distributed here.

| Role | Wiring |
|---|---|
| BASE | USB data cable to PC |
| ROVER GPIO43 TX | FC R3 / RX |
| ROVER GPIO44 RX | FC T3 / TX |
| ROVER GND | FC GND |
| NODE | Stable regulated power; antenna; no FC UART |

UART: 115200, 8N1, 3.3 V. FC: SERIAL3_PROTOCOL=2, SERIAL3_BAUD=115,
SYSID_THISMAV=ROVER_ID. Host GCS is sys255/comp190. Retain independent RC control.

## Auto connection and recovery

BASE issues authenticated probes even when a rover has no telemetry yet. Relays
append their own IDs to a bounded discovery path. The first accepted rover reply
returns along that exact path; each subsequent probe discovers a route anew.
There is no node-order or relay-count setting. Direct communication uses zero
relays; relays are used only when their forwarded probe reaches the rover first.
This is best-effort first-response discovery, not an optimized mesh route metric.

Nodes send periodic authenticated HELLOs even with no rover powered. A matching
BASE ACK changes OLED `SEARCH BASE` to `READY / STANDBY`; `FORWARDING` indicates
recent traffic. READY proves a recent base exchange, not FC readiness or mission
control. HELLOs are jittered and give way to queued mission packets. Nodes keep
listening and retry without BOOT gestures. An unused relay may remain in standby
when a direct route wins. OLED sleep after 30 s never pauses the radio.

CAD/backoff reduces collisions. RX is rearmed after idle, missed TX edges are
checked against the actual TX_DONE flag, and radio errors retry initialization
at 2 s intervals. Recovery discards queued commands/challenges and invalidates
rover upload/start authorization on RF faults. Never automatically retry START,
arm, or resume a host command after reconnect. Re-upload disarmed when authorization
has been invalidated. Actual FC AUTO continuation is governed by its configured
onboard loss policy, not by a synthesized heartbeat.

## One mission writer, multiple autonomous rovers

Start the matching BASE gateway for one addressed rover:

```powershell
python tools/fleet_gateway.py --port COM9 --rover 3
```

In a second terminal, upload a QGC WPL110 mission (row 0 is home metadata):

```powershell
python tools/mission_client.py --rover 3 upload route3.waypoints
python tools/mission_client.py --rover 3 start route3.waypoints
```

The client requires an explicit UPLOAD confirmation, DISARMED MANUAL/HOLD, accepted
upload, full actionable readback, fresh FC policy checks, independent RC arming,
and a separate `START <rover> <digest-prefix>` confirmation. It rechecks the plan
immediately before one-shot START and requires START ACK plus ARMED AUTO heartbeat.
A missing ACK is UNKNOWN, not permission to retry. It never arms, overrides RC,
writes parameters, or sends arbitrary actuator commands.

This development RF profile requires a verified GCS timeout of **10 seconds**
(`FS_GCS_TIMEOUT`, or supported `FS_TIMEOUT` fallback), FS_ACTION=2, GCS ID255,
and FS_GCS_ENABLE=1 for the default HOLD-on-loss profile. Configure and test the
policy locally; the client only reads it. Longer discovered routes may still
miss timing limits: this package does not increase token/FC/host watchdogs to
conceal loss. Embedded token/host/FC freshness limits remain 2400/1500/3500 ms.

To commission serial deployment of autonomous missions, explicitly configure and
verify the FC's AUTO-continuation policy (FS_GCS_ENABLE=2), then deliberately use:

```powershell
python tools/mission_client.py --rover 3 start route3.waypoints --continue-on-loss --detach
```

Detach is allowed only with the explicit continuation option and after confirmed
START. It closes the writer without requesting HOLD. Stop the gateway, wait at
least 5 s, then open it for the next rover. The prior vehicle continues under its
own verified policy; the PC is no longer maintaining its GCS heartbeat. Without
`--detach`, the client monitors that rover; Ctrl+C requests HOLD if START was
attempted. HOLD delivery and physical stopping remain unconfirmed if the link is
lost. An explicit addressed HOLD is also available:

```powershell
python tools/mission_client.py --rover 3 hold
```

This is **serialized mission deployment**, not simultaneous multi-rover command
control. BASE holds one active writer for 5 s after its last host traffic and
rejects another writer during that period. USB disconnect, RF fault, queue expiry
or source loss cannot replay saved START work.

## Read-only fleet monitor

Stop the writer gateway, then:

```powershell
python tools/fleet_gateway.py --port COM9 --monitor --watch 1-3,7
```

The monitor sends only local INFO/WATCH configuration, never MAVLink commands or
GCS heartbeats. It displays per-rover last data age, actual FC heartbeat age, armed
state and mode, plus route/node messages. `--watch` is a runtime PC list, so adding
an ID changes no firmware. Only one program can own BASE's COM port at a time.
The writer focuses polling on its rover; background fleet observation resumes
after it expires. Full fleet monitoring and an active writer are not simultaneous
in this release. Ages are receive-time observations; they do not prove stopping.

## Bounds, credentials, and qualification

- Rover IDs 1..20; node IDs 1..200; routes 0..4 relays. These are address/path
  limits, not demonstrated simultaneous RF capacity. Many relays increase flood
  traffic; begin with a small network and measure airtime, latency, interference
  and local duty-cycle limits. No guaranteed range, throughput, or failover time.
- The base scans all 20 IDs by default. Each absent rover can cost about 2.4 s;
  `--watch` narrows scanning. A full absent-ID sweep can exceed 48 s. Monitoring
  is best effort and is not a real-time fleet safety supervisor.
- One private ENDPOINT_ROOT derives rover-specific AES-256-GCM keys from fleet/ID.
  BASE and all rovers share this root; compromising one endpoint compromises this
  trust domain. There is no per-rover key revocation without reprovisioning.
  Nodes receive only ROUTE_KEY and cannot decrypt/forge mission endpoint payloads.
  All relays are trusted routing participants; they can deny/delay traffic.
- Hardware MAC fingerprints detect observed duplicate IDs; conflicts block
  commands on the affected identity/route. This is best-effort collision detection,
  not identity attestation: radio collisions or unseen duplicates can hide a
  device. Assign unique IDs before power-up. Resolve duplicates with all affected
  devices silent for 90 s, or restart BASE after correcting the IDs.
- Random 96-bit nonces, routing HMAC, endpoint AEAD, bounded paths, nonce cache,
  expiring one-use challenges and strict FC/host addressing reject stale/foreign
  commands. Discovery paths are appendable by trusted relays; chosen DATA/RESPONSE
  paths are endpoint authenticated. No reliable-delivery promise is made.
- Auxiliary outputs are disabled by default. Optional outputs 9/10/11 require
  one-time explicit `--servo-mask` provisioning and independent physical cutoff.
  The client re-reads SERVOx_FUNCTION=0 and 1000..2000 MIN/MAX limits before upload
  and start, and rejects mission PWM outside those limits.
  HOLD/link loss/FC reset cannot guarantee accessory OFF. M5..M8 stay denied.
- Host tests and actual ESP32 compilation are recorded in `validation/REPORT.md`.
  No radios, vehicles, Windows frozen app, ArduRover SITL/HIL, real failsafe timing
  or concurrent fleet capacity were qualified. Keep this candidate separate from
  stable field firmware until that work is complete.

# TeleRC Scalable LoRa 0.4.0rc1 — incremental nodes candidate

A new matched BASE / ROVER / NODE generation adds numbered boards from a saved
private network project. After a one-time migration to this TU2 generation,
adding a matching NODE3, NODE4 or another supported ID does not require changing
or reflashing deployed boards. Keep v1.0.1 stable and unified 0.3.0rc1 for rollback.
This is a development candidate, with physical RF/vehicle qualification pending.

| Capability | Current bound |
| --- | --- |
| Node identities | 1–200, unique within a network |
| Active route | Direct or at most **two relays**, selected automatically |
| Mission rover addressing | IDs 1–20, one selected at a time |
| Wheel/keyboard driving | Rover ID 1, unchanged PC TeleRC v1.0.1 interfaces |
| Base radios/controllers | One active BASE per private network |

Node number is an identity, not chain position: BASE → NODE3 → NODE200 → ROVER
is a valid route. BASE → NODE1 → NODE2 → NODE3 → ROVER exceeds the two-relay cap
and will not connect. More nodes provide alternate coverage/routes; 200 addresses
are not a claim of 200 simultaneously active radios or any measured throughput.
Long serial chains and simultaneous fleet monitoring are outside this candidate.

## Create the network once; add boards later

Install Python 3.12. Extract this package and run from its root. These examples use
a private folder outside the package/source repository. Public sketches/binaries
are keyless **RF OFF**, for review only.

```powershell
py -3.12 tools/provision.py init --project C:/TeleRC-private/NETWORK.private.json
py -3.12 tools/provision.py add --project C:/TeleRC-private/NETWORK.private.json --role BASE --out C:/TeleRC-private/TeleRCScale_BASE
py -3.12 tools/provision.py add --project C:/TeleRC-private/NETWORK.private.json --role ROVER --id 1 --out C:/TeleRC-private/TeleRCScale_ROVER_001
py -3.12 tools/provision.py add --project C:/TeleRC-private/NETWORK.private.json --role NODE --id 3 --out C:/TeleRC-private/TeleRCScale_NODE_3
```

Later, use the **same saved project** with `add --role NODE --id 4`, changing the
output to `C:/TeleRC-private/TeleRCScale_NODE_4`. Compile/upload just the new board.
MAKE-MATCHING-SKETCHES.cmd provides the same incremental flow interactively.
Do not edit only the number in another board's sketch. The tool rejects reused
IDs and occupied output folders. For a replacement board, reuse that ID's saved
sketch, retire the original and never power both with the same identity.

The private project contains the master secret and issued-ID inventory. Back up
it and generated sketches offline; protect their Windows folder permissions.
BASE includes all 20 derived rover keys at creation, so adding rover 2–20 later
does not alter BASE. ROVER contains only its endpoint key; NODE contains only the
routing key. A compromised relay cannot decrypt or create endpoint commands;
shared routing credentials cannot guarantee availability against a malicious relay.
Revocation/key rotation requires a deliberate matched-network migration.

Random private keys are preferred. Optional `init --password` prompts securely;
a 16+ character passphrase derives the project secret with a saved random salt.
Separate `init` runs, even with the same password, create separate networks.
Do not regenerate a project when changing workflow or adding a board.

## Radio discovery and command admission

TU2 replaces the two-bit mask with authenticated ordered node IDs. Discovery is
read-only and rate limited to one query per five seconds; each node forwards a
query at most once, with nonce-based contention delay. Routes reject repeated IDs,
excess hops and malformed packets. A heard return cancels a pending redundant
query. Routine telemetry/commands follow only the selected source route, rather
than flooding every node or enumerating exponentially many possible paths.

BASE needs three consecutive source-route round trips before forwarding host
commands. A route change, expiry or repeated loss discards queued work. Health
queries release manual ownership and invalidate mission-start/upload verification.
Only fresh commands can follow requalification. Mission re-upload/readback and
explicit Start are required after a recovery; there is no automatic mission restart.
An already-running onboard AUTO mission follows the FC's configured loss policy;
link recovery or closing the PC session does not guarantee it stopped.

Manual admission additionally requires a rolling measured query/reply time plus
worst-case command airtime and guard to fit a 350 ms budget. The rover 500 ms
per-axis stop/release watchdog and PC 500 ms remote-status check remain unchanged.
A slow route blocks manual commands; connection alone is not driving permission.
This estimate is conservative software admission, not a physical stopping guarantee.

## Compatibility, installation and workflow

Install the whole TU2 generation once on all participating boards. It rejects TU1
unified 0.3.0rc1, manual v1.0.1, TM2 and Fleet TF2 radio packets. The PC app stays
v1.0.1: main window LORA for manual driving; Mission window for planning/upload/
readback/Start. INFO is read-only, and the Mission reply retains TM2/fw=0.2.0 USB
framing with `unified=0.4.0`; actual board firmware is 0.4.0rc1. `relays=2` is the
fixed maximum route depth, not the number of installed nodes.

Use LilyGO T3-S3 SX1262, ESP32 Arduino 3.3.2, RadioLib 7.2.1, hardware USB CDC/JTAG
and PSRAM disabled. FC UART is TX43/RX44 at 115200; cross TX/RX and share ground.
FC SYSID_THISMAV must equal ROVER_ID. Default radio is 915 MHz, 2 dBm, SF7/BW500/
CR4:5. All boards inherit the same radio settings from the saved project.
`tools/compile_profiles.py <private-parent-folder>` compiles generated boards with
Arduino CLI; upload each matching role using Arduino IDE or your normal uploader.

Manual → mission: stop, disable control, disarm, disconnect, wait two seconds,
then open Mission. Upload/read back disarmed in MANUAL/HOLD, arm through independent
RC and explicitly confirm Start. Mission → manual: command HOLD or use independent
RC, verify stationary, close Mission, wait two seconds, select MANUAL and explicitly
enable at neutral. Manual commands are rejected in AUTO/HOLD. Never auto-arm.

## Evidence and remaining qualification

Focused tests exercise the actual role headers, encryption and validators; graph
packet-delivery tests cover NODE3/NODE200, return paths, duplicates, route loss,
later-node recovery and disconnected-network rate limits. Enrollment tests cover
all 200 node IDs and 20 rover IDs while preserving deployed BASE/ROVER files.
The unchanged PC serial drivers are tested against a native BASE.

Graph tests do not model collisions, hidden terminals, RF range, duty-cycle limits,
power disturbance or real channel capacity. No measured fleet-size claim is made.
Ten pinned target builds cover public RF-OFF and private test BASE/ROVER/NODE1/
NODE3/NODE200 profiles; private binaries/projects are excluded from distribution.
Complete HARDWARE_TEST.md before vehicle use. Stable v1.0.1 is unchanged.

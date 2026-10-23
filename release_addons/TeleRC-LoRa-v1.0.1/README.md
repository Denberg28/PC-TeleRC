# TeleRC LoRa v1.0.1 — node auto-join/rejoin fix

[Download the fixed manual firmware](https://github.com/Denberg28/PC-TeleRC/releases/download/v1.0.0/TeleRC-LoRa-v1.0.1-node-fix-firmware.zip)

Supersedes the manual TeleRC-LoRa-v1.0.0 companion. In v1.0.0 a healthy direct
base/rover path stayed locked and no further relay paths were probed; unused
nodes remained labelled AUTO CONNECTING. This was a confirmed software discovery
gap, not a diagnosis of a particular board's RF/power hardware.

v1.0.1 adds authenticated, empty round-trip probes for Node 1, Node 2 and the
two-node chain. The rover checks one candidate about every three seconds while
PC Control is OFF. These probes neither carry RC/ARM commands nor consume them
from the base mailbox, and they keep the chosen driving route unchanged.

**Update BASE, ROVER, NODE1 and NODE2 together.** This set uses radio protocol
v4; v1.0.0 uses v3 and cannot join it. Select LoRa on the rover. Leave **PC
Control OFF for 10–12 seconds** on a clear link; reachable paths should produce
`N1:OK N2:OK` on the rover and NODE READY on each verified relay.

| Node status | Meaning |
| --- | --- |
| NODE READY | Recent matching relay probe/reply confirmed the path |
| NODE FORWARDING | Recent real control/telemetry exchange used this node |
| NODE STANDBY | Authenticated network is heard, but no recent round-trip is confirmed |
| WAITING NETWORK | No recent matching authenticated traffic |

Idle probes pause while PC Control owns RC, including centered sticks. A direct
path remains preferred while it works. STANDBY during a healthy direct-control
session is expected; turn PC Control OFF to refresh standby checks. Real traffic
refreshes nodes actually in use. Nodes auto-rejoin on a fresh exchange after
reboot; missed DIO1 edges and a quiet/error receiver have recovery paths.

All four real LilyGO T3-S3 SX1262 targets compiled with Espressif 3.3.2 and
RadioLib 7.2.1. **612 host checks passed**, including 161 checks compiling the
actual BASE, ROVER, NODE1 and NODE2 role instances together for late join,
reboot/rejoin, direct-path failover, probe isolation and receiver recovery.
Hardware RF, app interoperability and physical failsafe tests remain pending.

Defaults remain 915 MHz / public test password `telerc123` / 2 dBm. Factory
images overwrite the full 4 MB flash including NVS; read the included flashing
guide. This is manual single-rover RC/arm/disarm firmware. It does not add mission
upload/start, waypoint/servo commands or fleet support. The separate mission
firmware, Windows app and master firmware catalog are unchanged.

ZIP SHA-256: `729cbdb0d1d7afd53c57c67c986ec462d841175c0815ec74198b2193ad779ec6`.

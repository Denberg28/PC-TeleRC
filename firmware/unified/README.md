# TeleRC Unified LoRa 0.3.0rc1 — manual and mission candidate

One matched BASE / ROVER / NODE firmware generation supports both PC TeleRC
wheel/keyboard driving and autonomous ArduRover missions. Changing workflow does
not require reflashing boards. This is a new development candidate; PC TeleRC
v1.0.1 and its stable firmware downloads are retained for rollback.

| Operation | PC TeleRC v1.0.1 entry |
| --- | --- |
| Manual driving | Main window → LORA → Connect → Enable PC Control at neutral |
| Mission planning/upload/start | Mission window, independent RC arming and explicit Start |

The native BASE accepts both existing PC USB interfaces. Host framing is selected
by the appropriate INFO handshake; INFO does not arm, enable or start anything.
The Mission capability reply retains TM2/fw=0.2.0 wire compatibility and adds
`unified=0.3.0`. The actual firmware version is 0.3.0rc1, not mission 0.2.0rc1.
All boards use the new TU radio protocol and must come from the same generation.
Do not mix them with manual v1.0.1, TM2 mission or Fleet TF2 boards.

## One-time matching setup

Public example binaries/sketches are keyless with **RF OFF**. Generate the private
matching set once, outside the public source folder, then compile/upload it:

```powershell
py -3.12 tools/provision.py --out C:/TeleRC-private-unified --rovers 1 --relays 2
```

Alternatively run MAKE-MATCHING-SKETCHES.cmd. Random private keys are preferred;
`--password` securely prompts for a private passphrase of at least 16 characters.
`telerc123` is not a default credential for this encrypted candidate. BASE has the
required endpoint keys; each ROVER has its own; NODEs contain only the route key.
Keep generated Config.h files private and back them up. Do not generate a different
set when changing between manual and mission operation.

The first compatibility target is **manual rover ID 1**. Mission IDs 1–20 retain
the existing addressed-client behavior when included in the generated key table;
this is not simultaneous multi-rover manual driving or fleet monitoring.

Use ESP32 Arduino 3.3.2, RadioLib 7.2.1 and LilyGO T3-S3 SX1262, hardware USB
CDC/JTAG enabled, PSRAM disabled. Firmware uses FC UART TX43/RX44, 115200 baud;
cross these to FC RX/TX and connect ground. FC SYSID_THISMAV must match ROVER_ID.
Default radio: 915 MHz, 2 dBm, SF7/BW500/CR4:5. This candidate is LoRa-only.
No flashing command or provisioning tool arms the rover or writes FC parameters.

## Workflow changes

Manual → mission: stop, disable PC Control, disarm, disconnect the manual link,
allow two seconds for host/override leases to expire, then open Mission. Upload
while disarmed and MANUAL/HOLD, verify readback, arm using independent RC, then
explicitly confirm Start. A manual acquisition invalidates previous mission-start
authorization; re-upload/readback is required before a subsequent Start.

Mission → manual: use HOLD or the independent RC mode switch, verify the rover is
stationary, close/disconnect Mission, wait two seconds, select MANUAL on the FC,
then connect LORA on the main screen and explicitly enable at neutral. Manual
steering commands are rejected in AUTO/HOLD. Closing a mission session does not
guarantee that an already-running onboard mission stopped; the FC's actual mode
and configured loss policy remain authoritative.

## Automatic radio connection and safety

With matching keys, power boards in any order. BASE searches direct, NODE1,
NODE2, then NODE1→NODE2 routes, within the configured maximum of two relays. Three
missed exchanges resume discovery. Idle health probes do not consume command
mailboxes or change the selected working route. NODE READY means a recent
authenticated return packet was queued for forwarding; standby is normal on unused paths.
RF errors discard queued work and retry initialization after two seconds.
Reconnect never automatically arms, starts a mission or restores driving commands.

Manual RC retains neutral acquisition, separate steering/throttle age and a
500 ms rover-side stop/release watchdog. The existing PC 500 ms remote-status
check remains unchanged. Latency/interference on a relay path can therefore stop
manual control; no range, delay or uninterrupted-control guarantee is made.
Mission validation, encrypted one-use tokens, explicit ARM/Start boundaries,
non-motor auxiliary opt-in and lost-ACK UNKNOWN behavior are retained. No mission
command is admitted through the manual gate; mission traffic cannot acquire RC.

## Qualification

Host/sanitizer checks cover actual role code, manual/mission arbitration, sparse
RC ages, stop/release, stale/consumed/cross-profile tokens, UART/RF faults and
the unchanged PC serial-driver handshakes. They are not physical RF tests.
Actual-board compile records identify the tested source and exact profiles.
Public binary images remain RF OFF; private test images are not distributed.

Physical flashing, control latency with relays, mode-switch/takeover behavior,
stopping distance, EMI/power loss, mission upload/start on real FC hardware and
accessory OFF behavior remain unqualified. Complete HARDWARE_TEST.md with wheels
restrained and retain an independent local cutoff before ground operation.

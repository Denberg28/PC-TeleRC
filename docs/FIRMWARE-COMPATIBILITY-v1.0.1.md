# PC TeleRC v1.0.1 — choose a matching firmware set

| Use | Required BASE / ROVER / NODE set | App entry |
| --- | --- | --- |
| Manual driving over LoRa | TeleRC LoRa **1.0.1**, radio protocol v4, all four matching roles | Select LORA, Connect, then enable PC Control at neutral |
| Autonomous waypoints and F actions | LoRa Mission **0.2.0rc1 TM2**, privately generated matching BASE/ROVER/NODE set | Open Mission |
| Manual WiFi | Existing compatible MAVLink WiFi bridge | Select WIFI |

Manual v1.0.1 does not implement mission upload or Start. TM2 does not implement
the main-window manual LoRa protocol. A BASE from one set cannot operate with a
ROVER or NODE from the other. Keep each set in its own folder.

## Manual BASE, ROVER and nodes

The included `TeleRC-LoRa-v1.0.1-node-fix-firmware.zip` contains the unchanged
reviewed sketches, factory images and original validation. Flash BASE, ROVER,
NODE1 and NODE2 together; v1.0.0/v3 boards cannot join this v4 set. Defaults are
915 MHz, public test password `telerc123`, 2 dBm. Change the matching sketch
settings before deployment as needed. Select LoRa on the ROVER. Leave PC Control
OFF for 10–12 seconds to check relay paths. Healthy direct driving takes priority;
node standby is expected during a direct session.

The new `PC-TeleRC-v1.0.1-firmware.zip` provides freshly compiled, separate
application/bootloader/partition images for all manual roles and the four TM2
public examples. Use its manifest's exact board profile and offsets. These
separate images preserve NVS when flashed at the listed offsets without erase.
The older manual ZIP's **factory images erase the entire 4 MB flash including
NVS**; use them only for intentional fresh installation after backup.

## Mission planning

The Mission-firmware folder includes the unchanged 0.2.0rc1 public sketches and
the matching-set generator. Public mission example binaries have **RF OFF**.
Run MAKE-MATCHING-SKETCHES.cmd to generate private keys and a matching set outside
the source folder, then compile and flash the generated roles. The FC's MAVLink
system ID must match the selected rover ID. Never publish generated keys.

Plan → connect mission BASE → upload disarmed → verify full readback → arm from
the RC handset → confirm Start. Disconnect/reconnect never starts a mission.
Read MISSION-PLANNING.md and the mission firmware HARDWARE_TEST.md.

The stable desktop release includes mission planning; the radio mission firmware
retains its **0.2.0rc1** designation. Twenty rover IDs support separate saved plans;
only one addressed mission session is active. Simultaneous fleet monitoring and
dynamic mesh routing are not provided.

## Qualification and rollback

Software tests and actual-board compilation do not measure RF range, electrical
reliability, stopping distance, accessory OFF behavior or RC takeover. Physical
qualification remains unrecorded. Complete restrained commissioning and retain
an independent local cutoff. WiFi MAVLink commands are not end-to-end authenticated.
Back up FC parameters, app settings and private provisioning; preserve NVS.
Keep the previous app and matching firmware set for rollback.

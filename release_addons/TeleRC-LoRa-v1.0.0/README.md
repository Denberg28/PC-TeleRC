# TeleRC LoRa v1.0.0 — PC TeleRC manual-control companion

[Download the firmware ZIP](https://github.com/Denberg28/PC-TeleRC/releases/download/v1.0.0/TeleRC-LoRa-v1.0.0-firmware.zip)

Added to the PC TeleRC v1.0.0 prerelease as a separate manual-control firmware
option. This is the exact reviewed package supplied by the maintainer, with
SHA-256 `f6e43280ce6374a2ca216ad70cee77aff66e359c6ba02cc51597d7061d9ad880`.

| Board | Transport |
| --- | --- |
| ROVER | Select Wi-Fi or LoRa through the saved BOOT menu |
| BASE | LoRa only; native USB to the PC |
| NODE1 | LoRa only; radio ID 3 |
| NODE2 | LoRa only; radio ID 4 |

The rover discovers direct, Node 1, Node 2, or ordered Node 1 + Node 2 paths.
Includes automatic radio recovery, neutral/release fixes, four source sketches,
four compiled factory images, flashing instructions and validation evidence.
Defaults are 915 MHz / public test password `telerc123` / 2 dBm.

**This is single-rover RC/arm/disarm firmware. It cannot upload/start missions,
execute waypoint/servo commands or operate a fleet.** Use the release's separate
TeleRC-LoRa-Mission-v0.2.0rc1 package and its private provisioning instructions
for the mission development line. Neither radio family interoperates with the
other, and the new manual radio protocol v3 does not interoperate with the old
v0.1.3 manual radio protocol v2. Flash BASE, ROVER and any NODEs together from
one matching package.

All four LilyGO T3-S3 SX1262 targets compiled with Espressif 3.3.2 / RadioLib
7.2.1; 318 host checks passed. Physical radio, app, power and motor failsafe
validation remain pending. Factory images overwrite all 4 MB flash including
NVS; use source upload without erase when retaining the saved transport.

This companion does not replace the mission firmware, alter the Windows
application or promote the maintained 11-profile master firmware catalog.
The current firmware catalog remains at `firmware/latest`; this package is
kept separately under `release_addons` so its distinct radio protocol cannot
silently enter another firmware family.

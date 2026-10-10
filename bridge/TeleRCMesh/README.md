# TeleRC Mesh 0.1.0 — LilyGO T3-S3 SX1262

A configurable connection sketch for PC TeleRC, with gateway, relay and rover roles. The same firmware runs on every participating T3-S3 SX1262 V1.2/V1.3 board. This is a **bench-test candidate**, not a field-validated release. It does not speak Meshtastic, LoRaWAN, or ELRS.

## Quick start

1. Flash `TeleRCMesh.ino` (keep both adjacent `.h` files in its folder) to each board. A blank board starts with its radio OFF.
2. Join **TeleRC-Setup-1**, Wi-Fi password **telerc123**.
3. Open **http://192.168.4.1**. Setup username **admin**, password **telerc**.
4. Fill in the profile, paste the same random 64-character mesh key on all boards, then Save and restart. Generate a key locally with `python -c "import secrets; print(secrets.token_hex(32))"`. Do not send or commit this private key.
5. Configure the gateway as node 1, rover as node 2, and relays as nodes 3, 4, etc. Use the same network ID, gateway/rover IDs, maximum radio legs, frequency and key on every board. The maximum allowed path is three radio legs (two relay boards).
6. To change a configured board later, hold **BOOT**, press/release **RST**, then release BOOT after startup. It enters setup with RF OFF. Never enter setup while the rover is moving.
7. Join the operational gateway AP **TeleRC-Mesh-1** using **telerc123**. Configure PC TeleRC for its normal **TeleRC UDP** mode, target **192.168.4.1**, local port **14550**, target port **14550**, steering **CH1**, bidirectional drive **CH2**. Connect with controls centered and control disabled; then explicitly enable control and ARM as appropriate.

`telerc` is six characters and cannot be used as a WPA2 Wi-Fi passphrase; the secured AP therefore uses `telerc123`. The setup login uses the exact requested `telerc`. Both passwords are editable in setup; blank password fields retain their stored values. The gateway accepts one local UDP peer on port 14550, with a five-second idle expiry. It broadcasts real vehicle telemetry before a peer is established, allowing PC TeleRC to discover the gateway. Its packet source port stays 14550.

## Profiles

| Board | Role | Node ID | Gateway ID | Rover ID | Radio legs | UART backend |
|---|---|---:|---:|---:|---:|---|
| Near PC | Gateway | 1 | 1 | 2 | 3 | Ignored |
| First relay | Relay node | 3 | 1 | 2 | 3 | Ignored |
| Second relay | Relay node | 4 | 1 | 2 | 3 | Ignored |
| On rover | Rover | 2 | 1 | 2 | 3 | ArduRover raw MAVLink, or TeleRC motor framed UART |

Select one radio leg for a direct pair, two for one relay, three for up to two relays. All participants must use the same setting. Extra relays can provide alternative coverage, but every extra forwarding node increases airtime and contention; begin with a single relay. There is one gateway and one rover per network. Multi-rover selection is not implemented.

The mesh uses bounded authenticated flooding: relays forward each poll/response once, decrease its hop budget, and keep a duplicate cache. There is no manually assigned route; a shorter direct path can still work when available. Neighbors heard within ten seconds, RSSI, RX/TX/reject/duplicate/drop counts are printed to USB Serial Monitor at 115200. These are heard-neighbor observations, not a guaranteed end-to-end route or measured distance. Relay boards need power and antenna only; no UART wiring or PC connection in operation.

RF is disabled until a valid installation-specific frequency and nonzero private key are saved. Frequency is entered in **kHz**, with no on-air default. Use the correct 433 or 868/915 MHz front-end and antenna, and a locally permitted operating frequency/power/bandwidth. The hardware bounds in the form are capability checks, not regulatory authorization. Fixed bench profile: **SF7, BW500 kHz, CR4:5, preamble 8, sync 0x12, TCXO 1.6 V**; power range 2–17 dBm, initial value 2 dBm. Attach the matching antenna before configuring/transmitting. Higher spreading factors are intentionally unavailable because their airtime would require a different control timing design.

## Rover wiring — choose exactly one backend

### ArduRover raw MAVLink (default, preserves the FC PWM motor path)

| LilyGO rover | Flight controller |
|---|---|
| GPIO43 TX | R3 RX |
| GPIO44 RX | T3 TX |
| GND | GND |

UART is **115200 baud, 3.3 V logic**, bidirectional. For the existing SpeedyBee F405 setup, use `SERIAL3_PROTOCOL=2`, `SERIAL3_BAUD=115`, vehicle system/component **1/1**, and controller system/component **255/190**. CH1 steering and CH2 drive are the only override channels accepted by this sketch. Configure the FC's receiver-takeover logic and GCS/RC failsafes independently. The firmware does not modify FC parameters or RC6 arbitration. Connect one bridge to R3/T3; remove the old Wi-Fi bridge from that UART when fitting the LilyGO rover. Your M5–M8 → PWM converter → BTS7960 motor wiring remains in place.

### TeleRC motor framed UART

| LilyGO rover | Dedicated TeleRC motor ESP32-S3 |
|---|---|
| GPIO43 TX | GPIO21 RX |
| GPIO44 RX | GPIO39 TX |
| GND | GND |

This backend speaks the existing TeleRC `A5 5A` CRC-protected UART framing. It requires the **TeleRCMotorController** firmware, not the standalone **BTS7960PWMConverter** sketch. That motor firmware retains its downstream watchdog, neutral handover and physical DIRECT/AUTOPILOT selector. This mesh package does not replace the motor firmware. The present Android LoRa base/rover sketches use a different radio envelope; upgrade every radio participant together to use this mesh, and use the Android local UDP connection at the gateway if testing Android. Native Android USB LoRa setup/provisioning is not implemented by this sketch.

Use a regulated supply through the board's supported input; common signal ground and 3.3 V UART levels. GPIO17/18 are onboard I2C pins, not this UART. Native USB CDC must be enabled so USB Serial Monitor does not occupy GPIO43/44. Avoid powering the board through USB and an external supply in a way that backfeeds either source.

## Build / flash

Pinned tested toolchain: **ESP32 Arduino core 3.3.2**, **RadioLib 7.2.1**, Arduino CLI 1.3.1. Arduino IDE: board **LilyGo T3-S3**, revision **Radio-SX1262**, USB CDC On Boot **Enabled**, USB Mode **Hardware CDC and JTAG**, PSRAM **Enabled** (2 MB QSPI), 4 MB flash, default 4 MB partition. SX1276/SX1278/SX1280 variants are unsupported here.

```bash
arduino-cli core install esp32:esp32@3.3.2 --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli lib install RadioLib@7.2.1
arduino-cli compile --fqbn esp32:esp32:lilygo_t3s3:CDCOnBoot=cdc,Revision=Radio_SX1262,PSRAM=enabled --output-dir build bridge/TeleRCMesh
arduino-cli upload --fqbn esp32:esp32:lilygo_t3s3:CDCOnBoot=cdc,Revision=Radio_SX1262,PSRAM=enabled -p COM7 --input-dir build bridge/TeleRCMesh
```

The package also contains `firmware/TeleRCMesh.ino.merged.bin`, a complete image for the pinned LilyGO profile. With Python and esptool installed, close Serial Monitor and run:

```powershell
py -m pip install esptool==5.1.0
py -m esptool --chip esp32s3 --port COM7 write-flash 0x0 firmware/TeleRCMesh.ino.merged.bin
```

Replace COM7 with your board's port. The merged image is a **factory flash** covering the complete 4 MB flash, so it clears saved NVS profiles and always requires setup again. To preserve existing mesh settings during later updates, use Arduino IDE / CLI upload of the compiled sketch instead of the factory image. This image is for the matching T3-S3 SX1262, not generic ESP32 boards.

## Timing and stopping behavior

- Rover-originated polls carry a random 64-bit challenge. A response is consumed once, only within **350 ms after poll TX completes**. Recovery cannot replay a previously accepted drive or ARM packet.
- Polls are scheduled **370 ms after previous poll TX completion**; actual delivered update rate is lower than 2.7 Hz. The profile prioritizes bounded multi-hop timing over fast wheel response. Maximum-size frames are about 55 ms on air at SF7/BW500; relay/return airtime matters.
- Gateway coalesces fresh commands; each touched axis has a **200 ms mailbox lifetime**, never refreshed by ignored channels. Commands are not periodically regenerated. Queued RF transmissions expire after **100 ms**, use asynchronous channel-activity detection and randomized deferral, and have no delivery retries. Hidden nodes and congestion can still cause collisions/drops.
- On the rover, each owned steering/drive axis must be updated within **500 ms**. Heartbeats, telemetry, polls, and steering-only packets do not renew stale drive. A missed control cycle may therefore deliberately stop the rover.
- Boot and a stop latch require a fresh simultaneous neutral CH1/CH2 packet (1475–1525 µs on both) before accepting motion. ARM must follow fresh centered controls. The sketch never creates ARM commands.
- On owned-axis timeout, explicit release/disconnect, RF failure, or raw-FC heartbeat expiry: one bounded UART write sends neutral then releases CH1/CH2, clearing ownership and latching control OFF. UART congestion retries only this stop sequence; it never retries stale drive/ARM. Release restores receiver authority where FC configuration permits it. This is not a universal disarm or hardware power cutoff.
- Monitor-only sessions do not generate neutral/release overrides. Real FC or motor telemetry supplies app heartbeat; the mesh does not fabricate vehicle heartbeat. Raw-FC mode forwards commands only while system 1/component 1 ArduRover heartbeat is fresh (2.5 seconds).
- Setup serves HTTP only with RF disabled. Active operation has no blocking web server. Mesh credentials are stored locally in NVS; setup uses HTTP Basic auth on the local protected AP. Mesh HMAC-SHA256/128 authenticates packets; it does not encrypt traffic or resist jamming. All nodes possessing the shared key are trusted.

Telemetry whitelist: real HEARTBEAT, COMMAND_ACK, SYS_STATUS, GPS_RAW_INT and GLOBAL_POSITION_INT, at most 96 bytes. Accepted control: MAVLink 1 GCS heartbeat, CH1/CH2 RC override, standard ARM/DISARM, TeleRC discovery/disconnect. Target ID 1/1 is fixed. Mission/parameter transfer, force-arm, signed MAVLink, arbitrary servo commands and transparent Mission Planner operation are outside scope.

## Bench acceptance (hardware tests still required)

Raise/restrain the rover and begin with motor battery disconnected.

1. Verify board model, antenna, UART crossover/ground, selected backend, identical profile/key, unique IDs and matching frequency. Confirm boot/config mode produces no motion or auto-arm.
2. Start with one gateway and rover, one radio leg; confirm PC receives the actual FC/motor heartbeat. At neutral, enable and explicitly ARM. Verify CH1/CH2 input and low-speed wheel directions.
3. Confirm non-neutral ARM/motion is rejected after startup/stop; fresh neutral permits an explicit operator restart.
4. Stop PC control updates, disable Wi-Fi, power off gateway, disconnect rover UART, and cut a relay separately. Measure from **last accepted axis frame** to neutral/release and actual wheel stopping. UART loss requires the FC/motor downstream failsafe; this sketch cannot deliver a stop over a disconnected wire.
5. Send steering-only updates while drive becomes stale. Confirm drive is not held. Test Disable, Disconnect, transmitter takeover/RC6, app exit and PC reconnect with displaced pedals.
6. Configure two radio legs and add relay 3, then three legs and relay 4. Place nodes so each hop is needed; measure per-hop loss, maximum gap, input-to-output latency and stops. Include hidden-node layouts, obstacles, electrical noise, brownouts and battery variation.
7. Restore communications with pedals displaced. Confirm no resumed motion until centered and explicitly re-enabled by the operator. Test RF init/receive/CAD/TX failures and full UART queues.

Range extension is an intended capability, not a measured range claim. Do not increase the watchdog to hide packet loss. If command gaps reach 500 ms, improve placement/antennas, reduce forwarding nodes or use a direct path before ground operation.

## Rollback and provenance

This addition does not change PC TeleRC Python code or the Android/motor firmware. To roll back, flash the earlier working Wi-Fi/LoRa bridge and restore its wiring with power removed. Mesh nodes cannot relay packets for the older point-to-point protocol.

PC baseline inspected: `9fbf053989203690195f1d0057fafcf0397a660a` (main, v0.1.0a13); transport also remains compatible with the MAVLink 1 UDP envelope documented for v0.1.0a10, but installation/HIL against that executable is not yet tested. `TeleRCWire.h` is reused from the user's TeleRC repository at `67b2cf5137989c1a6a65a4b02af960105d04afa3`; mesh framing/scheduling is a separate protocol version.

Primary references:
- LILYGO pins, board revisions and flash settings: https://github.com/Xinyuan-LilyGO/LilyGo-LoRa-Series/blob/master/docs/en/t3_s3_sx1262/t3_s3_sx1262_hw.md
- RadioLib SX126x API: https://jgromes.github.io/RadioLib/class_s_x126x.html
- Existing TeleRC integration: https://github.com/Denberg28/TeleRC/blob/main/bridge/LORA_INTEGRATION.md

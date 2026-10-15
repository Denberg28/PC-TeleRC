# TeleRC LilyGO direct LoRa — 915 MHz preset 1

Included with PC TeleRC v0.1.3 / LilyGO T3-S3 SX1262. The BASE and ROVER source files are unchanged from the user-confirmed pnp915-1 preset. Existing working boards need no reflash for the offline map application update.
Firmware baseline: LilyGO 0.5.0 at PC-TeleRC v0.1.2, commit f3f66b60ac7a61e1c9469cacf6678865edf9629b.
This is a separate source-sketch preset; it does not replace the stable desktop release.

## Included settings

| Setting | BASE and ROVER |
| --- | --- |
| LoRa frequency | 915.000 MHz (915000 kHz in the sketch) |
| Embedded password | telerc123 — all NINE characters |
| Initial mode | LoRa |
| Relay count | 0: BASE directly to ROVER; no NODE |
| Transmit power | 2 dBm |
| PC connection | BASE native USB, 115200 baud; PC TeleRC sets DTR high / RTS low |
| Rover connection | SpeedyBee UART3, MAVLink2 at 115200 |

Use this preset with the 915 MHz SX1262 hardware variant and a suitable antenna. The requested shared password is embedded in the source and firmware; it is publicly known.

## Upload once to each board

1. Disconnect motor power. Attach both LoRa antennas.
2. Extract this complete ZIP. Keep every adjacent header with its sketch.
3. Arduino IDE: install **esp32 by Espressif Systems 3.3.2** in Boards Manager and **RadioLib 7.2.1** in Library Manager.
4. Select **LilyGo T3-S3**, revision **SX1262**, **USB CDC On Boot: Enabled**, **USB Mode: Hardware CDC and JTAG**, QSPI PSRAM enabled and 4 MB flash. Keep **Erase All Flash Before Sketch Upload: Disabled**.
5. Open `firmware/TeleRCLoRa_BASE/TeleRCLoRa_BASE.ino`, select the BASE COM port, and upload to the PC-side board.
6. Open `firmware/TeleRCLoRa_ROVER/TeleRCLoRa_ROVER.ino`, select the rover COM port, and upload to the rover board.
7. Release BOOT and reset after uploading if the board remains in the downloader. Close Serial Monitor and Arduino IDE before opening PC TeleRC.

The Arduino IDE compiles these sketches during upload. This package contains source, not precompiled ESP32 binaries.

## Connect

- Leave BASE attached to the PC by native USB. Power ROVER and the SpeedyBee.
- Existing working LilyGO rover wiring stays: FC T3 -> GPIO44 RX, FC R3 <- GPIO43 TX, common GND. GPIO17/18 serve the OLED. Keep UART3 at MAVLink2 / 115200.
- Both OLEDs should show MODE: LORA, 915.000 MHz and RELAYS: 0. BOOT must be released during startup. Exit setup menus; setup pauses radio operation.
- In PC TeleRC v0.1.2 select **LilyGO T3S3 SX1262 / LoRa**, refresh ports, select BASE's actual COM port, then **Apply & Connect**. No Wi-Fi setup/password entry is needed.
- Wait for the real SpeedyBee heartbeat, use MANUAL mode, center/release input, and manually enable PC Control. ARM stays a separate explicit action. No automatic arming or driving was added.
- With wheels raised and a reachable motor cutoff, verify link-loss stopping and transmitter takeover before ground use.

## Previously saved Wi-Fi mode

On the first boot of this preset, ROVER writes LoRa as its saved mode and marks this migration complete. This overrides an old Wi-Fi selection without erasing calibration or pairing storage. Subsequent deliberate BOOT-menu Wi-Fi/LoRa selections remain saved. Reuploading this same preset with erase disabled preserves that later choice; select LoRa in BOOT to return to LoRa.

## Password behavior

An error in earlier guidance called `telerc123` eight characters; it actually contains nine. The preset accepts 8-32 visible ASCII characters when deriving pairing keys and validating sketch passwords. All nine characters are used. Existing eight-character key derivation is unchanged. Matching BASE and ROVER from THIS ZIP can pair without configuration.

Compiled pairing overrides old saved frequency/key on every boot. Web/USB pairing changes are locked while the sketch password is nonempty. Change the password/frequency in BOTH .ino files and reupload to change pairing. The PC v0.1.3 password editor accepts 8–32 visible ASCII characters; provisioning is still not needed with this compiled preset. An older, unmodified firmware sketch rejects this nine-character password.

## If COM9 still cannot open

This preset configures RF pairing; it does not resolve a Windows port-opening failure. Close Serial Monitor, Mission Planner and other serial applications; unplug/replug BASE and select the port that appears under Ports (COM & LPT). COM numbering can change. Windows USB JTAG/serial naming is normal, but TeleRC must successfully open the serial COM interface first.

## Validation scope

See VALIDATION.json for host checks against the exact packaged sources. Host simulation does not validate ESP32 target compilation, Windows USB drivers, physical radio delivery, RF range, power integrity or actual stop latency. No new desktop app is required for this preset.

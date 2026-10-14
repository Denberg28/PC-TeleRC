# PC TeleRC v0.1.1 stable setup

This release consolidates the Windows app, LilyGO Wi-Fi/LoRa firmware 0.3.1 and PWM converter 1.0.5. Keep the previous v0.1.0a10 installation and settings backup available for rollback. The stable software designation records the requested promotion and automated validation; physical rover operation remains to be verified.

## Choose the installed board roles

| Target-build directory | Board and use |
|---|---|
| ROVER_WIFI | LilyGO T3-S3 SX1262 on rover, direct PC Wi-Fi; no BASE required |
| ROVER_LORA | LilyGO T3-S3 SX1262 on rover, LoRa paired with BASE |
| BASE | LilyGO T3-S3 SX1262 connected to PC USB for LoRa |
| PWM | ESP32-S3 driving the four BTS7960 boards from SpeedyBee PWM |
| WIFI | Original ESP32-S3 Wi-Fi bridge, if used instead of LilyGO |
| ELRS | Original ESP32-S3 native MAVLink UART relay; ordinary CRSF is unsupported |

Wi-Fi and LoRa are separate firmware builds, selected while motor power is disconnected. There is no automatic transport fallback. The shipped ROVER source defaults to Wi-Fi; set TELERC_TRANSPORT_WIFI=0 in LinkMode.h to compile LoRa. Do not connect both an original ESP32 bridge and a LilyGO bridge TX to the same FC UART.

## Update order

1. Disconnect motor power. Back up the current PC settings and working sketches. Install PC TeleRC 0.1.1 or unzip the portable app into a new folder.
2. Update the motor-side ESP32-S3 with firmware/TeleRC_4x_BTS7960_PWM_GlitchFilter (converter 1.0.5). It confirms each PWM falling edge after 30 us of stable low and preserves the original rise across shorter notches. Valid command timestamps, 150 ms loss protection, 300 ms neutral recovery and the existing duty ramp remain.
3. Flash the LilyGO rover's selected Wi-Fi or LoRa role. For LoRa also update the PC-side BASE. Use ESP32 core 3.3.2, LilyGO T3-S3/SX1262, 4 MB flash, QSPI PSRAM and USB CDC/JTAG; RadioLib 7.2.1 is required for LoRa. Do not erase NVS when preserving pairing. See LILYGO-WIFI-LORA.md for the detailed board settings and indicators.
4. SpeedyBee stays in the loop: its T3 goes to LilyGO GPIO44 RX; its R3 receives LilyGO GPIO43 TX; common GND. Retain SERIAL3_PROTOCOL=2, SERIAL3_BAUD=115 and RC6 transmitter takeover. Use the actual board preset when compiling for a generic ESP32-S3 PWM/bridge module.
5. In Wi-Fi mode join TeleRC-Rover, password telerc123, and select ESP32-S3 / LilyGO Wi-Fi in the app. Target 192.168.4.1, UDP 14550, CH1 steering and CH2 throttle. In LoRa mode connect BASE USB, select LilyGO LoRa USB and retain matching frequency/key on both boards.
6. Apply & Reconnect, wait for the real FC heartbeat, center steering and release pedals. Enable PC Control manually at neutral, then ARM explicitly. LilyGO Wi-Fi requires fresh owned neutral CH1/CH2 before accepting ARM. Changing settings disables control and requires Apply Settings followed by manual enable.

Firmware 0.3.1 includes blinking while searching and solid indication on valid link traffic. The LED does not measure the supply voltage and is not an armed indicator. GPIO37 is the T3-S3 user LED. The SX1262 antenna serves LoRa, not Wi-Fi.

Existing PWM pins and motor mappings are retained. Verify the actual left/right motor wiring before applying any old conditional parameter patch; this release does not apply FC parameters automatically. Power requirements and the warning against paralleling independent USB/UBEC outputs are in the LilyGO guide.

## Validation and ground check

Release checks include 130 application tests, 19 actual-sketch host variants with sanitizers, and six ESP32 target builds (LilyGO BASE, both rover modes, PWM and original bridge Wi-Fi/ELRS). CI builds the Windows installer and portable app, checks all required downloads, then publishes v0.1.1 as stable/Latest.

Host tests cover authentication, command/FC loss, neutral acquisition, client/endpoint routing, LED freshness, AP retries, USB/UART stalls, timer rollover and 3000 noisy differential PWM frames. Target builds establish compilation against the pinned board/toolchain, not RF range, electrical immunity or a measured physical stop latency.

With wheels raised and a reachable cutoff, verify direction, simultaneous steering/throttle, loss stop and transmitter takeover. Repeat with USB removed and then normal ground operation. If a stop recurs, capture PC diagnostics and the firmware's preserved last-stop cause before reconnecting. See FIRMWARE-RECOVERY-rc7.md for fault interpretation. Do not assume a software update fixes a weak supply or loose connector.

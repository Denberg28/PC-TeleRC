# LilyGO T3-S3 SX1262 firmware 0.3.1 — Wi-Fi / LoRa stable package

ROVER now defaults to Wi-Fi. BASE remains the LoRa USB bridge. This stable release includes PC TeleRC 0.1.1, LilyGO firmware 0.3.1, PWM converter 1.0.5, source sketches and prebuilt role-specific binaries. The firmware extends the previously delivered 0.3.0 update with bounded USB diagnostic waits.

## First use: direct Wi-Fi from PC to rover

1. Disconnect motor power. Use the board's native USB-C to upload. In Arduino IDE select LilyGo T3-S3, radio revision SX1262, ESP32 core 3.3.2, USB CDC On Boot Enabled, USB Mode CDC and JTAG, 4 MB flash and QSPI PSRAM. Keep Erase All Flash Before Sketch Upload Disabled to preserve existing LoRa pairing settings.
2. Open firmware/TeleRCLoRa_ROVER/TeleRCLoRa_ROVER.ino. Keep every adjacent header in that folder. LinkMode.h defaults to TELERC_TRANSPORT_WIFI 1. Wi-Fi mode uses the ESP32 core libraries and does not require RadioLib.
3. Upload to the rover LilyGO. Keep the existing UART wiring: SpeedyBee T3 -> GPIO44 RX; SpeedyBee R3 <- GPIO43 TX; common GND. Supply regulated 5 V to 5V/VBUS. UART signals are 3.3 V. Do not use GPIO17/18 for FC UART on this board; they serve the OLED I2C bus.
4. Remove USB before feeding VBUS from the UBEC. Connect the PC to Wi-Fi TeleRC-Rover, password telerc123. This AP does not provide internet. It permits one Wi-Fi station. No PC-side BASE LilyGO is needed for Wi-Fi.
5. In PC TeleRC choose ESP32-S3 · Wi-Fi (the existing UDP profile also works with this LilyGO firmware), target 192.168.4.1, target/listen ports 14550, steering CH1 and throttle CH2. Apply & Reconnect. The PC application must be allowed through the Windows firewall for UDP on this network.
6. Keep SpeedyBee UART3 set to MAVLink2 / 115200 (SERIAL3_PROTOCOL=2, SERIAL3_BAUD=115). This candidate expects ArduRover system 1/component 1. Update the PWM converter to 1.0.5 for the pulse-noise fix. Retain motor mapping and RC6 transmitter takeover configuration. Only the old Wi-Fi bridge is replaced; never connect two bridge TX outputs to FC R3.
7. Wait for the real FC heartbeat, center steering and release pedals. Manually enable PC Control. ARM is a separate explicit action, allowed by the bridge only while both owned CH1/CH2 commands are fresh and neutral. Wi-Fi association never arms or enables control.

## LED indication

| Mode | Blinking, 250 ms on / 250 ms off | Solid |
|---|---|---|
| Wi-Fi ROVER | Searching, no valid PC traffic, no fresh FC heartbeat, or AP unavailable | Wi-Fi client present, valid TeleRC packet within 1.5 seconds, and valid FC heartbeat within 2.5 seconds |
| LoRa BASE / ROVER | Waiting for valid paired traffic, maintenance/unconfigured, or radio unavailable | Accepted authenticated peer packet within 500 ms |

The longer Wi-Fi LED interval accommodates the PC's approximately 1 Hz monitor heartbeat. It does not increase the 500 ms motor-command timeout. Solid is not an armed/control-active indicator or an exact 5 V measurement. A processor hang can freeze a GPIO LED. The charging LED is independent. The next visible OFF phase after link expiry can take up to another 250 ms.

## Switching back to LoRa

Disconnect motor power. Set TELERC_TRANSPORT_WIFI to 0 in the rover's LinkMode.h, then compile and upload the ROVER sketch again. Install RadioLib 7.2.1 for LoRa compilation. Upload firmware/TeleRCLoRa_BASE/TeleRCLoRa_BASE.ino to the PC-side board if needed. Use LoRa Setup in the PC app to retain/configure matching frequency, power and pairing key on both boards, then restart them and select the app's LilyGO LoRa USB profile. Wi-Fi is not started in this mode.

Mode selection is at compile/upload time, not a runtime dropdown or BOOT-button toggle. There is no automatic fallback. The modes share UART3 but never run concurrently. In Wi-Fi mode the SX1262 is held in reset; BASE is not in the driving path. Existing LoRa credentials are not changed by the Wi-Fi sketch. Do not attempt LoRa Setup on a ROVER currently running Wi-Fi mode.

## Safety and compatibility

- Wi-Fi uses the existing unframed PC TeleRC UDP protocol. It accepts standard CRC MAVLink1 PC heartbeat, explicit normal ARM/DISARM and CH1/CH2 overrides, plus discovery/disconnect strings. No arbitrary command passthrough, legacy nonstandard RC CRC, four-channel Android motor control or automatic arming is added.
- Startup/recovery requires neutral CH1/CH2 and a fresh real FC heartbeat. A stale owned axis at 500 ms, FC heartbeat age 2.5 s, Wi-Fi station/AP loss, UART failure, explicit disconnect or DISARM stops/releases owned overrides. Pending neutral/release writes retry. Other RC channels, including RC6, remain untouched.
- GCS heartbeat/discovery packets never renew motor command freshness. Client loss clears old queued UDP packets. Peer endpoint lock prevents an active owner being displaced. Wi-Fi recovery requires fresh neutral acquisition. The existing PC app controls its own enable latch; a short Wi-Fi interruption below its heartbeat timeout can leave its UI showing ACTIVE. In that case the bridge can reacquire when valid neutral packets arrive. Firmware alone cannot distinguish a new button click from an already-active PC session using this legacy UDP protocol.
- WPA2 password controls Wi-Fi access. UDP CRC/source IDs validate frames but are not application-level authentication. LoRa retains its HMAC/challenge protocol.
- The external SX1262 antenna is for LoRa, not Wi-Fi. This firmware does not establish better Wi-Fi range or fix a noisy/weak power supply. Keep independent FC failsafes and the physical motor cutoff.
- USB may hide a weak UBEC supply. Do not parallel USB VBUS and UBEC output. The white battery socket/VBAT accepts a protected single Li-ion/LiPo cell, maximum 4.2 V; never feed it 5 V.

## Validation and first bench test

Six host C++ checks pass: Wi-Fi startup/control/ARM gates and failsafes; endpoint/oversize/queue/rollover behavior; AP retries; LoRa ROVER build/maintenance; LoRa BASE build/maintenance; LED state/timeout tests. Reproduce with python3 tests/run_host_tests.py and g++. The mocks do not validate ESP32 drivers, cryptography, physical RF, actual UART timing or electrical power. The stable build compiles both LilyGO rover transport modes and the BASE against ESP32 core 3.3.2/RadioLib 7.2.1. Target compilation is checked by the release workflow; no physical HIL claim is made.

With wheels raised, a reachable motor cutoff and low throttle: verify direction, steering, neutral enable and explicit ARM/DISARM. Turn off PC Wi-Fi and confirm the rover stops. Disable PC Control before rejoining, then manually re-enable at neutral. Also test a short interruption: the bridge must reject non-neutral recovery; the existing PC app may not latch OFF unless its own timeout is reached. Disconnect FC UART and confirm heartbeat loss prevents continued control. Confirm transmitter takeover. Repeat with USB removed, then test LoRa separately. Record physical stop latency and LED behavior before ground use. Physical rover validation remains outstanding.

Hardware/API references:
- https://github.com/Xinyuan-LilyGO/LilyGo-LoRa-Series/blob/master/docs/en/t3_s3_sx1262/t3_s3_sx1262_hw.md
- https://github.com/Xinyuan-LilyGO/LilyGo-LoRa-Series/blob/master/examples/Factory/utilities.h
- https://docs.espressif.com/projects/arduino-esp32/en/latest/api/wifi.html

The LoRa-specific wiring/pairing detail remains in docs/LILYGO-SX1262-ARDUROVER.md.

# Firmware recovery review — PC TeleRC v0.1.1rc7

## What was reproduced and fixed

The previous converter immediately treated every valid-width falling edge as a completed command. A 20 us low notch occurring 1000 us into an otherwise valid 1800 us forward pulse therefore produced a 1000 us reverse command. The remaining 780 us fragment was rejected. The new fault-injection test failed against converter 1.0.4 before the fix.

Repeated short notches earlier in a pulse could also split both fragments below the valid minimum; the last valid pulse would eventually expire and latch all motors off. A notch at 1500 us inside a 2000 us pulse could misrepresent a held command as neutral during recovery. These are reproduced software defects. They are plausible contributors to load changes and neutral-wait stops, but do not prove the cause of the physical rover event.

Converter 1.0.5 defers pulse completion until the input has remained low for 30 us. A rising edge within that window discards the short low notch and preserves the original rising-edge timestamp. Confirmation occurs in the existing interrupt/main-loop flow, without a busy wait or additional acceleration ramp. Valid pulse age remains anchored to its original falling edge; confirmation does not extend the loss timeout.

Noise longer than this filter window, actual signal loss, loose connections, driver protection and supply dips can still interrupt operation. This is a software filter with a specified window, not a substitute for sound power and signal wiring.

## USB diagnostic waits

Checking Serial.availableForWrite() alone does not establish a nonblocking call: the pinned Arduino ESP32 HWCDC implementation takes its transmit mutex using a default 100 ms wait. Serial.write() can wait separately. All current role sketches now set the USB CDC transmit wait to 1 ms at startup. Chunked output remains in place; partial writes retain their unsent offset. A zero timeout is avoided because the pinned HWCDC write retry loop decrements an unsigned timeout counter.

This bounds those configured USB waits; it does not guarantee a universal hard real-time scheduling bound or cure an electrical reset. The mock test injects contention according to the configured wait and confirms it does not cause the converter's 150 ms loop-stop latch.

References: [Arduino ESP32 3.3.2 HWCDC implementation](https://github.com/espressif/arduino-esp32/blob/3.3.2/cores/esp32/HWCDC.cpp), [USB CDC API](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/usb_cdc.html).

## Safety and response retained

- PWM last-valid timeout: 150 ms. All four FC PWM channels remain required.
- Neutral recovery: all four inputs within 1500 ±35 us continuously for 300 ms, with valid input. No automatic arm.
- Converter acceleration: 8 duty counts per 5 ms tick, about 160 ms to full duty. Reversal crosses zero without an added dwell.
- Wi-Fi accepted-command timeout: 500 ms. Centered neutral is required after startup/release/timeout; normal simultaneous steer/drive is accepted.
- LoRa neutral acquisition, command/FC loss checks, stop counter, boot tracking, authentication and transmitter takeover remain.
- PC manual enable, freshness checks and separate steering/throttle sensitivity remain.

The firmware contains no obstacle sensor or motor-current feedback. It does not intentionally stop because an obstacle was hit or because steering and throttle were combined. A physical impact can still disrupt a connector, power rail or signal.

## Which board to flash

| Board role | Source folder | Embedded version | When to use |
|---|---|---|---|
| ESP32-S3 controlling four BTS7960s | firmware/TeleRC_4x_BTS7960_PWM_GlitchFilter | 1.0.5 | Required for the PWM noise correction; applies with either Wi-Fi or LoRa upstream |
| ESP32-S3 Wi-Fi bridge to SpeedyBee | firmware/TeleRCBridge | 0.1.5 | Existing Wi-Fi path; TELERC_LINK_MODE=0, SSID TeleRC-Rover, password telerc123 |
| ESP32-S3 native MAVLink ELRS UART relay | firmware/TeleRCBridge | 0.1.5 | Existing relay path only; TELERC_LINK_MODE=1, not ordinary CRSF |
| LilyGO T3-S3 SX1262 at PC | firmware/TeleRCLoRa_BASE | 0.2.1 | Direct SX1262 pair; retains stored provisioning |
| LilyGO T3-S3 SX1262 at rover | firmware/TeleRCLoRa_ROVER | 0.2.1 | Direct SX1262 pair; SpeedyBee stays in the control path |

Flash only the roles actually installed. The PWM converter update is separate from the Wi-Fi/LoRa board update. Use Arduino IDE Library Manager to install RadioLib 7.2.1 for the LilyGO sketches, with ESP32 core 3.3.2. Keep the entire sketch folder together so Link.h, MeshCore.h and TeleRCWire.h remain alongside the .ino.

Target-build archive directories are PWM, WIFI, ELRS, BASE and ROVER. PWM/WIFI/ELRS use the generic ESP32-S3 target with Hardware CDC/JTAG and CDC on boot; BASE/ROVER use LilyGO T3-S3, SX1262, PSRAM enabled. These build configurations are not proof of the flash size/PSRAM configuration on an unidentified DevKit module. Prefer compiling the source using your board's actual preset. Never flash an image from a different role. Existing pin assignments and FC parameters are unchanged.

## Validation

The actual-sketch host suite covers both Arduino API generations 2 and 3, Wi-Fi and ELRS bridge modes, and both SX1262 roles. New tests include the reproduced in-pulse notch, 3000 rapid differential frames with repeated short notches, original falling-edge age, real loss timeout, prevention of false neutral qualification, 300 ms recovery and contended USB diagnostics. Existing rollover, isolated invalid pulse, same-side output, direction reversal, UART failure, AP recovery, radio/FC loss and stalled USB cases remain.

The release workflow additionally compiles all five target modes with the pinned ESP32 toolchain and builds/tests the Windows application. Check the workflow's final result for target-build evidence. Host mocks do not measure real ISR timing, motor current, voltage sag, radio range or Windows wheel behavior.

## Verify on the rover

1. Flash the PWM converter first. Confirm its side mapping: M5/M6 must drive the physical left side and M7/M8 the right side if using the documented FL/RL/FR/RR order. The review's conditional parameter patch remains conditional; no parameters are automatically changed.
2. With motor power off and logic powered, exercise rapid steering and drive. Then test at low output with driven wheels clear. Keep a reachable motor-power cutoff.
3. Perform normal ground operation without deliberately colliding or stalling motors. At any stop, preserve PC diagnostics and the converter/bridge Serial Monitor record before reconnecting.
4. If stops recur, use the stored cause: last=input-timeout with mask/ageUs identifies expired FC PWM; last=loop-gap identifies converter execution delay; bridge last=command-timeout identifies lost accepted commands; restarting up/reset identifies a board reset. A live PC heartbeat alone does not prove the motor path stayed active.

No component purchase is needed for this software correction. If the event is a power dip, size the electrical correction from measured transient/stall current and supply voltage; firmware alone cannot establish or solve that fault.

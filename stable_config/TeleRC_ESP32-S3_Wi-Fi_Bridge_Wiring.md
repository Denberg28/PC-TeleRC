# TeleRC ESP32-S3 Wi-Fi Bridge Wiring

For an ESP32-S3 Wi-Fi/MAVLink bridge connected to SpeedyBee F405 V4 running ArduRover.

## UART3 connections

| ESP32-S3 bridge | SpeedyBee F405 V4 | Purpose |
|---|---|---|
| GPIO17 (TX) | R3 (RX) | Commands to the flight controller |
| GPIO18 (RX) | T3 (TX) | Telemetry from the flight controller |
| GND | GND | Common signal reference |
| Board 5V input | Same regulated 5V supply as the FC | Controller power |

TX connects to RX in each direction. Use GPIO18, not GPIO28, for the standard TeleRC bridge RX assignment. GPIO numbers are not header positions.

## Bridge sketch settings

```cpp
constexpr int FC_RX_GPIO = 18;
constexpr int FC_TX_GPIO = 17;
constexpr uint32_t FC_BAUD = 115200;
constexpr uint16_t UDP_PORT = 14550;
```

Verify these assignments in the sketch actually flashed to the bridge. UART wiring carries MAVLink; it does not carry motor power.

## SpeedyBee settings

In Mission Planner, set UART3 to MAVLink 2 at 115200 baud:

```text
SERIAL3_PROTOCOL,2
SERIAL3_BAUD,115
```

Reboot the flight controller after changing serial settings.

## Power wiring

Use regulated 5V, never raw battery voltage, for the ESP32 board's 5V input.

| Arrangement | Connections |
|---|---|
| One UBEC | Separate 5V/GND branches to FC/ESP controllers and BTS driver logic |
| Two UBECs | UBEC 1 supplies FC and ESP controllers; UBEC 2 supplies BTS VCC, R_EN and L_EN |
| Motor power | Battery distribution through fuse/cutoff to each BTS B+ and B- |

With two UBECs, do not join their positive 5V outputs. Keep grounds common. Motor return current must use power wiring directly to battery distribution, not FC/ESP signal-ground leads.

If the FC already receives regulated 5V from its UBEC, connect the ESP to that same 5V rail; this is one supply, not two supplies in parallel. Check available regulator capacity and wiring voltage drop.

Disconnect external ESP 5V before using USB unless the specific carrier supports simultaneous supplies safely. Do not apply 5V to UART GPIOs; use compatible 3.3V UART signals.

## Separate PWM converter

The Wi-Fi bridge and PWM converter are separate ESP32-S3 boards in this setup:

| Function | Connection |
|---|---|
| Wi-Fi command/telemetry bridge | GPIO17/18 to FC R3/T3 |
| PWM-converter inputs | FC M5/M6/M7/M8 to converter GPIO4/5/6/7 |
| PWM-converter outputs | Converter GPIO8-15 to four BTS RPWM/LPWM pairs |

Flash the Wi-Fi bridge firmware to the bridge MCU and the converter firmware to the motor MCU. Flashing the converter onto the bridge replaces its Wi-Fi functionality.

## Connection check

1. Disconnect motor battery power before checking or changing wiring.
2. Verify GPIO17 to R3, GPIO18 to T3, and common GND.
3. Verify regulated 5V and polarity at both controller boards.
4. Power the FC and bridge; connect TeleRC to the bridge's configured Wi-Fi network.
5. Confirm an actual FC heartbeat and telemetry in TeleRC before enabling control.
6. Test arm/disarm and control with wheels raised, then verify neutral output on command-link loss according to the installed firmware and FC failsafes.

If telemetry is missing, check swapped TX/RX, the flashed GPIO assignments, UART3 parameters, and whether the FC is powered. If controllers reset under motor load, investigate power integrity separately from UART wiring.

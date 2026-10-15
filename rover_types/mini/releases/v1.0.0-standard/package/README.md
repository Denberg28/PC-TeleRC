# TeleRC Mini Rover — v1.0.0-standard

Standard source baseline for **two or four brushed DC motors with left/right skid steering**, ESP32-S3, FlySky FS-iA6 PWM and PC TeleRC over Wi-Fi. Default remains four TT motors and two MX1508 boards. Selectable interfaces also cover DRV8833, TB6612FNG, BTS7960 modules and L298N modules.

“Standard” means a versioned, configurable software interface with tests and wiring instructions. **Hardware qualification is pending** for every profile. This is open-loop duty control, without encoders, current feedback or a speed/torque guarantee.

## Choose and upload

1. Read [HARDWARE_PROFILES.md](HARDWARE_PROFILES.md). In `TeleRC_MiniRover/HardwareProfile.h`, select `TELERC_DRIVER`, `TELERC_MOTOR_COUNT`, declared maximum motor supply voltage and motor rating. Follow [WIRING.md](WIRING.md) for that exact profile. No automatic driver detection is performed.
2. Set polarity, per-motor reduction/caps and Wi-Fi password in `Config.h`. Two-motor builds use slots **LF and RF**, indices **0 and 2**; LR/RR pins are unused.
3. Disconnect motor power and external ESP32 positive 5 V before attaching PC USB. Extract the ZIP fully and open `TeleRC_MiniRover/TeleRC_MiniRover.ino`; keep all seven adjacent headers.
4. Install **esp32 by Espressif Systems**, select **ESP32S3 Dev Module**, match flash/PSRAM to your board and choose its COM port. No PSRAM or third-party Arduino library is needed. Native USB: enable USB CDC On Boot. Upload, using BOOT/RESET download mode if necessary.
5. Open Serial Monitor at **115200 baud**. Check profile, motor count, PWM frequency and declared voltage. Voltage values are settings, not sensor readings. Fatal pin/PWM initialization errors must be corrected before connecting motor power.
6. Complete [RADIO_SETUP.md](RADIO_SETUP.md) and [BENCH_TEST.md](BENCH_TEST.md), starting with raised wheels and a current-limited supply.

Target CI covers cores **2.0.17 and 3.3.12**; see `VALIDATION.md` and the enclosing release's `TARGET_BUILD.md` for exact configurations/results. The ZIP includes source, tests and documentation; no prebuilt binary.

## Package map

| File | Purpose |
|---|---|
| `HardwareProfile.h` | Driver interface, 2/4 motors, pins, voltage declarations, PWM frequency |
| `Config.h` | Radio/network/safety limits, polarity, trims and duty caps |
| `MotorOutputs.h` | Driver truth tables, enable/sleep control, channel allocation and pin checks |
| `RoverCore.h`, `RadioControl.h` | Mixing, arming, timeouts and source ownership |
| `ReceiverPWM.h`, `MiniMavlink.h` | PWM capture and bounded network decoding |
| `HARDWARE_PROFILES.md`, `REVIEW.md` | Compatibility and scaling decisions |
| `WIRING.md`, `wiring.svg`, `wiring.png` | Default wiring plus profile-specific signal tables |
| `tests/`, `VALIDATION.md`, `BENCH_TEST.md` | Automated evidence and physical acceptance |

## Receiver wiring summary

| FS-iA6 output | ESP32-S3 input | Purpose |
|---|---|---|
| CH1 signal | GPIO12 | Steering, center 1500 us |
| CH2 signal | GPIO13 | Bidirectional drive, center 1500 us |
| CH5 signal | GPIO14 | ARM OFF / ON |
| CH6 signal | GPIO15 | TX / STOP / PC selector |
| Receiver + | Logic buck 5 V | Receiver power |
| Receiver - | Common GND | Signal/power reference |

Confirm receiver signal amplitude. **Do not apply 5 V logic to an ESP32 GPIO.**
Use the 3.3 V powered SN74LVC125A buffer arrangement in `WIRING.md` for unknown
or 5 V signal levels. Direct signals are permitted only after verifying 3.3 V
compatibility. This is ordinary PWM, not UART, iBUS or PPM.

## Start with transmitter control

1. Lift wheels; set CH5 **OFF**, CH6 **STOP**, center steering and drive.
2. Verify receiver binding, PWM channel display and failsafe settings in `RADIO_SETUP.md`.
3. Select CH6 **TX**. Keep CH5 OFF and both axes centered for at least **0.4 s**.
4. Flip CH5 **ON**. Confirm `source=TX`, `permit=1`, `armed=1` in serial output.
5. Apply a small drive command. CH5 OFF, CH6 STOP or BOOT stops/disarms.

Held-ON ARM at startup is rejected. A rejected ARM edge is not retried when
you later center the stick: switch OFF, center for 0.4 s, then ON again.

## PC TeleRC mode

| Setting | Value |
|---|---|
| Wi-Fi | `TeleRC-MiniRover` |
| Demonstration password | `telerc123`; change in `Config.h` for normal use |
| PC transport | TeleRC UDP / ESP32-S3 Wi-Fi |
| Listen address and port | `0.0.0.0:14550` |
| Rover target | `192.168.4.1:14550` |
| Steering / drive | CH1 / CH2 |

1. Keep the FlySky transmitter on. Set CH5 OFF and CH6 PC, center radio axes,
   wait 0.4 s, then CH5 ON. This permits PC control but **does not arm motors**.
2. Connect PC TeleRC. Center the wheel/pedals and enable PC Control while disarmed.
3. Wait 0.3 s for fresh PC neutral, then press the PC **ARM** button explicitly.
4. CH5 OFF / CH6 STOP remains a local motor stop. A source change disarms;
   changing back requires authorization and neutral again.

PC wheel/pedal support uses the inspected existing wire contract. Keyboard
commands require a PC app that implements them; this firmware adds no Windows
keyboard handling and does not rebuild the EXE.

## Safety and operating limits

- Required PWM width range: 900..2100 us; commands clamp to 1000..2000 us.
  One malformed pulse is ignored. If any required channel has no valid pulse
  for **120 ms**, both sources stop/disarm.
- CH6 low (<=1250 us): TX; center: STOP; high (>=1750 us): PC.
  Selection requires 80 ms stable input; transitions remove drive immediately
  when observed by the main loop. CH5 uses the same low/high thresholds;
  an intermediate CH5 value stops/inhibits.
- TX authority requires explicit CH5 OFF->ON after 250 ms centered inputs and
  stable source selection. Use 0.4 s operational dwell to cover selector settling.
- In PC mode, a healthy receiver and CH5 permission are mandatory. PC drive
  packets expire after 500 ms independently of radio/heartbeat traffic.
- Wi-Fi loss, PC release, PC ARM/DISARM and PC disconnect cannot interrupt the
  selected healthy TX owner. PC heartbeat can still monitor actual armed state.
- Radio failure never automatically hands control to PC. There is no source
  blending, automatic arm or automatic source failover.
- **Configure receiver failsafe to CH1=1500, CH2=1500, CH5=OFF, CH6=STOP.**
  PWM cannot distinguish real control from repeated held-last receiver outputs.
  Correct failsafe behavior must be tested with the transmitter switched off.
- All stops **coast**, not active holding brake. The rover can roll on slopes.
  BOOT is a software stop; use a motor-power switch for physical isolation.
- 20 kHz PWM (L298 profile: 10 kHz), maximum duty 180/255 (~71%), steering gain 0.5, 30 ms reversal coast.
  These limits are not current limiting. Verify motor load/stall current and the selected driver temperature.
- Timeouts are cooperative software deadlines. A blocked/hung task can delay
  output updates; physical stop distance and radio failsafe delay are unmeasured.
- No receiver RSSI, battery/current sensors, camera, navigation or ELRS support.


See `HARDWARE_PROFILES.md` and `WIRING.md` for manufacturer references and electrical limits.

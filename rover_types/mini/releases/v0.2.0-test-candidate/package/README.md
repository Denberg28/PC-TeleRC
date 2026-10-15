# TeleRC Mini Rover — v0.2.0 FS-iA6 test candidate

ESP32-S3 + 4 TT geared motors + 2 MX1508 dual drivers, with **FlySky FS-iA6
individual PWM inputs** and the existing PC TeleRC Wi-Fi link. No flight
controller, iBUS decoder, CRSF adapter or extra Arduino library is required.

Motor pins and the left/right mixer remain the v0.1.0 baseline. Receiver support
adds an explicit source/ARM gate. This candidate requires the FS-iA6 to be
connected and transmitting valid PWM **even in PC mode**. Use v0.1.0 separately
if you need the older Wi-Fi-only architecture.

## Files

- `TeleRC_MiniRover/TeleRC_MiniRover.ino` and five adjacent headers: upload together.
- `WIRING.md`: motor, receiver, signal voltage and two-buck power wiring.
- `wiring.svg` / `wiring.png`: overview diagram.
- `RADIO_SETUP.md`: channel assignment, mandatory failsafe, TX/PC operation.
- `BENCH_TEST.md`: acceptance tests before ground operation.
- `VALIDATION.md` / `tests/`: test evidence and limitations.

## Upload

1. Disconnect motor power and external ESP32 positive 5 V before connecting PC USB.
2. Extract the ZIP fully. Open `TeleRC_MiniRover/TeleRC_MiniRover.ino` in Arduino IDE.
3. Install **esp32 by Espressif Systems**; select **ESP32S3 Dev Module** and the
   correct COM port. Match flash/PSRAM settings to the actual board; no PSRAM is needed.
4. For native USB serial select USB CDC On Boot enabled. Upload. If necessary,
   hold BOOT, press/release RESET, release BOOT, then retry upload.
5. Open Serial Monitor at **115200 baud**. Never wait for serial connection or
   disable brownout protection to mask a power fault.

The source has Arduino-ESP32 2.x and 3.x LEDC API branches. The repository adds
target compile checks for pinned cores **2.0.17 and 3.3.12**. Read the actual
workflow result before treating a target build as verified; host API doubles
are not an ESP32 cross-compiler. Source ZIPs contain no prebuilt `.bin`.

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
- 20 kHz PWM, maximum duty 180/255 (~71%), steering gain 0.5, 30 ms reversal coast.
  These limits are not current limiting. Verify TT load/stall current and MX1508 temperature.
- Timeouts are cooperative software deadlines. A blocked/hung task can delay
  output updates; physical stop distance and radio failsafe delay are unmeasured.
- No receiver RSSI, battery/current sensors, camera, navigation or ELRS support.

## References

- FS-iA6 PWM/power specifications: https://www.flysky-cn.com/ia6-canshu
- FlySky failsafe guidance: https://www.flysky-cn.com/journal/2021/2/21/about-the-flysky-remote-control-failsafe-function
- GPIO interrupts: https://docs.espressif.com/projects/arduino-esp32/en/latest/api/gpio.html
- ESP32-S3 board/power: https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.1.html
- 3.3 V buffer with 5.5 V tolerant inputs: https://www.ti.com/product/SN74LVC125A
- MX1508 IC datasheet: https://uelectronics.com/wp-content/uploads/2018/04/MX1508_Datasheet.pdf

Read `VALIDATION.md`: this is a new test candidate, not a stable hardware release.

# TeleRC Mini Rover — v0.1.0 test candidate

Four TT geared DC motors + two MX1508 dual drivers + one ESP32-S3 DevKitC-1.
The ESP32-S3 is both the Wi-Fi endpoint and motor controller. No flight
controller, UART bridge, PWM converter, RadioLib, or MAVLink library is needed.

## Files

- `TeleRC_MiniRover/TeleRC_MiniRover.ino`: Arduino sketch; keep its three `.h` files beside it.
- `WIRING.md`: exact pin mapping, motor outputs, power, suppression, and BOM.
- `wiring.svg`, `wiring.png`: wiring overview with exact signal groups.
- `BENCH_TEST.md`: acceptance tests before ground operation.
- `VALIDATION.md`: what was tested and what still needs hardware verification.
- `tests/`: actual sketch simulation with Arduino/Wi-Fi API doubles.

## Upload

1. Disconnect motor power. Extract the ZIP fully.
2. Install **esp32 by Espressif Systems** in Arduino IDE Boards Manager.
   The source provides API branches for Arduino-ESP32 2.x and 3.x. The normal
   choice for a new installation is 3.x. No additional libraries are required.
3. Open `TeleRC_MiniRover/TeleRC_MiniRover.ino`. Select **ESP32S3 Dev Module**
   and the board's COM port. Match Flash Size / PSRAM to your module label;
   the sketch does not need PSRAM. For the native USB port use USB CDC On Boot
   enabled; for a USB-to-UART port choose the board's normal UART settings.
4. Upload. If necessary hold BOOT, press/release RESET, then release BOOT and
   retry upload. Do not hold BOOT during normal startup: it is also download mode.
5. Serial Monitor: **115200 baud**. Check AP startup and reset reason.
   Never disable brownout detection to hide a power fault.

## Connect PC TeleRC

| Setting | Value |
|---|---|
| Windows Wi-Fi SSID | `TeleRC-MiniRover` |
| Wi-Fi password | `telerc123` (editable in `Config.h`) |
| PC TeleRC transport | ESP32-S3 Wi-Fi / TeleRC UDP |
| Listen/bind address | `0.0.0.0` |
| Listen port | `14550` |
| Rover target address | `192.168.4.1` |
| Rover target port | `14550` |
| Steering RC channel | `CH1` |
| Drive RC channel | `CH2` |
| Vehicle system / component | `1 / 1` |

Allow the app through Windows Firewall for this Wi-Fi connection. Keep the
Wi-Fi connection when Windows says it has no internet. Close another app
using UDP 14550. Use a wheel/gamepad already calibrated in PC TeleRC.

The protocol was checked against `denberg28/PC-TeleRC` main on 2026-10-14 UTC:
`src/pctelerc/mavlink.py`, `transport.py`, `config.py`, and `field_safety.py`.
It uses `TELERC_DISCOVER_V1`, `TELERC_DISCONNECT_V1`, and MAVLink
RC overrides from source system/component **255/190**. This source snapshot
does not establish that every later portable EXE has identical behavior.

### Start driving: order matters

1. Lift the wheels clear of the bench. Center the steering and release pedals.
2. Connect PC TeleRC; wait for heartbeat / DISARMED.
3. Enable **PC Control** with steering and drive neutral. Wait at least **0.3 s**.
   The disarmed rover needs this neutral stream before accepting ARM.
4. Press **ARM**. Wait for the heartbeat to show ARMED, then apply a small input.
5. Disable PC Control to stop driving; press DISARM when finished. Before
   enabling control again, center both axes for 0.3 s.

If ARM is denied, enable PC Control while centered, wait 0.3 s, then press ARM
again. Do not force-arm. If a future PC build refuses to send neutral while
disarmed, it needs an app integration change; do not remove the rover interlock.

## Drive behavior

Forward: CH2 >1500 us; reverse: CH2 <1500 us. Right turn: CH1 >1500 us.
Centered CH1/CH2: 1500 us, with a +/-25 us deadband. Both left motors receive
the left demand; both right motors receive the right demand.

`left = drive + 0.5 * steer`, `right = drive - 0.5 * steer`. If either exceeds
1.0 in magnitude, both are divided by that same peak, preserving the ratio.
PWM magnitude = round(normalized demand * **180**), on a 0..255 scale.
Full steering at zero drive counter-rotates the sides. Check chassis clearance.

There is no long acceleration ramp. Direction changes coast for at least
**30 ms** before applying the opposite leg. Neutral, DISARM, disconnect,
timeout, and BOOT stop use **coast** (both inputs low), not a holding brake.
The rover can roll on a slope. A brake pedal/key works only through the
neutral/reverse behavior already implemented by your PC app; this sketch
does not add keyboard support to the EXE or interpret Space as a short brake.

## Configuration

Edit `Config.h`, then upload:

- `WIFI_SSID` / `WIFI_PASSWORD`: fixed in the sketch, no password entry webpage.
  Change the shared default password for normal use.
- `MOTOR_INVERT[4]`: correct individual wheel direction, ordered LF, LR, RF, RR.
  Alternatively swap that motor's two wires, with power disconnected.
- `MAX_PWM=180`: onboard output cap (~71% duty), **not current protection**.
- `STEER_GAIN=0.50`: independent onboard steering reduction.
- `STATUS_LED_PIN=21`: optional ordinary LED. Set to -1 if omitted. The board's
  RGB LED on GPIO38/48 is not used; it is not a normal LED.

For a first wheels-up trial use PC throttle limit **25%**, steer sensitivity
**50%**, drive sensitivity **100%**. The app's gains multiply the onboard limits.
At very low duty a TT motor may hum without starting. If directions and current
are correct, raise the PC throttle limit gradually toward 50%; do not add a
large automatic start pulse. Match speed to the chassis and motor voltage.

## Stop and recovery logic

- Boot/reset: disarmed, outputs off; no automatic enable or arm.
- Valid CH1+CH2 commands must keep arriving. No fresh drive frame for **500 ms**
  disarms and coasts, even if Wi-Fi discovery and GCS heartbeats still arrive.
- Wi-Fi station gone, explicit disconnect, or peer lease expired (3 s): disarm
  and coast. Reconnect requires neutral and explicit ARM again.
- RC release (`0` on either motion channel): coast immediately and inhibit drive.
  It preserves armed state, matching PC Control OFF separate from DISARM.
  A new continuous neutral stream for 250 ms is needed before movement resumes.
- During operation hold BOOT to stop/disarm. Releasing it does not restart motors.
  BOOT is a software stop, not a hardware emergency power cut.
- Bad CRC, wrong sender/target, out-of-range RC, oversized packets, or missing
  motion channels are rejected. They never refresh the control watchdog.
  A single malformed frame does not trigger a long neutral recovery pause.
- New peers cannot take over an active endpoint lease. Maximum one Wi-Fi station.

MAVLink 1 and unsigned MAVLink 2 are accepted for the listed command subset.
Telemetry is MAVLink 1 heartbeat + command ACK. The heartbeat truthfully says
generic ground rover; PC TeleRC may display a generic mode name. No GPS,
autopilot, navigation, return-to-home, battery sensing, current sensing,
RC receiver takeover, or camera stream is provided. Signed MAVLink is rejected;
CRC and source ID checks are not cryptographic authentication. Wi-Fi access
control is the link's authentication boundary.

## Engineering limits

The 500 ms stop is a cooperative firmware deadline, not a measured physical
stop time. Motor update is nominally every 5 ms. Network scheduling and task
blocking need bench verification; a hung CPU can leave hardware PWM active
until reset. A motor-power switch is required for immediate physical isolation.
Thermal driver shutdown is not a firmware reset; the serial reset reason and
5 V rail measurement help distinguish them. A capacitor cannot fix an
undersized supply, motor stall current, or poor ground routing.

This is a new **test candidate**, not a stable hardware-validated release.
Read `BENCH_TEST.md` before ground operation.

## References

- PC source: https://github.com/Denberg28/PC-TeleRC
- MAVLink common definitions: https://mavlink.io/en/messages/common.html
- Espressif LEDC API (S3 has eight PWM channels): https://docs.espressif.com/projects/arduino-esp32/en/latest/api/ledc.html
- ESP32-S3 DevKitC-1 power and pins: https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.1.html
- MX1508 IC datasheet reproduction, pp.1-3 (ratings and truth table): https://uelectronics.com/wp-content/uploads/2018/04/MX1508_Datasheet.pdf

Confirm your module's markings and pin labels. MX1508 and MAX1508 are different
parts; MAX1508 is not the H-bridge used here.

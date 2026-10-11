# TeleRC PWM glitch-filter test candidate 1.0.1

Based on the user's October 10, 2026 `Pasted markdown(3).md`, not a new Wi-Fi bridge firmware. Flash ONLY the separate ESP32-S3 PWM converter connected to FC M5-M8 and BTS7960 RPWM/LPWM. Flashing this onto the Wi-Fi bridge will replace that bridge.

## Change

Previously every invalid falling-edge sample cleared pulse validity, and the next 5 ms control update stopped all four motors. The candidate discards out-of-range pulses and unmatched falling edges without changing the last valid pulse width or timestamp. The last valid command can remain active for less than 150 ms. No valid pulse for 150 ms on any input stops all motors at the next control update (nominally up to 5 ms later). Continuing invalid pulses cannot postpone this stop. Startup still requires valid input on all four channels; after a stop, valid neutral inputs must persist for 300 ms before movement can resume.

Pin assignments, direction configuration, acceleration/deceleration steps, PWM frequency, output cap, and FC parameters are unchanged to isolate this issue. The source's Markdown escapes and excess blank lines were removed to create a compilable `.ino`.

This filters malformed pulse widths, not every possible noise waveform. Noise producing a width within 850-2150 us is still accepted. Continuous noise will still stop the converter. Fix persistent wiring/power noise rather than lengthening the timeout. No software brownout protection was disabled.

## Diagnostics at 115200 baud

- `bad=a,b,c,d`: rejected falling-edge counts for GPIO4/5/6/7 since boot.
- `stops`: number of transitions from enabled operation to an input-timeout stop; not repeated control-loop ticks or normal neutral commands.
- `up`: milliseconds since boot (wraps after approximately 49.7 days). It dropping back near zero can indicate a reboot, provided Serial Monitor did not itself reset the board.
- `reset`: numeric `esp_reset_reason()` captured at startup. Interpret with the installed ESP-IDF version. A reset reason alone does not establish the electrical cause.
- `*`: last valid pulse remains fresh; `!`: never valid or expired. An isolated rejection can increase `bad` while `*` remains displayed.

## Bench check

1. Extract ZIP and open the `.ino` inside its matching sketch folder in Arduino IDE. Select the exact ESP32-S3 board preset, Hardware CDC/JTAG USB mode and USB CDC on boot. This package contains source, not a precompiled firmware binary.
2. Verify motor mapping with wheels raised before testing. This sketch labels M5=front left, M6=rear left, M7=front right, M8=rear right. The reviewed parameter file instead assigns Left/Right/Left/Right (73/74/73/74). If physical wiring follows the sketch labels, M6 must be left (73) and M7 right (74). Do not assume labels match actual wiring. No parameter changes are applied by this package.
3. Have a physical motor cutoff available. Do initial checks with wheels raised and avoid deliberate stalls. Move steer and drive together while recording diagnostics.
4. If `bad` increases while `source=enabled`, `stops` stays unchanged and uptime continues, isolated malformed inputs are being rejected successfully.
5. With motor power removed, verify loss of any required FC PWM input stops all outputs; valid non-neutral input must not resume operation until all inputs return neutral for 300 ms.
6. If stops continue with no rejected pulses, investigate bridge neutral hold, FC mode/failsafe, and driver protection. If boot text reappears or uptime resets during motor load, investigate power integrity. This candidate cannot repair a supply-voltage brownout.

## Validation

Ten host checks passed for each Arduino API branch (2 and 3), executing the actual candidate ISR, control loop and diagnostics with simulated GPIO/time/LEDC/Serial functions. AddressSanitizer and UndefinedBehaviorSanitizer enabled; leak checking disabled because this container cannot enumerate process threads for LeakSanitizer. Checks cover startup, isolated bad pulse and unmatched edge, invalid-stream timeout, non-neutral recovery inhibition, 300 ms neutral dwell, all-channel loss, timer rollover, invalid-only input, PWM initialization failure and diagnostics.

These checks validate software behavior with mocks; they are not an ESP32 target compile, timing measurement, electrical-noise test or hardware-in-the-loop test. Arduino CLI/toolchain is unavailable here. Compile in Arduino IDE and complete bench checks before operational use.

Reproduce host checks from the extracted folder:

```bash
g++ -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -DESP_ARDUINO_VERSION_MAJOR=3 -I tests tests/test_converter.cpp -o /tmp/telerc-pwm-tests
ASAN_OPTIONS=detect_leaks=0 /tmp/telerc-pwm-tests
```

Use `-DESP_ARDUINO_VERSION_MAJOR=2` to exercise the older API branch. Headers in `tests/` are host mocks and must not be copied into the Arduino sketch folder.

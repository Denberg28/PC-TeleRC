# Validation — v1.0.0-standard, 2026-10-15 UTC

Status: **standard source baseline; hardware acceptance pending**. No physical rover/receiver was available.

## Host checks

`bash tests/run_tests.sh` compiles and runs the actual sketch/ISR with Arduino, GPIO interrupts, clocks, UDP, Wi-Fi and LEDC API doubles. All **20 combinations** pass: five drivers × two/four motors × Arduino core 2/3 API branches. Build uses C++17, `-Wall -Wextra -Werror`, AddressSanitizer and UndefinedBehaviorSanitizer. LeakSanitizer is disabled. No sanitizer finding in the completed runs. Raw output: `tests/RESULTS.txt`.

Verified behaviors:

- Profile-specific global coast, one side coast while the other drives, safe TB wake, active-channel budget and partial LEDC allocation failure.
- Duplicate/conflicting/reserved output pins rejected before output initialization; per-motor caps bounded.
- Six compile-time rejection cases: invalid driver/count/frequency, driver overvoltage, motor overvoltage, unacknowledged BTS logic interface.
- Real ISR pulse capture and microsecond wrap; missing required CH5/CH6; malformed pulse rejection.
- Startup/held-ARM lock, centered dwell and explicit fresh OFF→ON edge; rejected nonneutral edge cannot arm later.
- TX/PC handover stops and disarms; no automatic source fallback.
- PC release/DISARM/disconnect/Wi-Fi loss cannot interrupt healthy selected TX; radio is usable without Wi-Fi.
- Independent PC 500 ms drive timeout; discovery/radio traffic cannot keep PC drive alive.
- Radio ARM OFF, BOOT, PC neutral/release and Wi-Fi loss stop their intended owner.
- Reversal coast, no simultaneous active opposite PWM legs, timer wrap and 10,201 bounded mixer combinations per run.
- Independent bitwise CRC comparison, malformed/trailing/wrong-peer/wrong-target packet rejection, MAVLink 2 truncation/signing rejection.
- 50,000 deterministic malformed frame inputs per configuration (1,000,000 across the matrix).

Host doubles verify requested GPIO/PWM states; they do not measure transistor behavior, electronics timing or the receiver RF link.

## Actual target builds

Repository workflow `.github/workflows/mini-rover-standard.yml` uses Arduino CLI and the actual ESP32-S3 toolchain (`esp32:esp32:esp32s3`), not the host doubles. Matrix: all five driver profiles with four motors and MX1508 with two motors on core **3.3.12**, plus default MX1508/four motors on **2.0.17**. The enclosing release's `TARGET_BUILD.md` records run/commit/results and memory figures. No other board target or full target cross-product is claimed.

Only source and checksums are bundled; no prebuilt `.bin`. Binary artifact upload is optional because the account's GitHub artifact storage quota has previously been full. A missing upload is separate from compile/test results.

## Hardware acceptance remains open

Upload to exact board, PWM voltage, power-up/reset levels, radio failsafe OFF/return, simultaneous startup current, motor rail sag/overshoot, driver temperature, current capacity, PC wheel integration, interrupt/load timing, Wi-Fi range and physical coast distance require `BENCH_TEST.md`. Keyboard input is not added or tested by this firmware.

Ordinary receiver PWM has no RF-loss flag. Repeated held-last pulses can look healthy; mandatory failsafe CH1/CH2 center, CH5 OFF, CH6 STOP must be programmed and physically verified. Software timeouts are cooperative thresholds; blocked code/CPU failure can delay output changes. Compile success is not hardware qualification.

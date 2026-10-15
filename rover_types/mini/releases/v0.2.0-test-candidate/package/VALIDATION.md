# Validation at packaging — 2026-10-15 Asia/Manila

Status: **v0.2.0 FS-iA6 test candidate**. No physical radio or rover available.

## Completed host checks

The actual `.ino` and actual PWM ISR/capture code run in a host C++ executable
with Arduino, interrupt, time, Wi-Fi and PWM API doubles. Synthetic rising and
falling edges exercise capture; pulse input is not bypassed by injecting decoded
channel values. Both Arduino-ESP32 API branches (2.x and 3.x) pass.

Compilation: `-std=c++17 -Wall -Wextra -Werror`, AddressSanitizer and
UndefinedBehaviorSanitizer. LeakSanitizer is disabled due to this host's process
inspection restrictions. No ASan/UBSan finding in the completed runs.

Verified:

- Startup/held ARM lock, neutral dwell and explicit OFF->ON arm edge.
- No delayed auto-arm after a nonneutral ARM attempt.
- Actual ISR capture and unsigned microsecond wrap handling.
- One bad pulse ignored; missing CH5/CH6 causes receiver timeout and disarm.
- Configured STOP failsafe and RF-return simulation do not auto-arm.
- TX/PC source handover disarms and needs fresh authorization.
- PC commands/disconnect/Wi-Fi loss do not interrupt healthy selected TX.
- Radio remains usable when Wi-Fi is disabled; Wi-Fi errors do not grant PC permission.
- PC RC watchdog remains independent of radio/discovery freshness.
- Radio ARM OFF, BOOT, neutral/release and PC Wi-Fi loss stop their intended owner.
- Direction-reversal coast, both PWM legs never simultaneously active in exercised cases.
- Millisecond wrap, 10,201 mixer combinations bounded to MAX_PWM.
- CRC against independent bitwise reference; MAVLink 2 truncation and signing rejection.
- 50,000 deterministic malformed packet inputs per API branch.

Run `bash tests/run_tests.sh`; results are in `tests/RESULTS.txt`.

## Target build and hardware limits

Local Arduino CLI/ESP32 cross-toolchain is unavailable, and the local attempt
to reach Arduino's download host timed out. A repository Actions workflow is
added to compile ESP32-S3 using pinned Espressif cores **2.0.17 / 3.3.12** and
run host tests. Its outcome was **pending at ZIP packaging**; consult the
sub-release's external build record/Actions result for later target-build evidence.

No physical FS-iA6 pulse voltage, exact failsafe timing, receiver hold behavior,
S3 upload, interrupt timing under RF/Wi-Fi load, MX1508 temperature/current,
voltage sag, PC wheel test, keyboard test, range or stopping distance is verified.
The source ZIP has no compiled `.bin`; successful CI builds publish binary
artifacts separately. Target compilation does not establish hardware readiness.

Important architectural limit: ordinary PWM has no RF-loss flag. Valid repeated
held-last pulses cannot be distinguished from real control. Program and test
CH5 OFF + CH6 STOP failsafe. The watchdog only detects missing/invalid pulses.
Timeouts are cooperative and can be delayed by blocked code or a hung CPU.

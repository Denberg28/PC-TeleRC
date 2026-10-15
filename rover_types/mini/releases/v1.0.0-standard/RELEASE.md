# Mini rover v1.0.0-standard

Standard source release for ESP32-S3 mini rovers with two/four individually driven brushed DC motors, left/right skid steering, FS-iA6 PWM and PC TeleRC Wi-Fi. Default is the original four TT motors / two MX1508 boards. PC application version remains unchanged.

- [Complete source / wiring ZIP](archives/TeleRC-MiniRover-v1.0.0-standard.zip)
- [Setup](package/README.md) · [Wiring](package/WIRING.md) · [Diagram](package/wiring.png)
- [Driver profiles and scaling](package/HARDWARE_PROFILES.md) · [Review](package/REVIEW.md)
- [Radio failsafe](package/RADIO_SETUP.md) · [Bench acceptance](package/BENCH_TEST.md)
- [Automated evidence](package/VALIDATION.md) · [Target build record](TARGET_BUILD.md)

Supported driver interfaces: MX1508, DRV8833, TB6612FNG, paired-BTS7960 modules and L298N modules. Choose one family per build and wire its required enable/sleep/standby pins. Two motors use LF/RF physical slots. Driver changes are compile-time configuration, never automatic runtime detection.

The previous fixed-driver sketch was not interchangeable across these inputs. This version adds the output backend, safe coast truth tables, pin/channel checks, declared voltage guards and per-motor polarity/trim/caps while preserving explicit arming and ownership. Read REVIEW.md for the compatibility decision.

## Maturity and limits

**Standard source baseline, hardware acceptance pending.** Host safety matrix and actual target compilation establish software evidence only. No exact physical board upload, signal voltage, radio failure, startup current, thermal, range or mechanical stopping tests are claimed. Bench checklist is unfilled.

No encoder feedback, current limiting, acceleration ramp, battery cutoff, active holding brake, BLDC/ESC, servo steering or balance support. Larger motors need independently sized power electronics and measured stopping behavior; reducing duty does not replace correct voltage or current protection. Ordinary FS-iA6 PWM requires configured and verified CH5 OFF + CH6 STOP RF failsafe; held-last valid pulses can defeat missing-pulse detection.

FS-iA6 remains required even in PC mode. Keyboard support is not added by firmware. The release includes no Windows EXE or prebuilt binary and does not create an app-version tag. Prior version directories remain unchanged.

`release.json` contains archive/source identity and SHA-256; `package/SHA256SUMS.txt` covers package contents. Extracted archive content matches package/.

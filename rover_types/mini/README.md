# Mini rover

ESP32-S3 + four TT geared motors + two MX1508 dual drivers. Four driven wheels
with left/right skid steering; no flight controller is needed.

**Current:** [v0.2.0 FS-iA6 test candidate](releases/v0.2.0-test-candidate/RELEASE.md).

## FS-iA6 + PC TeleRC build

- [Download sketch and wiring ZIP](releases/v0.2.0-test-candidate/archives/TeleRC-MiniRover-FS-iA6-v0.2.0-sketch-and-wiring.zip)
- [Setup / upload](releases/v0.2.0-test-candidate/package/README.md)
- [Receiver and motor wiring](releases/v0.2.0-test-candidate/package/WIRING.md)
- [Wiring diagram](releases/v0.2.0-test-candidate/package/wiring.png)
- [Radio assignment and mandatory failsafe](releases/v0.2.0-test-candidate/package/RADIO_SETUP.md)
- [Arduino sketch](releases/v0.2.0-test-candidate/package/TeleRC_MiniRover/TeleRC_MiniRover.ino)
- [Bench acceptance](releases/v0.2.0-test-candidate/package/BENCH_TEST.md)
- [Validation at packaging](releases/v0.2.0-test-candidate/package/VALIDATION.md)

FS-iA6 PWM: CH1 -> GPIO12, CH2 -> GPIO13, CH5 -> GPIO14, CH6 -> GPIO15.
CH5 is ARM; CH6 selects TX / STOP / PC. The radio receiver is required even in
PC mode. Configure explicit CH5 OFF + CH6 STOP receiver failsafe and verify
transmitter-off behavior. Check receiver signal voltage before direct GPIO wiring.

TX start: CH5 OFF -> CH6 TX -> centered 0.4 s -> CH5 ON. For PC mode,
select PC with CH5 OFF, center 0.4 s, then CH5 ON; enable PC Control centered
for 0.3 s and explicitly ARM from the app. Source changes disarm.

Connection: `TeleRC-MiniRover`, rover target `192.168.4.1:14550`, CH1 steering /
CH2 drive. A public demo password is in Config.h; replace it for normal use.
PC keyboard capability requires implementation/testing in the Windows app.
No EXE/input implementation is changed by this firmware release.

## Previous Wi-Fi-only candidate

[v0.1.0-test-candidate](releases/v0.1.0-test-candidate/RELEASE.md) remains
preserved unchanged for the earlier receiver-free Wi-Fi-only architecture.
Use its own wiring and arming guide; do not mix source versions.

## Evolution

Complete exact-board upload, signal-level, receiver failsafe, current/voltage,
thermal and PC integration tests before any stable promotion. Subsequent
firmware/wiring changes receive independent versioned snapshots.

# Mini rover

First documented build: ESP32-S3 + 4 TT geared DC motors + 2 MX1508 dual drivers,
direct Wi-Fi connection to PC TeleRC. Four driven wheels, left/right skid steering.

**Current:** [v0.1.0-test-candidate](releases/v0.1.0-test-candidate/RELEASE.md).
Host-simulated; actual ESP32 compilation and hardware testing remain pending.

## Start here

- [Download sketch and wiring ZIP](releases/v0.1.0-test-candidate/archives/TeleRC-MiniRover-v0.1.0-sketch-and-wiring.zip)
- [Setup / connection](releases/v0.1.0-test-candidate/package/README.md)
- [Wiring and power](releases/v0.1.0-test-candidate/package/WIRING.md)
- [Wiring diagram](releases/v0.1.0-test-candidate/package/wiring.png)
- [Arduino sketch](releases/v0.1.0-test-candidate/package/TeleRC_MiniRover/TeleRC_MiniRover.ino)
- [Bench checklist](releases/v0.1.0-test-candidate/package/BENCH_TEST.md)
- [Validation limits](releases/v0.1.0-test-candidate/package/VALIDATION.md)

Connection: Wi-Fi AP `TeleRC-MiniRover`, rover target `192.168.4.1:14550`, CH1
steering / CH2 drive. The package contains a public demonstration Wi-Fi password;
set your own in `Config.h` before normal operation and never commit a private key.

Startup: centered controls -> Connect -> PC Control ON -> wait 0.3 s -> ARM.
This differs from the main app README's ArduRover example: the mini requires a
fresh centered RC stream before ARM. Follow the mini guide for this vehicle.

Wheel/pedal commands use the inspected PC TeleRC wire contract; physical PXN
interoperability still needs testing. Keyboard support depends on the Windows
app and is not added or verified by this sub-release. Stop is coast, not a
holding brake. Timeout/link loss disarms; reconnect cannot automatically arm.

## Evolution backlog

1. Complete `BENCH_TEST.md` on the exact parts and record measurements.
2. Verify PC wheel control and keyboard control as separate acceptance cases.
3. Add voltage/current/encoder telemetry only when sensors and pins are selected.
4. Evaluate driver upgrades from measured overload or thermal evidence.
5. Create new versioned snapshots for behavioral/hardware changes.

This file is a navigation and planning wrapper; the original candidate snapshot
is preserved unchanged under `releases/`.

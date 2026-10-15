# Mini rover

**Current:** [v1.0.0-standard source release](releases/v1.0.0-standard/RELEASE.md).
ESP32-S3, two/four brushed DC motors, left/right skid steering, FS-iA6 PWM and PC TeleRC Wi-Fi. Default: four TT motors and two MX1508 boards. Hardware acceptance is pending.

- [Download complete sketch and wiring ZIP](releases/v1.0.0-standard/archives/TeleRC-MiniRover-v1.0.0-standard.zip)
- [Choose hardware and upload](releases/v1.0.0-standard/package/README.md)
- [Five driver interfaces and scaling](releases/v1.0.0-standard/package/HARDWARE_PROFILES.md)
- [Wiring by profile](releases/v1.0.0-standard/package/WIRING.md)
- [Default wiring diagram](releases/v1.0.0-standard/package/wiring.png)
- [Versatility review](releases/v1.0.0-standard/package/REVIEW.md)
- [Radio / mandatory failsafe](releases/v1.0.0-standard/package/RADIO_SETUP.md)
- [Bench checklist](releases/v1.0.0-standard/package/BENCH_TEST.md)
- [Target build evidence](releases/v1.0.0-standard/TARGET_BUILD.md)

Change driver/count/voltage declarations and pins in `HardwareProfile.h`; set polarity, reducing trim and duty caps in `Config.h`. Supported interfaces: MX1508, DRV8833, TB6612FNG, paired-BTS7960 modules and L298N modules. Two-motor builds use LF/RF slots. No automatic identification, current control or closed-loop speed regulation.

FS-iA6 requires CH1→GPIO12 steering, CH2→GPIO13 centered drive, CH5→GPIO14 ARM and CH6→GPIO15 TX/STOP/PC. Receiver is required even in PC mode; confirm signal levels and configure failsafe CH1/CH2 center, CH5 OFF, CH6 STOP. Test transmitter OFF/return physically.

TX start: CH5 OFF, CH6 TX, centered 0.4 s, then CH5 ON. PC: CH5 OFF, select PC, centered 0.4 s, CH5 ON grants permission; stream fresh PC neutral 0.3 s and explicitly ARM in the app. Source changes disarm. Full procedure is in the package.

Wi-Fi `TeleRC-MiniRover`, target `192.168.4.1:14550`, CH1 steering / CH2 drive. Change demonstration password in Config.h. PC wheel uses the existing protocol; keyboard handling needs implementation/verification in the PC app. This release changes no Windows EXE or app version.

## Preserved releases

- [v0.2.0 FS-iA6 test candidate](releases/v0.2.0-test-candidate/RELEASE.md): original fixed four-MX1508/TT radio build.
- [v0.1.0 Wi-Fi-only candidate](releases/v0.1.0-test-candidate/RELEASE.md): earlier receiver-free architecture.

Use the wiring and operating instructions shipped with each version. The standard is a reviewed source baseline, not completed hardware qualification. Different motor voltage/current, module logic and higher-inertia stopping behavior require new measurements and acceptance.

# TeleRC dropout review candidate

Read `REVIEW-DROPOUTS.md` first. The saved FC parameters conflict with the converter's documented motor-side wiring. The conditional two-value parameter patch must match your physical wiring; do not import it blindly.

## PC source overlay — 0.1.1rc4

This is an overlay for the previously delivered **portable 0.1.1rc3** package, not a standalone installer.

1. Close PC TeleRC and make a separate copy of the complete rc3 portable folder.
2. Copy this archive's `pc-app-overlay/app/pctelerc` folder over `app/pctelerc` in that copy.
3. Keep the existing `PC-TeleRC.exe` and `runtime` beside `app`. Launch that EXE and confirm **0.1.1rc4** in its title.
4. To roll back, close it and launch your untouched rc3 copy. Calibration/settings remain in the existing PC data folder.

The overlay does not apply to a PyInstaller-only installer or a10 folder. Full Python source and regression tests are in `source`. Source tests ran on Linux; Windows native launch remains unverified.

## Sketches

- Bridge ESP32: `source/firmware/TeleRCBridge/TeleRCBridge.ino` — v0.1.4. For your Wi-Fi setup leave `TELERC_LINK_MODE=0`. SSID `TeleRC-Rover`, password `telerc123`. FC TX/T3 to GPIO18; FC RX/R3 from GPIO17.
- PWM converter ESP32: `source/firmware/TeleRC_4x_BTS7960_PWM_GlitchFilter/TeleRC_4x_BTS7960_PWM_GlitchFilter.ino` — v1.0.4. Existing pins and responsive ramp retained. New persistent fault fields identify M5–M8 signal loss and loop gaps.
- These are Arduino source sketches, not compiled flash images. Use your actual ESP32-S3 board preset. Serial Monitor 115200. Disconnect motor power while flashing.

After a stop, save PC Diagnostics and both ESP serial logs before reconnecting. Center steering and release pedals for at least half a second; then manually re-enable PC Control. Do not disable the failsafes to suppress the symptom.

Test evidence: 112 application tests, nine firmware host configurations. Actual rover dropout, native Windows execution and ESP32 target compilation remain unverified.

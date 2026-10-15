# Changes

## 0.2.0 FS-iA6 test candidate — 2026-10-15 Asia/Manila

- Four individual PWM captures on GPIO12/13/14/15 for FS-iA6 CH1/CH2/CH5/CH6.
- TX / STOP / PC selector with 80 ms settling and disarm on source change.
- Neutral-first, OFF->ON radio ARM permission; high-at-startup and delayed auto-arm rejected.
- 120 ms required-channel freshness watchdog; single malformed pulse tolerance.
- Mandatory receiver-side CH5 OFF + CH6 STOP failsafe and documented RF-hold limitation.
- Receiver permission required in PC mode; original PC 500 ms RC watchdog retained.
- PC session changes do not interrupt selected TX; Wi-Fi startup failure leaves TX available.
- Motor wiring, skid mixer, MAX_PWM, steering gain and reversal coast retained.
- Updated wiring/power/buffer guide, radio setup, bench checklist and ISR-driven tests.
- Added pinned ESP32-S3 compile workflow; no Windows app version or input implementation change.

## 0.1.0 test candidate

Previous Wi-Fi-only mini baseline remains preserved in its original sub-release.

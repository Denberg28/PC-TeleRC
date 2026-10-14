# Changes

## 0.1.0 test candidate — 2026-10-14 UTC / 2026-10-15 Manila

- New standalone ESP32-S3 Wi-Fi motor controller for four TT motors and two MX1508 drivers.
- PC TeleRC discovery/disconnect, CH1 steering, CH2 drive, generic rover heartbeat and arm/disarm ACK.
- Eight independent 20 kHz PWM outputs; configurable motor inversion and output/steering limits.
- Explicit neutral-first arming, 500 ms RC watchdog, peer lock, Wi-Fi loss stop, and BOOT stop.
- No long acceleration softening; 30 ms direction-reversal coast interval.
- Full wiring, power/noise suppression, BOM, benchmark checklist and host simulation suite.

No PC application or earlier rover bridge sketch was modified.

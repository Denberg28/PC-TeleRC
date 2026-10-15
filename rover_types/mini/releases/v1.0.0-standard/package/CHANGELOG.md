# Changelog

## 1.0.0-standard — 2026-10-15

- Separate driver/motor hardware profile from source ownership and mixing.
- Support 2/4 individual brushed motor channels and MX1508, DRV8833, TB6612FNG, BTS7960 module, L298N interfaces.
- Driver-specific coast, enables, sleep wake, pin validation and partial-PWM-setup fault handling.
- Voltage declarations with compile-time limits; reducing per-motor trim, duty cap and inversion.
- Full host safety matrix, fault injection, invalid-configuration rejection and ESP32-S3 target CI.
- Preserve FS-iA6 CH1/2/5/6 requirements, explicit neutral arming and PC isolation.
- Package wiring, compatibility review, setup and unfilled bench acceptance record.

Prior releases remain independently archived. This vehicle release does not change the PC app version or add keyboard/ELRS support.

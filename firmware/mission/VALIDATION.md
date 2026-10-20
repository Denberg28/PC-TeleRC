# LoRa Mission 0.2.0rc1 validation

See ../../docs/evidence/mission-v0.1.5rc2/VALIDATION.md and MISSION-REVIEW-015.md.

13 actual-code host profiles pass normally and under ASan/UBSan; 8 Python tests
pass. All four BASE/ROVER/NODE_1/NODE_2 actual ESP32-S3 targets compile and link on
ESP32 Arduino 3.3.2 and RadioLib 7.2.1. Shipped sketch headers match those compiled.
Public examples remain keyless/RF OFF. Private test binaries and keys are excluded.
Image hashes identify ephemeral test fixtures, not ready-to-flash operational images.

PC client mission semantics pass real Rover 4.6.3 SITL, including integer-coordinate
readback, START and planned ON/OFF arrival windows. This is not a physical RF test.
Physical commissioning and independent cutoff acceptance in HARDWARE_TEST.md remain
required. No stable, measured range or stopping-distance claim is made.

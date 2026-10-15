# Mini v0.2.0 FS-iA6 test candidate

New firmware candidate, 2026-10-15 Asia/Manila. Adds **individual FlySky FS-iA6
PWM input** to the standalone ESP32-S3 mini rover while retaining PC TeleRC Wi-Fi.

[Download sketch and wiring ZIP](archives/TeleRC-MiniRover-FS-iA6-v0.2.0-sketch-and-wiring.zip)

| Item | Value |
|---|---|
| Release ID | `rover-mini-v0.2.0-test-candidate` |
| Firmware version string | `0.2.0-test-candidate-fsia6` |
| Motor hardware | Four TT motors, two MX1508 dual drivers |
| Receiver | FS-iA6, CH1/CH2/CH5/CH6 PWM on GPIO12/13/14/15 |
| Source selection | CH6: TX / STOP / PC; transition stops/disarms |
| ARM | CH5 OFF->ON after neutral dwell; PC also needs explicit MAVLink ARM |
| Receiver watchdog | 120 ms for missing valid pulses on any required channel |
| PC RC watchdog | 500 ms, independent of healthy radio/discovery |
| PC app | Unchanged; keyboard implementation not added |
| Hardware validation | Pending; no stable promotion |

ZIP SHA-256: `5cf83b16af8b5e08d421be0267fad00699a1d771b6f50cfb5035633fe8d2aaa1`.

See [setup](package/README.md), [wiring](package/WIRING.md),
[radio/failsafe](package/RADIO_SETUP.md), [bench checklist](package/BENCH_TEST.md),
and [validation at packaging](package/VALIDATION.md).

Both sources require a healthy receiver and physical radio authorization.
Configure receiver failsafe **CH5 OFF + CH6 STOP**, steering/drive centered.
PWM has no RF-loss flag; held-last PWM cannot be detected as radio failure.
Stops coast, not hold. Signal-level checks and motor-power isolation are required.

Host simulation with real ISR edge capture passes under both LEDC API branches.
A dedicated Actions workflow compiles the actual ESP32-S3 target using pinned
cores 2.0.17 and 3.3.12; its result is separate from package-time host evidence.
No compiled binary is embedded in the source ZIP. The workflow publishes binaries
as build artifacts when successful. No Git release tag or Windows release is made.

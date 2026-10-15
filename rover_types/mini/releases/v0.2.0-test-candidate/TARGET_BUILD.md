# Actual ESP32-S3 build evidence

Source commit: `eedfa9713f2332cfba7bdc63d3022bf8d9816963`.

[GitHub Actions run 38657826368](https://github.com/Denberg28/PC-TeleRC/actions/runs/38657826368)
compiled the actual `esp32:esp32:esp32s3` target using Arduino CLI, not API doubles.

| Check | Result | Program storage | Static RAM |
|---|---|---:|---:|
| Host ISR/network/safety suite | PASS | N/A | N/A |
| Espressif core 2.0.17 target compile | PASS | 697,905 bytes / 1,310,720 | 45,840 bytes / 327,680 |
| Espressif core 3.3.12 target compile | PASS | 892,292 bytes / 1,310,720 | 47,344 bytes / 327,680 |

The 3.3.12 compiler emits two deprecation warnings for incrementing volatile
capture counters. Those increments occur under the ISR spinlock; compilation
succeeds. These are recorded rather than represented as a warning-free build.

Both compile jobs subsequently failed **only at binary artifact upload**:
GitHub reported `Artifact storage quota has been hit`. No binary artifact was
retained from that run. Source ZIP and wiring remain downloadable in this
repository. The workflow now treats the artifact-upload step as optional while
keeping compilation failures fatal. No existing artifacts were deleted.

The final documentation/workflow follow-up does not change firmware, tests or
the ZIP represented by this evidence. Package-level `VALIDATION.md` correctly
records the earlier pending status at packaging; this file records the later
actual target-compilation result. The original ZIP checksum remains unchanged.

No physical board upload, receiver signal level, RF failsafe behavior, motor
current/thermal test or ground validation has been performed. Successful
compilation is not a stable/hardware-validated release claim.

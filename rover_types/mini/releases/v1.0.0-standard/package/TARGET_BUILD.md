# ESP32-S3 target build record — 2026-10-15 UTC

Source commit: `9a8a52ca3b01ab95bfbc2ab88e4027b890885b9e`.
Workflow: https://github.com/Denberg28/PC-TeleRC/actions/runs/38659722284

All eight jobs passed: host matrix plus seven actual target builds.
The packaged executable source/tests match the source commit; subsequent packaging commits add documentation and archives.

| Core | Driver ID | Motor count | Flash bytes | Static RAM bytes | Compile |
|---|---:|---:|---:|---:|---|
| 3.3.12 | 3 | 4 | 893324 | 47360 | PASS |
| 3.3.12 | 1 | 2 | 893376 | 47360 | PASS |
| 3.3.12 | 2 | 4 | 893356 | 47360 | PASS |
| 3.3.12 | 5 | 4 | 893144 | 47360 | PASS |
| 2.0.17 | 1 | 4 | 698829 | 45856 | PASS |
| 3.3.12 | 4 | 4 | 893276 | 47360 | PASS |
| 3.3.12 | 1 | 4 | 893184 | 47360 | PASS |

Target FQBN: `esp32:esp32:esp32s3`. Driver IDs: 1 MX1508, 2 DRV8833, 3 TB6612FNG, 4 BTS7960-module, 5 L298N-module. All target builds use default 5 V/6 V-rated declarations except BTS: 12 V supply/motor declarations and logic verification acknowledgement. These values are compile settings, not tested motor specifications.

Host CI passes all 20 driver/count/API combinations and six invalid-configuration cases with ASan/UBSan. Compiler logs contain no project warning in these completed builds. The two/four motor cross-product for every driver is host tested; actual target matrix is exactly the table above.

Binary upload was attempted separately and is nonblocking. Account artifact-storage quota blocked new uploads; compile/test jobs still passed. No binary is bundled or represented as available. The source ZIP is committed with this release.

Hardware qualification remains pending: target compilation is not upload to a particular physical board, receiver failsafe testing, current/thermal characterization or mechanical stopping validation. See BENCH_TEST.md.

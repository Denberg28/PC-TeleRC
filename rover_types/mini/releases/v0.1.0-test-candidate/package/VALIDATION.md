# Validation — 2026-10-14 UTC

Status: **v0.1.0 test candidate**. No physical rover or radio was available.

## Completed

The actual `.ino` is compiled into a C++17 host executable with controlled
Arduino, Wi-Fi, and PWM API doubles. Both Arduino-ESP32 major API branches
(2.x channel writes and 3.x pin writes) pass. This verifies the source's use of
the simulated API contract; it is not an ESP32 compiler or SDK validation.

`bash tests/run_tests.sh` uses `-Wall -Wextra -Werror`, AddressSanitizer and
UndefinedBehaviorSanitizer. LeakSanitizer is disabled because this execution
environment disallows its process inspection. No ASan/UBSan findings occurred.

Verified behaviors:

- Startup disarmed and all eight PWM duties zero.
- Discovery required, local IP/port and source-ID checks, peer lock and expiry.
- Wrong target, bad CRC, trailing invalid bytes and ignored motion channels
  cannot refresh drive freshness.
- Neutral dwell before ARM; nonneutral and force-arm rejection.
- Full drive, steering differential, 10,201 steering/drive input combinations
  bounded to the configured PWM limit.
- Neutral/release stops immediately and requires neutral recovery.
- Command timeout disarms even with discovery still arriving.
- Wi-Fi station loss and explicit disconnect stop/disarm.
- BOOT stop cannot resume on release alone.
- Reversal coast interval and opposite-leg PWM exclusion in exercised cases.
- Millisecond timer wraparound and exact timeout boundary in the control core.
- Unsigned MAVLink2 zero-truncation, target-component broadcast, actual v2
  command dispatch, concatenated v1 frames, and signed-frame rejection.
- Outgoing heartbeat/ACK layout and CRC checked with an independent bitwise
  X.25 reference implementation.
- 50,000 deterministic malformed inputs per API branch under sanitizers.

Compatibility reference: PC TeleRC default branch files retrieved via GitHub:

| File | Retrieved blob SHA |
|---|---|
| `src/pctelerc/transport.py` | `ae0a469a7119a7be67716807fbfd21e5d24f81b3` |
| `AGENTS.md` | `a5485b605b2f067c7445c695a2dc27e6502d1f6b` |

`mavlink.py`, `config.py`, `field_safety.py` were also read for discovery,
source IDs, CH1/CH2 mapping, ARM command construction and neutral prerequisites.
No PC application source was changed or EXE rebuilt.

## Not completed

- Actual ESP32-S3 cross-compilation: Arduino CLI, ESP32 SDK and Xtensa toolchain
  are not installed in this environment. Upload must be compiled in Arduino IDE.
- Flash/upload, exact board variant, actual PWM frequency/levels, radio latency,
  packet-loss tolerance, Windows EXE interoperability and neutral-first ARM flow.
- Motor direction, voltage sag, startup/stall/load current, driver thermal
  performance, physical stopping distance, range, or ground testing.

No compiled `.bin` is included and no stable hardware-readiness claim is made.
Use `BENCH_TEST.md` as the hardware acceptance gate.

# 0.1.5rc2 / Mission 0.2.0rc1 qualification

- Full application regression: **247 passed**; includes 32 focused mission tests.
- Firmware Python/protocol-peer checks: **8 passed**.
- Actual Runtime/Protocol/Crypto host profiles: **13 passed**; direct, one-node and
  two-node roles plus four keyless examples. The same **13 pass ASan/UBSan**.
  Leak detection is disabled for this runtime; no physical RF is simulated by stubs.
- Actual ESP32-S3 compilation/link/image generation: **BASE, ROVER, NODE_1, NODE_2
  all pass** on Arduino ESP32 3.3.2 / RadioLib 7.2.1, manufacturer SX1262 4 MB /
  PSRAM-off / hardware CDC profile. Compiled headers match shipped canonical headers.
  Test private profiles and binaries are not distributed.
- Real **ArduRover 4.6.3 SITL** at source revision
  `3fc7011a7d3dc047cbb17d8bd98ee94577d144c6`: exact upload/readback, explicit simulation
  arming with ordinary FC checks, one-shot START/ACK/AUTO, servo9 ON/OFF near the
  reviewed arrival points at <=0.2 m/s reported speed, and confirmed HOLD **pass**.
  This tests FC mission semantics over local TCP, not the physical USB/LoRa link.
- Offscreen UI/media self-test: **23 checks pass**, including actual video decode,
  maps, logo, authority locks, mission codec and close cleanup. Small-window
  expanded panels are also inspected and tested; inputs retain normal height.
- Compileall and focused undefined-name/unused-import lint pass. Publish tests:
  **13 passed**. Updated Python files formatted with Ruff.
- Native Windows/frozen execution is not locally qualified. Earlier GitHub Windows
  job failed before steps. Wine fallback is blocked by the runtime's Unix socket
  restriction. A Windows build is requested from the committed candidate workflow;
  its actual outcome must be checked before claiming an executable release.
- **Physical RF, USB/FC wiring, power, RC takeover, loss/stop timing, stop distance
  and independent accessory cutoff are NOT TESTED. Stable promotion remains gated.**

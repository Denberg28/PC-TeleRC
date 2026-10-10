# Verification — TeleRC Mesh 0.1.1

Evidence applies to the source packaged with this document. No hardware is connected to this build environment.

| Gate | Result | Evidence / limit |
|---|---|---|
| Source and protocol review | PASS | PC UDP source/port and MAVLink 1 envelope checked; T3-S3 V1.2/V1.3 SX1262 pins checked against manufacturer documentation. No PC application source changed. |
| Actual target build | PASS | Arduino CLI 1.3.1, ESP32 Arduino 3.3.2, RadioLib 7.2.1; `esp32:esp32:lilygo_t3s3:CDCOnBoot=cdc,Revision=Radio_SX1262,PSRAM=enabled`. |
| Host core regression | PASS | Packet authentication and corruption/wrong-key rejection; hop budget; duplicate cache; challenge freshness and one-use consumption; millis rollover; startup neutral fence; independent CH1/CH2 expiry; sparse mailbox expiry and no retransmission; parser framing. |
| Host actual-sketch regression | PASS | Includes the actual `.ino` against peripheral stubs: rejects initial drive; stop then neutral/release; backpressure stop retry; monitor-only behavior; real-FC heartbeat requirement; framed motor GENERIC heartbeat; release + DISARM preservation; challenge replay/late direct response; relay forwarding; asynchronous CAD defer/free transitions; direct TX-completion poll anchor and pending-challenge guard; late-response TX drop; two missed representative direct refreshes and three-miss stop latch; RF receive restart failure; setup profile/authentication validation. |
| Direct timing/loss model | PASS | 500,000 input events and 100,000 sessions per loss setting; direct profile read from the actual header. Fixed-seed Monte Carlo and independent-loss analytical reference; representative mean delay 135 ms, P95 200 ms, 7.76 Hz. This is model evidence, not measured RF/HIL. |
| ASan / UBSan | PASS | Same host checks under address/undefined-behavior sanitizers; leak detection disabled because this environment's process tracing prevents LeakSanitizer operation. |
| Packaging | PASS | Source, wiring/setup guide, build image and SHA256 manifest. Binary validation is compile/packaging evidence, not an upload or boot test. |
| PC executable installation / wheel / Wi-Fi | NOT TESTED | No Windows PC/PXN wheel or LilyGO connected. v0.1.0a10 wire envelope reviewed; actual executable compatibility remains a bench gate. |
| Flash / boot / portal on device | NOT TESTED | Actual board compile passed; native USB, portal/login and NVS persistence still need device tests. |
| FC / TeleRC motor paired operation | NOT TESTED | UART format and software stubs verified. Existing downstream motor/FC firmware not rebuilt or changed. |
| RF mesh / range / hidden nodes | NOT TESTED | No radio measurements. Multi-hop airtime and collisions remain physical validation gates. |
| Physical stopping / takeover / brownout | BLOCKED | Requires the user's rover hardware and restrained-wheel measurements described in README. |
| Stable promotion | BLOCKED | Hardware/installation/paired compatibility gates remain open. This is a bench-test candidate. |

The existing PC Windows release workflow is unchanged. The separate mesh CI job tests and uploads firmware artifacts without publishing a release. Results above are local; any remote workflow result must be inspected separately.

Run from repository root:

```bash
bridge/tests/run_mesh.sh
ASAN_OPTIONS=detect_leaks=0 SANITIZE=1 bridge/tests/run_mesh.sh
python3 bridge/simulation/simulate_direct.py --output bridge/simulation/results
arduino-cli compile --fqbn esp32:esp32:lilygo_t3s3:CDCOnBoot=cdc,Revision=Radio_SX1262,PSRAM=enabled --output-dir build-mesh bridge/TeleRCMesh
```

Actual target build: 997,247 bytes flash (76%), 50,408 bytes static RAM (15%). Boosted receive gain setup compiles for the real target; gain benefit and current remain unmeasured.

Next check: flash gateway and rover with 0.1.1, select one radio leg on both (existing stored profiles retain their setting), confirm actual FC/motor heartbeat and neutral enable/ARM, then measure input latency, channel gaps and last-axis-to-stop interval before adding relay boards. Preserve settings with ordinary sketch upload; merged factory flash clears NVS.

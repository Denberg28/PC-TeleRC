# Direct-pair optimization simulation — TeleRC Mesh 0.1.1

Topology: PC over Wi-Fi/UDP -> T3-S3 SX1262 gateway -> direct LoRa -> T3-S3 SX1262 rover -> 115200 baud UART. No relays. USB is used for gateway power/programming/logs; this firmware's control path is Wi-Fi.

## Reproduce

```bash
python3 -m pip install -r bridge/simulation/requirements.txt
python3 bridge/simulation/simulate_direct.py --output bridge/simulation/results
```

Tested with Python 3.12.14, numpy 2.3.5 and matplotlib 3.10.8. The script reads the direct/relay timing profile from `bridge/TeleRCMesh/MeshCore.h`. Seed 20261011, 500,000 operator input events per profile, 100,000 one-minute sessions per loss setting. Results are in `results/`: CSV tables, JSON summary and comparison chart. Simulation does not operate hardware, flash devices or change firmware.

## Comparison

| Quantity | Before | Optimized direct |
|---|---:|---:|
| Poll wait after poll TX completion | 370 ms | 100 ms |
| Response acceptance window after poll TX completion | 350 ms | 90 ms |
| Representative control cycle | 399 ms | 129 ms |
| Updates per second | 2.51 | 7.76 |
| Mean operator input to UART-completion delay | 272 ms | 135 ms |
| 95th percentile delay | 452 ms | 200 ms |
| 99th percentile delay | 477 ms | 214 ms |
| Clear-link modeled RF occupancy | 15.1% | 45.4% |
| Sessions stopped within 60 s at 1% independent packet loss | 95.1% | 0.343% |

The independent-loss analytical reference for the optimized 1% case is about 0.356%. Monte Carlo comparisons are checked against that reference with sampling tolerance. A zero observed count at 0.1% loss is not a guarantee: the analytical stop probability is about 0.000368% for a one-minute session under this model.

The 500 ms deadline and nonneutral recovery rejection are preserved. In the deterministic trace, two lost direct exchanges are followed by a fresh command before timeout. Three consecutive losses are followed by a stop and rejection of later nonneutral traffic. This is representative of the modeled 129 ms cycle; contention, response variation and larger payloads reduce that margin. At 5% packet loss, about 32% of optimized one-minute sessions still stop.

## Modeling assumptions

- SF7, BW500 kHz, CR4:5, explicit header, CRC on, preamble 8. Mesh overhead 40 bytes. Airtime is calculated with the equation used by the installed RadioLib 7.2.1 SX126x implementation, and known 57-/67-byte reference values are checked (26.944/30.784 ms).
- Representative poll length 57 bytes (17-byte MAVLink heartbeat plus envelope); response 67 bytes for RC or 85 bytes with GCS heartbeat. GCS heartbeat occurrence is approximately one per second, so its bundling probability changes with polling rate.
- PC produces RC at 20 Hz. Input event waits uniformly 0–50 ms for a host tick; Wi-Fi delivery uniformly 2–10 ms; clear-channel CAD at each radio uniformly 1–3 ms; gateway processing uniformly 0.5–1.5 ms; response deferral 3 ms. These are assumptions, not measured hardware timings.
- Input arrival phase is uniform within the representative poll cycle. Clear-link delay is for successful exchanges and ends after sending the 26-byte UART RC frame. It excludes flight-controller/motor processing and physical motion.
- The loss experiment uses the fixed mean representative cycle and independent loss on both RF transmissions. It assumes fresh PC commands and FC heartbeat, successful UART writes, and both axes owned after an initial centered start. It retains the stop latch and does not auto-recover. It does not couple distance to loss probability.
- Radio busy backoff, hidden-node collisions, correlated fading, variable telemetry scheduling, operating-system stalls, cryptographic/interrupt costs beyond assumed processing, brownouts and electrical noise are not simulated. A late congested response can be dropped by the firmware even without RF decoding loss.
- Maximum 136-byte packets take 56.384 ms; with 3 ms CAD the direct cycle becomes 159.384 ms. The representative 7.76 Hz result is not a guaranteed update rate with all payloads.
- Timing optimization changes no TX-power, frequency, spreading-factor or antenna default. Boosted RX gain is enabled in firmware, but the simulation assigns it no unmeasured sensitivity/range benefit. Faster polling increases airtime and requires real channel/operating-rule checks for the selected installation.

## Range scenarios retained from the previous model

915 MHz; assumed 2 dBi antennas at each end; 2 dB combined feed/implementation loss; assumed unmeasured receive threshold -114 dBm; require 10 dB reserve. Log-distance path loss: free-space loss at 1 m (~31.68 dB) + 10*n*log10(distance in metres) + extra loss. Chosen scenario inputs: open n=2.5/0 dB extra; low antennas/vegetation n=3/6 dB extra; built-up n=3.5/12 dB extra. Antenna heights, ground reflection, Fresnel clearance and actual terrain are not resolved.

| Chosen scenario | 2 dBm default | 10 dBm | 17 dBm |
|---|---:|---:|---:|
| Open, good antenna clearance | 1.13 km | 2.36 km | 4.50 km |
| Low antennas / vegetation | 221 m | 408 m | 698 m |
| Built-up / obstructions | 69 m | 117 m | 185 m |

These values are examples, not maximum range specifications or assurances about a site. Power examples do not establish permitted operating settings. Over 5 km propagation alone is approximately 0.0167 ms, so reception loss and scheduling dominate this model.

## Firmware verification and remaining gates

The actual `.ino` host regression exercises direct scheduling at TX completion, pending challenge protection, late-response rejection, late TX suppression, watchdog expiry, centered restart, existing relay behavior and other existing safety checks. Address/undefined-behavior sanitizer checks pass. The actual T3-S3 SX1262 target compiles with the pinned ESP32 Arduino 3.3.2/RadioLib 7.2.1 toolchain.

Field validation remains required: flash both boards and set radio legs to one, record actual input/UART latency and accepted-axis gaps, test gateway/Wi-Fi/RF loss, restrain wheels and measure stop behavior and receiver takeover. Previously saved three-leg profiles retain their slower timing until explicitly changed. A firmware stop means a neutral/release request, not demonstrated motor shutdown or hardware power cutoff. The result is a bench-test candidate; no stable promotion is implied.

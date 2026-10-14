# LilyGO 0.5.0 / PC TeleRC 0.1.2rc2 — sketch pairing, screen sleep and relays

Edit the settings at the top of each `.ino` before uploading. Keep every adjacent header with the sketch. The downloadable templates have an empty password; they do not contain a shared public driving password.

```cpp
#define TELERC_LORA_PASSWORD ""          // replace with your private 8-character password
#define TELERC_LORA_FREQUENCY_KHZ 915000 // example only; use your hardware/permitted band
#define TELERC_LORA_POWER_DBM 2
#define TELERC_RELAY_COUNT 1             // match BASE, ROVER and all NODEs
#define TELERC_TRANSPORT_WIFI 0          // ROVER initial default: LoRa; saved BOOT mode wins
#define TELERC_NODE_INDEX 1              // NODE position; index 1 is nearest BASE
```

Use the same exactly eight visible ASCII characters (case sensitive; no spaces), frequency and relay count on BASE, ROVER and all NODEs. A non-empty sketch password takes precedence over saved pairing on every boot. Old NVS cannot silently replace it. Web/USB pairing writes are locked in this case; change the sketch and upload again to change pairing. Password validation fails compilation for the wrong length/characters. The eight-character derivation matches the preceding PC/web setup, so existing same-password installations retain the same key.

An empty password retains the saved pairing workflow; blank unconfigured boards keep LoRa OFF. Compiled pairing is not automatically written to NVS, so returning to an empty sketch password restores any older saved pairing. Your custom password is embedded in your sketch and firmware image: keep those custom files private. No password is printed to USB or shown on the OLED.

ROVER remains capable of Wi-Fi or LoRa; a previously saved BOOT mode overrides its initial default. Select LoRa in the BOOT menu when using the relay chain. BASE remains native USB-to-LoRa. NODEs need only regulated power and a matching antenna; no FC UART or PC connection in operation. Upgrade BASE and ROVER to 0.5.0 for relay operation. Direct mode (relay count 0) keeps compatibility with the preceding direct protocol.

## Choose the shortest required chain

| Relay count on all boards | Position from PC to rover | NODE sketch settings |
|---|---|---|
| 0 | BASE → ROVER | No NODE needed |
| 1 | BASE → NODE 1 → ROVER | One NODE: index 1 |
| 2 | BASE → NODE 1 → NODE 2 → ROVER | First NODE index 1; second index 2 |

Upload `firmware/TeleRCLoRa_BASE/TeleRCLoRa_BASE.ino` to BASE, `TeleRCLoRa_ROVER.ino` to ROVER, and `firmware/TeleRCLoRa_NODE/TeleRCLoRa_NODE.ino` to each relay after changing its index. NODE indices are unique positions: do not install two nodes with the same index. Count 1 is the smallest relay configuration and adds the least delay. Count 2 is for a path that needs two relays. All participants must agree on count; mismatched settings fail closed. With relays enabled, the configured chain is required; it does not automatically bypass a missing node.

Place nodes where both adjacent links are reliable, preferably elevated with suitable antennas and clear line of sight. A node beside BASE does not extend a path it cannot itself reach. Actual range, placement and fade margin need measurement; no distance claim is made.

## Screen and BOOT

The onboard SSD1306 turns off after 30 seconds without button activity. Radio, UART, control and the existing watchdogs continue running. This is display sleep, not MCU sleep. While asleep, firmware stops display I2C traffic. GPIO37 link indication remains independent.

Tap BOOT to wake. The first complete press, even if held, wakes only; it does not enter setup or stop PC control. Release it, then hold for one second to intentionally enter the setup menu. While awake, tap advances and hold selects as before. Screens also time out in menus/setup; waking preserves the current page. Holding BOOT during reset still invokes the ESP ROM downloader. Missing/faulty OLED output never gates the control link.

Entering the setup menu stops/releases owned PC overrides. Exiting/changing mode retains the preceding 16-second setup pause and manual neutral re-enable behavior. Screen wake alone adds no pause.

## Delay and fail-safe design

- Ordered forwarding rather than flooding. A node authenticates the expected sender, origin, direction, hop count and shared key; forwards that token once; and never writes motor/FC UART commands.
- Fixed SF7 / BW500 kHz / CR4:5 / preamble 8 / sync 0x12, boosted RX. Two-ms forwarding turnaround, asynchronous CAD and bounded busy-channel deferral. No delivery retries, blocking radio sends, old-command regeneration or duplicate flooding.
- BASE coalesces the newest fresh USB command after CAD, immediately before TX. Per-axis mailbox lifetime stays 200 ms; stale/ignored axes do not become fresh.
- The 100 ms poll interval is a minimum spacing after poll TX, not a fixed additional wait after a successful relay response. An outstanding challenge prevents overlap. Reply deadlines are 90/220/360 ms for direct/one/two relays. After a valid reply the next exchange can start as soon as spacing permits. Lost replies expire; their tokens cannot be replayed to renew control.
- RF queues still expire after 100 ms per forwarding stage. The endpoint rejects replies beyond its original challenge window. CH1/CH2 command loss remains 500 ms and FC heartbeat expiry remains 2.5 s. Neutral acquisition, explicit ARM, receiver takeover and UART stop retries are retained. More nodes add airtime and reduce tolerance for lost packets; they cannot guarantee better control on a congested channel.

The clear-channel host model compiles isolated instances of the actual driver and uses RadioLib 7.2.1 SF7/BW500 airtime, two-ms CAD, one-ms loops and adjacent-only reception. In an eight-second outage/recovery scenario, delivered newest-sample-to-UART latency was approximately 62/106/146 ms mean and 83/128/167 ms p95 for zero/one/two relays. These numbers describe delivered samples after coalescing, not every wheel event, physical hardware latency or a guarantee. Lost samples, contention, USB/FC timing and electrical/RF faults can increase delay or cause deliberate stops.

## Builds and checks

Use Arduino ESP32 core 3.3.2, RadioLib 7.2.1, LilyGo T3-S3 SX1262 revision, USB CDC On Boot enabled and QSPI PSRAM. Keep erase disabled for saved settings. FC wiring is unchanged: GPIO44 RX ← FC T3, GPIO43 TX → FC R3, 115200 MAVLink2, common ground; OLED uses GPIO18/17. PWM converter 1.0.5 and original ESP32 bridge 0.1.5 are unchanged.

Release target groups include BASE direct/relay1/relay2, ROVER Wi-Fi/direct-LoRa/relay1/relay2 and NODE one-relay/node1-two-relay/node2-two-relay, plus the original PWM/Wi-Fi/ELRS targets. Prebuilt images use an empty sketch password and saved/web pairing; a custom sketch password requires compiling your edited copy. Choose matching relay-count profiles across the installation.

Host checks cover 30-second screen OFF and I2C idle, wake-only first gesture during active control, intentional second hold, timer rollover, compiled password overriding NVS, invalid-password compilation failure, setup write lock, all three authenticated chains, node power-cycle outage, 500 ms stop, displaced-input recovery rejection, neutral reacquisition, mismatched key rejection, late/replayed responses and NODE UART isolation. Hardware/RF range, actual OLED power draw, UART/motor stop latency and receiver takeover still require bench validation with wheels raised and a reachable motor cutoff before ground use. This remains a draft candidate; v0.1.1 remains Latest.

Reproduce from repo root: `python3 firmware/runtime-tests/run_tests.py`, `python3 firmware/relay-tests/run_tests.py`, existing firmware test runners and `python -m pytest -q`.

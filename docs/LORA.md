# Native LoRa control — PC TeleRC 0.1.0a14

The Windows app uses the existing TeleRC v0.8.53 firmware and USB protocol. No separate relay process, UDP loopback port or Meshtastic installation is needed. This is TeleRC motor control over LoRa, not the Meshtastic mesh protocol.

## Hardware path

PXN wheel → PC TeleRC → native USB → LilyGO T3-S3 **BASE** → LoRa → T3-S3 **ROVER** → UART → dedicated ESP32-S3 **TeleRCMotorController** → four BTS7960 drivers.

Keep the motor controller separate from the communications radios. The standalone BTS7960PWMConverter does not accept the gateway's joystick commands. Match the actual SX1262 or SX1276 board profile; SX1280 is unsupported. The rover gateway remains interchangeable with the existing Wi-Fi gateway through the documented motor UART/expansion interface.

Firmware baseline: [TeleRC v0.8.53](https://github.com/Denberg28/TeleRC/releases/tag/v0.8.53), commit `0f7272da0d30b398dfe13c0a1008afca93f24c5c`. See its [wiring guide](https://github.com/Denberg28/TeleRC/blob/v0.8.53/bridge/LORA_INTEGRATION.md) and [swappable gateway guide](https://github.com/Denberg28/TeleRC/blob/v0.8.53/bridge/SWAPPABLE_GATEWAYS.md). Existing firmware is unchanged by this PC build.

## Provision blank boards

1. Disconnect motor power. Flash each board with its matching BASE/ROVER firmware and radio profile.
2. Open **LoRa Setup**, connect one board using its native ESP32-S3 USB port, select its COM port, and click **Open USB**. Opening setup closes the driving connection. An automatic local read shows role, chip, radio status, frequency, power, key fingerprint and counters.
3. Enter a frequency matching your radio hardware and permitted installation band. No frequency is preselected. Start at 2 dBm for bench testing.
4. Click **Generate** once for a random 32-byte key. The key is masked; **Show/Hide** changes visibility. It stays in memory only, never in settings, logs or diagnostics. Do not generate a second key for the partner board.
5. **Save to board** is available only after a valid read of an inactive radio. Wait for `Saved`, close USB, and restart that board.
6. Connect the partner board. Use the same frequency, power and key, save, close USB, and restart. Reading an already configured board may populate its frequency/power: verify your intended draft before saving. A 16-bit fingerprint helps identify mistakes, but does not prove that keys match.
7. A timeout blocks further exchanges until USB is closed/reopened. A late reply cannot confirm another save. Active radios cannot be re-paired through USB: disconnect motor power, erase the board's NVS, and reflash the blank firmware first.

Closing the app clears its key field. To configure a partner in another session, enter your separately retained key; the app cannot read a key back from a board.

## Drive

1. Plug the **BASE** native USB into the PC. Use **Link Setup → Connection → LoRa · LilyGO USB**, select/enter the COM port, then **Apply & Connect**. Setup USB closes before the driving port opens. The app checks the board role and active radio before sending discovery/control traffic.
2. Wait for a fresh rover heartbeat. A working local USB connection alone does not count as a rover connection.
3. Use **Controller** to select and calibrate the wheel/pedals. Keep steering on **CH1**, drive on **CH2**. Other LoRa channel pairs block enable/ARM.
4. Set the physical motor controller selector to **DIRECT**. Return to **Drive**, center the wheel, release the pedals, and click **Enable PC Control**. Allow the motor controller's neutral source dwell to complete and wait for **DIRECT** status.
5. Click **ARM** explicitly. The app sends neutral before ARM. ACK/rejection/timeout and heartbeat confirmation are shown; there is no automatic retry or automatic arm. Check that the rover confirms ARMED before driving.
6. Steering and drive sensitivity are independent (25–100%); the independent throttle limit defaults to 25%. Applying/editing settings disables control.
7. **STOP** remains visible on all pages. It disables PC control and sends neutral/release. **DISARM** is explicit. Page changes disable control. Disconnect closes the port and stops heartbeats. Reconnect requires a new heartbeat, fresh input and manual enable/ARM.

## Protocol and safety limits

- Native USB CDC: 115200, DTR asserted, RTS low. Use the native USB port; this mode is not for reset-wired USB/UART adapters or raw MAVLink serial radios.
- USB datagram: `A5 5A`, little-endian 16-bit length (1–280), payload, CRC16-CCITT of length+payload. Incomplete frames expire after 20 ms. CRC failures, invalid lengths and non-MAVLink status text cannot refresh vehicle heartbeat.
- Outbound commands are MAVLink 1, system 255/component 190, addressed to motor system 1/component 1. Complete accepted telemetry frames may be MAVLink 1/2. Only a ground-rover heartbeat from system 1/component 1 can establish LoRa vehicle identity.
- PC input ticks are 20 Hz. The existing radios poll at about 10 Hz and coalesce latest commands; the app does not increase over-air packet rate. USB writes have bounded waiting and failures latch control OFF. USB delivery is not an over-air acknowledgement.
- Local stale controller/worker checks remain active (default controller timeout 350 ms); PC heartbeat timeout defaults to 3 s. The dedicated motor firmware independently provides its 500 ms command watchdog, replay/stale rejection, neutral source transfer and hard-stop behavior. Measured motor stopping time remains unverified.
- No automatic Wi-Fi/LoRa switching. Choose one gateway/control source and reconnect explicitly. RC/FC takeover still requires the documented hardware selector/firmware workflow; PC LoRa does not claim ELRS/Pocket arbitration.

## Compatibility

| PC mode | Firmware / transport | Channels | Status |
| --- | --- | --- | --- |
| Wi-Fi · ESP32 | Existing TeleRC MAVLink 1 UDP bridge, UDP 14550 | Existing mapping, default CH1/CH2 | Preserved; regression-tested |
| LoRa · LilyGO USB | TeleRC v0.8.53 BASE + ROVER + TeleRCMotorController | CH1 steer / CH2 drive | Software-tested candidate; HIL pending |
| ELRS USB MAVLink | Compatible external TX/receiver, raw USB MAVLink 460800 | Existing mapping | Experimental; exact hardware unverified |

## Bench acceptance and rollback

With wheels lifted/restrained, verify both board roles, settings match, DIRECT handover, neutral enable, arm confirmation, gradual steering/drive, STOP, DISARM, page changes, exit, USB removal, rover-radio loss, motor-UART loss, controller removal, and reconnect with a held pedal. Measure actual stop latency; check that no queued command resumes movement after recovery. Repeat with the F405 selector path and transmitter takeover if installed. Check Windows PXN driver mode and axes. Range, RF interference, battery-load behavior, installed upgrade and these physical tests are NOT TESTED by CI.

Rollback: reinstall v0.1.0a13 and select its existing Wi-Fi path. Current PC calibration/settings identity is preserved; the added `lora_usb` mode is not understood by the old app, so reselect Wi-Fi and verify settings after downgrade. Firmware need not be changed for PC rollback. For a configured motor controller, retain an independently tested failsafe and emergency motor-power isolation.

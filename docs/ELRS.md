# ELRS USB workflow — v0.1.1rc2 candidate

Select **HGLRC T ONE 900 MHz · ELRS**, select the TX module's USB COM port, and click **Apply & Connect**. A COM port opening only proves that USB opened. Wait for an ArduRover heartbeat, verify wheel calibration and CH1/CH2 directions, release the pedals, ARM explicitly if needed, then enable PC Control. The app never arms or resumes control automatically.

## Setup

Use the module's data USB port and a data cable. Close Mission Planner or another program holding that COM port. Port refresh enumerates devices without opening them, preserves the selected device even if unplugged, and never selects an alternative automatically. Port descriptions appear as tooltips.

The TX and RX must support native ExpressLRS MAVLink mode. The official guide documents minimum TX/RX firmware 3.5.0 and different receiver configuration steps for ELRS v3 and v4. Bind the exact compatible hardware targets and follow that guide; the app does not flash or configure radios. The T ONE USB interface and exact GEPRC receiver target remain unverified physically.

For ArduPilot, the official guide specifies `SERIALx_PROTOCOL=2`, `SERIALx_BAUD=460`, and `RSSI_TYPE=5` on the receiver UART, with low telemetry stream rates. Check the correct UART for your board. These are receiver MAVLink settings, not the separate ESP32 Wi-Fi bridge's 115200-baud settings. TX and RX UART wiring must cross TX/RX and share ground according to their hardware manuals.

For standalone PC operation, validate TX USB → ELRS RF → RX UART → ArduRover with the handset disconnected first. Simultaneous Pocket stick traffic and PC MAVLink overrides require physical arbitration testing; this candidate provides no verified automatic RC6/Pocket takeover. Disable PC Control attempts neutral and release of CH1/CH2; release acceptance depends on FC settings and RF delivery.

## Reliability behavior

| Trigger | App action |
| --- | --- |
| USB opened, no heartbeat | Control and ARM remain inhibited; after 10 seconds show TX/RX/UART checks |
| Controller input stale/missing | Check at 20 Hz, latch PC Control OFF, attempt owned neutral/release |
| Heartbeat older than configured timeout | Latch OFF; fresh telemetry alone cannot re-enable |
| Worker gap exceeds controller timeout | Latch OFF even if the newest controller sample is fresh |
| USB output exceeds 64 bytes or remains nonempty for 100 ms | Stop session, latch active control OFF, require manual reconnect |
| USB input exceeds 8192 queued bytes | Stop session; reduce telemetry before reconnecting |
| Partial/failed drive or heartbeat USB write | Stop session, require manual reconnect |
| Disable PC Control | Clear the local USB output queue, then attempt three neutral/release pairs |
| Monitor-only disconnect | Close USB without sending RC overrides |
| DISARM during PC control | Disable/release first, then send explicit disarm request |
| Edit while reconnect timer is pending | Cancel connection; old callbacks cannot start another session |
| Apply Settings with a pending radio change | Save draft; ARM/control handlers stay blocked until reconnect |

ELRS sends the latest drive sample at 5 Hz and a GCS heartbeat at 1 Hz. Missed sends are not replayed as a catch-up burst. At MAVLink 1 framing this is approximately 147 bytes/s before shutdown/ARM traffic. The 20 Hz safety loop does not add normal RF command traffic. The 64-byte/100-ms queue limits are conservative local USB stall limits at 460800 baud, not measurements of RF capacity. The 8192-byte input limit prevents a large local backlog from masquerading as current telemetry.

Expected controller-loss detection is the configured 350 ms default plus a nominal safety-loop interval of 50 ms. OS scheduling, bounded serial writes and shutdown retries can extend this; it is not a guaranteed rover stop time. The FC must enforce its own override timeout/failsafe. USB queue clearing cannot remove packets already in the module, on the air, or at the receiver. Successful USB writes do not acknowledge vehicle delivery.

## Bench acceptance before powered driving

1. Lift the driven wheels. Verify calibrated neutral and commanded CH1/CH2 directions at a low throttle limit.
2. Run standalone USB, verify real ArduRover heartbeat, ARM explicitly and enable control. Measure response and record RF packet mode.
3. Unplug the wheel while driving gently; confirm the app latches OFF and measure physical stop time.
4. Remove TX USB, then test RF loss separately with hardware controls appropriate to the module. Confirm the FC stops within the chosen timeout. Reconnect must remain OFF.
5. Disable PC Control and verify CH1/CH2 release to the intended transmitter. Test RC6/Pocket takeover separately with neutral sticks and an independent stop method.
6. Test disconnect/reconnect and COM-port occupation by Mission Planner. The app must not silently select another device or resume control.

If any check fails, keep the candidate out of powered field operation and record the failing setup. Range, arbitration, RF queue latency and physical failsafe timing remain hardware validation items.

Official reference: [ExpressLRS MAVLink guide](https://www.expresslrs.org/software/mavlink/) (reviewed 2026-10-14).

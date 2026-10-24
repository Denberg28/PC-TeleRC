# PC TeleRC 1.1.0rc1 firmware support

Recommended firmware: TeleRC ArduRover baseline 1.1.0rc1, containing scalable
LoRa 0.4.0rc1 and ESP32-S3 four-BTS7960 PWM converter 1.0.5. The public archive
is included under `Firmware-baseline/`, with its original eleven-board-build
report, hashes, keyless examples, provisioner and wiring guide. Its bytes are
pinned to the verified release; this application update does not alter firmware.

Use your existing private 20-rover bundle for actual radio uploads. It retains
the matching BASE, rovers 001–020 and nodes 1–3. Do not flash public RF-OFF examples
over an operational private network. The converter sketch is the same on each
rover and runs on its separate ESP32-S3. No radio keys are stored in PC settings.

| Firmware set | Manual window | Mission window | Relay configuration |
| --- | --- | --- | --- |
| Scalable LoRa 0.4.0rc1, TU2 | Rover 1 only | Selected rover 1–20 | Automatic route discovery; at most 2 active hops |
| Unified LoRa 0.3.0rc1, TU1 | Rover 1 only | Selected rover 1–20 | Matching fixed relay IDs 1/2 |
| Older manual LoRa 1.0.1 | Existing manual workflow | Unsupported | Matching legacy set |
| Mission 0.2.0rc1, TM2 | Unsupported | Selected rover 1–20 | Matching fixed relay count |

Use one complete matching radio set and one active BASE. These radio protocols
cannot be mixed. The app recognizes the mission USB API separately from the
board version; scalable firmware still advertises `fw=0.2.0` for its TM2 USB API.
The detected board family/version appears in Mission. Unrecognized firmware or
changing capabilities fail closed before mission work is admitted.

## Connect and operate

1. Connect the provisioned BASE's native USB port, select LORA and its COM port.
   Main-window manual control is rover 1, FC SYSID_THISMAV=1. Start with neutral
   input, then deliberately enable PC Control. Opening a connection never arms.
2. For missions, open Mission, select the BASE COM port and matching rover/FC ID.
   Connecting closes manual ownership; one addressed rover is active at a time.
3. Plan offline, connect, wait for real addressed FC telemetry, upload disarmed,
   and verify full readback. Arm deliberately from RC and separately confirm Start.
   The scalable maximum-two-hop profile requires a verified GCS timeout of 7–10
   seconds for this mission workflow; the app reads FC parameters and never writes them.
4. If an established route is lost, rediscovered or changed, or the BASE reports
   an RF fault or discarded command, the app clears verification and closes the
   session. Inspect live FC state, reconnect and re-upload before another Start.
   No automatic reconnect, mission replay, ARM or START occurs.

Initial route discovery is expected and displayed as Finding rover. It does not
authorize actions. A successful USB write is not proof of RF delivery. HOLD remains
an explicit action; a missing ACK is UNKNOWN. FC loss policy and receiver takeover
remain independent. The converter's 150 ms input timeout/300 ms neutral recovery
and the radio manual 500 ms watchdog are unchanged.

## Expansion and qualification

Add NODE IDs 1–200 using the saved private network project; never duplicate a
physical ID. Existing firmware need not change when adding an unused identity.
Two hops is the path limit; 200 IDs is not a measured simultaneous-node capacity.
Twenty rover IDs do not mean simultaneous driving or live fleet monitoring.

Historical manual/TM2 firmware remains included for rollback in its own folders;
`FIRMWARE-COMPATIBILITY-v1.0.1.md` describes those older sets only. The new public
baseline is a release candidate. RF range, timing under real contention, motor
behavior, electrical reliability and RC takeover still require hardware testing.

# v0.1.0a11 versus v0.1.0a10 regression analysis

Date: 2026-10-03

The release introduced a confirmed controller polling failure. The heartbeat changes also introduced compatibility restrictions; the exact cause of the reported hardware connection failure remains unconfirmed without its received heartbeat or diagnostic log.

| Area | a10 | a11 | Assessment and correction |
| --- | --- | --- | --- |
| Wheel polling | No get_attached call | Calls JoystickType.get_attached every poll after acquisition | The pinned pygame-ce 2.5.8 has no such method. Every connected wheel falls into the exception path, repeatedly clears input and changes generation. Replace with JOYDEVICEREMOVED events matched by get_instance_id. |
| Heartbeat acquisition | Accepts non-GCS heartbeat and locks identity | Requires ground-rover type 10, ArduPilot autopilot 3, component 1 | Generic or boat heartbeats, and nonstandard components, are rejected. Restore broader acquisition while rejecting GCS, invalid autopilot, and reserved system IDs; keep first vehicle identity and UDP endpoint lock. The actual user's heartbeat header is not captured. |
| Bridge registration | No discovery packet | No discovery packet | Existing compatibility gap, not independently an a11 regression. Current TeleRCBridge.ino registers/refreshes its telemetry peer using TELERC_DISCOVER_V1; it does not accept MAVLink GCS heartbeat as a registration packet. Send discovery from the shared listener socket every second, to the configured/locked endpoint, or default AP 192.168.4.1 before acquisition. |
| UDP receive | pymavlink udpin server | Exclusive shared socket and pinned peer | Significant architectural change. Keep source identity checks, but hardware/Windows routing requires validation. Normal rover heartbeat over real localhost UDP, control, neutral/release, port reuse, and reconnect pass. |

The controller exception explains visible wheel glitches and PC Control being latched off by generation changes. It does not itself stop the independent MAVLink receive worker. Do not conflate those symptoms.

The bridge only accepts clients using UDP source port 14550 on its local AP subnet. Production configuration must retain listener port 14550 and the intended AP interface. The bridge may retain another client's pairing for five seconds. Discovery cannot bypass an active phone's pairing lease. Close Android TeleRC/Mission Planner listeners before testing the PC session. The bridge's broadcast fallback can deliver telemetry without discovery, so missing discovery alone does not prove why a10 worked and a11 failed.

## Verification

- Four added tests cover repeated controller sampling/removal, generic/boat/component heartbeat acquisition, exclusion of GCS/non-autopilot heartbeats, and discovery-triggered real UDP telemetry with repeated registration.
- Three targeted regression tests fail against the unmodified a11 modules and pass with these corrections.
- Full corrected local suite: 84 tests passed.
- Earlier 80 tests did not execute the controller polling loop with the pinned joystick API or model bridge discovery. Passing those tests was insufficient evidence of hardware compatibility.
- No physical PXN, ESP32, or flight-controller test was performed here. Windows CI and field validation must be checked separately.

No automatic arm or control enable is added. Reconnect still requires fresh heartbeat/input and manual PC Control enable. Steering sensitivity and neutral/release behavior remain covered by the existing suite.

For current hardware operation, use the known-working a10 until a corrected Windows build has been tested. No flight-controller parameter changes are justified by this diagnosis alone.

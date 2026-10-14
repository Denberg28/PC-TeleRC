# Bench acceptance tests

Record actual motor voltage, module markings, firmware version, PC EXE version,
motor current, minimum ESP32 5 V rail voltage, and each result. Begin with wheels
lifted and an accessible motor-power switch. Keep the chassis away from edges.

| Test | Procedure | Pass condition |
|---|---|---|
| Flash and power | Motor power off; upload and observe 115200 serial | Correct AP and no repeated resets |
| Startup protection | Power drivers while ESP32 disarmed; repeat reset | All four motors remain off; external pulldowns installed |
| Unplugged controller | With motor power off, unplug ESP32 while drivers remain powered | Driver inputs remain low through pulldowns |
| Connection | Join SSID; PC target 192.168.4.1:14550 | Heartbeat and DISARMED shown |
| Interlock | Click ARM before sending a neutral stream | ARM denied; no wheel movement |
| Neutral arm | Enable PC Control centered, wait 0.3 s, ARM | ARMED confirmed; still no movement |
| Forward/reverse | Very small drive with steering centered | All four physical wheels agree; stop before correcting polarity |
| Steering | Small steer alone, then steer + forward | Positive steer turns right; LF/LR agree and RF/RR agree |
| Disable | Disable PC Control while driving | Motor drive removed on neutral/release; no resume until 0.3 s centered stream |
| DISARM | DISARM while commanding drive | All outputs off; no movement until neutral + explicit ARM |
| Command timeout | Stop drive packets while discovery/heartbeat continue | Output drive removed ~500 ms after last valid RC frame; disarmed |
| Wi-Fi loss | Switch PC Wi-Fi off while commanding drive | Drive off on station-loss detection or command timeout; disarmed |
| Reconnect | Rejoin while pedal is held | No movement; release/center, enable control and ARM required |
| App close/crash | Test normal close, then terminate PC TeleRC | Neutral/release/disconnect on close; watchdog stop on crash |
| Reverse | Small forward then small reverse | Coast interval before opposite polarity; no supply reset |
| BOOT stop | Hold BOOT while driving, then release | Stops/disarms; release alone cannot resume |
| Sustained load | Light ground load and simultaneous steer/drive | No reset, input pause, excessive heating, or voltage collapse |

Measure command timeout at GPIO outputs using a logic analyzer or oscilloscope,
not by how long wheels take to roll to rest. The host test establishes logic,
not radio timing. To distinguish causes of a stop: a new serial boot/reset
reason suggests MCU reset; continuing logs with rising `fs` indicates firmware
failsafe; live PWM with a stopped hot driver suggests driver thermal protection.

The `ok` counter includes valid protocol events, not only drive commands.
`bad` counts rejected traffic; `fs` counts command or peer timeout events.
`armed` and `inhibit` show why output is permitted or blocked. Log messages
do not prove the physical motor terminals are at the expected voltage.

Before increasing speed, verify actual loaded current against each channel,
the supply rail during four-motor startup, and stop behavior. No claim of
range, terrain capability, reliable slope holding, or stable-release readiness
is made until these tests pass on your hardware.

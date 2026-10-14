# Field clarification and rc5 continuation

The user reports that the ground/bump stop clears after approximately three seconds once steering and pedals return to neutral, without manually re-enabling PC control. This matches neutral-gated bridge/converter recovery; it does not establish bridge overload or a measured brownout. The reported PC snapshot has HB0.9s/input0.032s and ACTIVE, so it does not capture the triggering event. The transmitter comparison remains ambiguous between powered/connected and transmitter-driven operation.

rc5 adds a direct SX1262 BASE-to-ROVER path to test the suspected Wi-Fi interruption and gives the PC authenticated rover stop/boot information. It retains the motor converter and existing safety thresholds. Hardware results are still required. The full rc4 review follows as historical baseline evidence.

# PC TeleRC — rapid steer/drive and bump dropout review

Date: 14 October 2026. Candidate: PC source 0.1.1rc4, bridge 0.1.4, PWM converter 1.0.4.

The strongest configuration finding is a mismatch between the saved motor-side assignments and the latest converter's documented wiring. The actual field dropout is **not yet reproduced on hardware**. Power interruption, loose connectors, driver protection and signal interruption remain possible. This package corrects confirmed PC workflow defects and adds evidence to identify the next stop; it is not a certified brownout cure.

## Reviewed baseline and scope

- Delivered `PC-TeleRC-portable-v0.1.1rc3.zip`, including its complete first-party Python source, UI, calibration, diagnostics, radio setup/transports, lifecycle and tests. Its metadata describes a reused rc2 Windows launcher/runtime, with no native Windows or hardware validation. Baseline tests: 104 passed.
- Latest saved `TeleRC-WiFi-Recovery-v0.1.3-test-candidate.zip`, version 3. It contains bridge code identifying itself as 0.1.2 and the responsive converter identifying itself as 1.0.3. These are the latest delivered firmware bytes, despite differing package/embedded version numbers.
- Repository `Denberg28/PC-TeleRC`, main snapshot `dff03ccc989c9a0d2826e6a48ee02f762b83fdcc`, file `stable_config/Base_Ardurover_4.6.3_11oct2026.param`. This is saved configuration evidence, not a download from the presently connected FC. GitHub main and the rc2 development branch are behind the delivered rc3 package for this work.
- No hardware connection, measured supply/current waveform, current FC parameter dump, native Windows launch, ESP32 target compilation, RF range test, or third-party dependency source audit was performed. LoRa firmware itself is outside these supplied bridge/converter files; the PC LoRa path and its existing tests were reviewed.

## 1. High priority: motor-side mapping conflict

The converter passes each FC input independently to its corresponding driver. It does not remap left/right internally. ArduRover output function 73 is Throttle Left; 74 is Throttle Right.

| FC output | ESP input | Driver outputs RPWM/LPWM | Motor named in sketch | Saved function | Required for named wiring |
|---|---|---|---|---:|---:|
| M5 / SERVO5 | GPIO4 | GPIO8 / GPIO9 | Front left | 73 | 73 |
| M6 / SERVO6 | GPIO5 | GPIO10 / GPIO11 | Rear left | 74 | **73** |
| M7 / SERVO7 | GPIO6 | GPIO12 / GPIO13 | Front right | 73 | **74** |
| M8 / SERVO8 | GPIO7 | GPIO14 / GPIO15 | Rear right | 74 | 74 |

If the physical wiring follows these motor names, a turn sends different commands to the front and rear motors on each side. A pivot can oppose motors on the same side. That can increase drivetrain load and supply sag. This is an engineering inference from the verified mapping conflict, not proof that it caused the observed event.

With motor power isolated, trace and label every driver. If the actual order is FL/RL/FR/RR, use `parameters/ONLY-FOR-FL-RL-FR-RR.param`, which changes only SERVO6_FUNCTION to 73 and SERVO7_FUNCTION to 74. If the physical order is FL/FR/RL/RR, the saved 73/74/73/74 mapping may already be correct: **do not apply that patch**. Do not swap wiring and parameters at the same time. Verify wheel rotation direction separately; physical mounting and motor lead polarity can require reversal.

## 2. Confirmed PC defects corrected

| Finding | Correction |
|---|---|
| Wi-Fi enable checked only throttle neutral, while the bridge requires every addressed channel near neutral | Require centered steering for Wi-Fi enable/ARM; reflect that prerequisite in UI/diagnostics. Active driving still allows full steering. |
| PC accepted CH5–CH8 even though the Wi-Fi bridge rejects addressed channels above CH4 | Reject incompatible Wi-Fi mapping before enabling control; ELRS channel support remains unchanged. |
| Wheel worker pumped SDL but never consumed its event queue and tracked only GUID | Consume the queue, process removal/addition, identify the live instance, and assign a connection session. Rapid event bursts cannot accumulate indefinitely. |
| A rapid remove/replug could occur entirely between control ticks | Compare the current wheel session with the session at manual enable. A new instance latches control off even when the disconnected snapshot was missed. |
| Non-finite axis values could be clamped into seemingly valid commands | Reject non-finite raw axes and invalid frames. |
| Stale input reporting omitted the measured age | Include input age/limit in the stop reason and current sample age/session in Copy Report. |

The rc3 direct worker-to-wheel snapshot fix is retained. No GUI timer is used to provide control input. No automatic arm or motion resumption is added. The wheel changes use `get_instance_id()` and documented events, not the unsupported `get_attached()` call associated with the earlier a11 regression.

These defects and regression tests demonstrate software failure paths. They do not establish that a rover bump disconnected the PC wheel.

## 3. Firmware findings and changes

The supplied converter already rejects isolated invalid pulses while retaining the last valid pulse for less than 150 ms. It does not stop on one rejected edge. All four channels must be fresh; one truly stale channel stops all motors. Recovery requires every channel within 1500 ±35 microseconds for 300 ms. Releasing only the pedal while the steering remains turned can therefore keep it in neutral-wait.

The bridge separately stops/releases owned channels after 500 ms without an accepted override. PC heartbeat freshness defaults to 3 seconds. Thus a brief uplink interruption can stop the bridge while PC telemetry remains connected. PC's displayed PWM values indicate transmitted requests, not confirmation that the FC or motors applied them. The bridge's ASCII status does not currently propagate its control latch into PC diagnostics. Capture the bridge USB diagnostics to distinguish this case.

The diagnostic sketches now preserve:

- Converter: last stop cause/time, stale-channel bit mask (1=M5, 2=M6, 4=M7, 8=M8; sums mean multiple channels), each channel's age at failure and the control-loop gap. These remain visible after neutral recovery until the next fault or reboot.
- Bridge: last active stop reason/time, command age when stopped, largest accepted-command gap, neutral-gate rejects and short UART writes. Existing uptime/reset/counters remain.
- Larger diagnostic buffers prevent the additional fields from suppressing complete lines. Output remains chunked through available USB capacity; it does not wait for a connected monitor.

Converter drive behavior is unchanged: 8 duty counts per 5 ms acceleration tick, approximately 160 ms to full duty; 12-count deceleration; reversal passes through zero and begins opposite drive on the next tick. There is no extra reversal dwell. These are duty slew limits, not measured current limiting. Genuine pulse/loop timeouts and brownout detection remain intact. Wi-Fi SSID/password, GPIO mapping and ELRS mode selection are retained.

## 4. Other saved parameter findings

| Saved setting | Implication for diagnosis |
|---|---|
| FS_CRASH_CHECK=0 | The saved configuration does not enable the Rover crash-check stop. This does not exclude EKF, RC, power, or wiring faults. |
| RC6_OPTION=46 | RC6 controls RC Override Enable. Observe RC6 during the event; preserve the transmitter takeover function. |
| RC_OVERRIDE_TIME=1 | The FC has another timeout layer, independent of the bridge and converter. |
| FS_GCS_ENABLE=0 | The saved file does not provide an enabled GCS-heartbeat failsafe. End-to-end loss/handover must be verified separately. No failsafe parameters were changed by this package. |
| MOT_SLEWRATE=85 | There is FC-side throttle slew as well as converter slew. The converter's 160 ms ramp is not a guarantee of total vehicle response time. |

## 5. Discriminating bench procedure

1. Verify the physical motor-side mapping first. Secure the rover with driven wheels clear and a reachable motor-power cutoff. At low output, confirm the two wheels on each side obey the same side command, and forward/reverse physical directions are correct.
2. Apply the PC source overlay only to a copy of the rc3 portable bundle. Confirm the title says 0.1.1rc4. Flash the converter/bridge diagnostic sketches to their respective ESP32 boards using the actual board presets. Keep bridge `TELERC_LINK_MODE=0` for Wi-Fi; mode 1 is only the existing native-MAVLink ELRS UART relay, not ordinary CRSF support.
3. Start serial captures before the test. Opening a serial port can reset some boards, and USB power can mask a weak UBEC supply. Note whether USB changes the power arrangement. Do not connect two independent 5 V outputs together.
4. With motor power off and logic powered, repeat rapid simultaneous steer/drive input for one minute. This isolates command handling from motor load. Capture PC Diagnostics and both sketch logs if a fault occurs.
5. Repeat with wheels lifted at low duty. Gently flex/inspect suspect connectors with motor power isolated first; do not deliberately stall or crash the rover. If unloaded tests pass but normal ground load fails, inspect the battery/UBEC/driver paths and measure the affected board's supply during an event. A scope captures short dips a handheld meter may miss.
6. At the next stop, copy PC Diagnostics **before reconnecting**, and preserve serial lines from before/after it. Note FC heartbeat/armed/mode state and RC6. Center the wheel and release pedals for at least half a second before attempting manual PC re-enable. Do not repeatedly reconnect to erase the evidence.

| Observation | Most useful next check |
|---|---|
| ESP uptime restarts / boot log repeats | Reset or power interruption. `brownout` is strong low-voltage evidence; `power-on` can also follow complete power loss. Reset reason alone is not a supply measurement. |
| Converter `stops` increases and `last=input-timeout` | Read `mask` and `ageUs`; inspect those FC-to-converter signals and their grounds. A recovered live `*` does not erase the stored fault. |
| Converter `gap` increases / `last=loop-gap` | Loop was delayed at least 150 ms; investigate scheduling/USB behavior separately from the PWM source. |
| Bridge timeout increases / `last=command-timeout` | Accepted uplink commands stopped for at least 500 ms. Check PC stop reason, Wi-Fi continuity, and neutral rejection counter. |
| PC says stale input or controller reconnected | Investigate PXN USB/driver/cable and PC scheduling using its age/session record. |
| FC telemetry stays live but FC output or RC6 changes | Inspect FC mode, arming, takeover and failsafe state. |
| All command layers remain active but motors stop | Inspect driver power, connector continuity, driver protection and battery current capability. There is no driver-current/fault feedback in this converter. |

Cost priority: verify mapping and connector retention before buying parts. For a confirmed supply problem, the dominant requirements are motor stall/transient current, wiring resistance and regulator capacity—not another firmware timeout increase. The available information is insufficient to size a replacement driver/UBEC or capacitor reliably.

## Validation and delivery limits

- 112 Python tests passed on the candidate, including 2,000 alternating combined input ticks and a same-GUID/new-instance reconnect occurring between control ticks.
- Nine actual-sketch host builds/runs passed with address/undefined-behavior sanitizers: converter, power response and new dropout test on Arduino API mocks 2 and 3; bridge Wi-Fi and ELRS modes; Wi-Fi startup/recovery.
- Firmware test includes 2,000 rapid differential ticks with rejected edges, one-channel timeout, persistent fault mask, rollover, genuine signal loss, neutral recovery, blocked USB, AP recovery and short UART writes.
- These mocks do not simulate motor current, RF interference, ISR latency on silicon, USB hardware, FC firmware or brownouts. Native Windows and actual ESP32 compilation/HIL remain outstanding.
- Delivered source/overlay and sketches are test candidates. No GitHub stable release, installed application, FC parameter set or physical wiring was changed remotely.

## References

- [ArduRover motor and servo connections](https://ardupilot.org/rover/docs/rover-motor-and-servo-connections.html): left/right output functions.
- [ArduPilot auxiliary functions](https://ardupilot.org/rover/docs/common-auxiliary-functions.html): option 46.
- [pygame-ce joystick documentation](https://pyga.me/docs/ref/joystick.html): hotplug instance identifiers.
- [pygame-ce event documentation](https://pyga.me/docs/ref/event.html): event queue handling.
- [Espressif ESP32-S3 fatal errors](https://docs.espressif.com/projects/esp-idf/en/v4.4/esp32s3/api-guides/fatal-errors.html): brownout resets.
- [Espressif reset reasons](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/system/misc_system_api.html): diagnostic reset reporting.

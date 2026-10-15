# FS-iA6 acceptance checklist

Record exact receiver/transmitter firmware, ESP32 board, core/compiler version,
motor/driver markings, supply ratings and measured values. Begin with wheels
raised and an accessible motor-power switch. Verify signal HIGH levels before
connecting receiver outputs to the ESP32 or use the specified buffer.

| Test | Expected result |
|---|---|
| Reset / power-up with CH5 already ON | Outputs remain off; no automatic ARM |
| Missing any of CH1, CH2, CH5, CH6 | Both sources inhibited; no valid pulse for 120 ms stops/disarms |
| Receiver input voltage | PWM arriving at ESP32 stays in its 3.3 V logic domain |
| CH6 STOP | Disarmed/coast; serial source STOP |
| CH6 TX, CH5 OFF, centered 0.4 s, CH5 ON | Explicitly arms; no motion at center |
| ARM ON with nonneutral drive or steering | Denied; centering later while ON does not arm |
| Low drive and steering | All wheel directions correct; steering sign correct |
| CH5 OFF during drive | Stops/disarms |
| Switch TX to PC while moving | Stops/disarms; does not inherit motion or ARM |
| PC selected without receiver permission | PC ARM/drive denied |
| PC permitted, centered stream 0.3 s, PC ARM | Arms explicitly; wheel controls motor demand |
| PC RC stops, radio remains healthy | Stops/disarms after 500 ms RC deadline |
| Radio selected TX; PC ARM/DISARM/release/disconnect | No interruption of TX driving |
| Radio selected TX; PC Wi-Fi disappears | TX driving continues while receiver healthy |
| Radio selected PC; Wi-Fi disappears | Stops/disarms; no fallback to TX |
| BOOT held | Stops/disarms; release alone cannot resume |
| Reverse direction | Coast interval before opposite drive; no reset |
| Transmitter OFF while moving | Receiver produces CH5 OFF + CH6 STOP or no pulses; motors stop |
| Transmitter ON again with CH5 still ON | Remains disarmed until a new OFF -> centered -> ON sequence |
| Bump / combined steering+drive | No supply collapse, reset or unexplained driver thermal shutdown |

**The transmitter-OFF and return tests are mandatory.** A receiver holding the
last PWM values can look healthy to this firmware. Do not assume a timeout
detects RF loss in that case. Correct CH6 STOP failsafe is essential to prevent
an apparent new ARM edge on RF return. See `RADIO_SETUP.md`.

Use a scope/logic analyzer to measure last pulse/command to output-off latency.
The claimed deadlines are code thresholds, not measured radio-to-motor or
physical stopping times. Record whether a stop has a new serial boot/reset
reason, continuing logs, missing PWM, or driver heating. Check 5 V rails and
motor startup current rather than disabling brownout detection.

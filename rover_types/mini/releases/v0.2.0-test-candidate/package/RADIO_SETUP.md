# FlySky FS-iA6 radio setup

Use a compatible bound FlySky AFHDS 2A transmitter, such as your FS-i6X.
The **FS-iA6** has separate PWM outputs. This build does not use iBUS, UART,
PPM, CRSF or an ELRS transmitter.

## Channel assignment

| Channel | Radio control | Required pulse values |
|---|---|---|
| CH1 | Steering stick | Left ~1000, center 1500, right ~2000 us |
| CH2 | Spring-centered forward/reverse stick | Reverse ~1000, stop 1500, forward ~2000 us |
| CH5 | Two-position switch, e.g. SWA | OFF ~1000, ON ~2000 us |
| CH6 | Three-position switch, e.g. SWC | TX ~1000, STOP ~1500, PC ~2000 us |

Assign CH5/CH6 in the transmitter's auxiliary-channel menu. Physical up/down
orientation depends on the transmitter's reversal settings: verify the pulses
in serial output and label the positions. A knob is not the intended source
selector. CH3 and CH4 are unused and need no signal wire.

CH2 is deliberately the spring-centered rover drive input. Do not use an
aircraft throttle interpretation where 1000 means stop: **1000 is full reverse
in this sketch**. On a different stick mode, configure the mixer/channel output
to get the intended spring-centered control. Do not silently swap channels in code.
Adjust radio reversal, or `RX_STEER_INVERT` / `RX_DRIVE_INVERT` in `Config.h`.

Set trim/subtrim so centered CH1/CH2 are within 1475..1525 us. The firmware's
neutral dwell checks both steering and drive. For the first test, reduce
transmitter travel/dual rates if needed; maximum motor PWM is also capped in firmware.

## Mandatory receiver failsafe

With wheels raised and motor power OFF initially, save explicit failsafe values:

| Channel | Failsafe value |
|---|---|
| CH1 | Center / 1500 us |
| CH2 | Stop / 1500 us |
| CH5 | ARM OFF / approximately 1000 us |
| CH6 | STOP / approximately 1500 us |

Use the transmitter's RX setup -> Failsafe menu and save actual positions,
following its exact manual. An entry labeled OFF may mean **hold last position**,
not motor-off. Do not infer safety from a menu label. If the receiver instead
stops PWM on loss, the 120 ms missing-pulse watchdog also disarms.

The **CH6 center STOP failsafe is required**. It resets source authorization;
when RF returns with CH5 still ON, the sketch cannot re-arm until OFF and ON
are deliberately observed again after source settling and centered controls.
CH5 OFF alone, without the STOP sentinel, is not the specified recovery contract.

Test it: observe serial pulses, switch the transmitter OFF, confirm either
CH5 OFF + CH6 STOP or loss of required pulses. Repeat at small drive with wheels
raised and motor power available. Motors must stop. Turn the transmitter back
on with CH5 still ON: motors must remain disarmed. Do not operate on the ground
if this fails. Firmware cannot detect RF loss if the receiver continues valid
held-last pulses on every required channel.

## TX operation

Select STOP and ARM OFF before powering. Select TX, center both axes, leave ARM
OFF at least 0.4 s, then flip ON. If ARM is rejected, centering while ON does not
retry: return OFF, center 0.4 s, then ON. CH5 OFF, CH6 STOP or BOOT stops/disarms.

## Handover to PC

Disable PC control before changing source. Set ARM OFF, select PC, center radio
axes for 0.4 s, then ARM ON. The radio grants permission; motors stay disarmed.
Enable PC Control centered for 0.3 s, then click PC ARM. Wheel motion now supplies
drive. Radio CH5 OFF and CH6 STOP still override it.

To return to TX, ARM OFF, select TX, center 0.4 s, then ARM ON. A PC release,
disconnect or stale PC connection does not affect already selected TX control.
During TX operation a PC DISARM command is denied; use the transmitter stop or
physical motor switch. Keep only one active PC control application.

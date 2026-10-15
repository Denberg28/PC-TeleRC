# Mini rover standard wiring

Default: ESP32-S3 DevKitC-1, four 6 V-rated TT motors on a regulated 5 V rail, two MX1508 boards and FS-iA6 receiver. Driver selection in the sketch must match wiring. Motor/driver supply is independent of 3.3 V logic levels.

## Receiver inputs

Connect the **signal pin** of each channel, not its positive or negative rail.
Follow the receiver's printed signal/+/- marks; pin orientation is not assumed.

| FS-iA6 | ESP32-S3 | Function |
|---|---|---|
| CH1 S | GPIO12 through signal conditioning if required | Steering |
| CH2 S | GPIO13 through signal conditioning if required | Centered drive |
| CH5 S | GPIO14 through signal conditioning if required | ARM |
| CH6 S | GPIO15 through signal conditioning if required | TX / STOP / PC |
| Receiver VCC / + | Logic buck +5 V | Power, not a signal |
| Receiver GND / - | Logic/common GND | Reference |

Receiver specification: 4.0..6.5 V supply; use regulated 5 V, never raw 2S.
All four channel signals are mandatory, including in PC mode. CH3/CH4 unused.

## Receiver signal voltage

Receiver supply voltage does not establish its output logic amplitude. ESP32
GPIOs are not 5 V tolerant. Measure PWM HIGH with an oscilloscope or confirm
the exact receiver's signal specification before a direct connection. A meter
reading the average PWM voltage does not establish the HIGH level.

For unknown/5 V logic, use a **SN74LVC125A four-channel buffer powered from the
ESP32's 3V3 rail**. TI specifies inputs tolerant up to 5.5 V and translation
from 3.3 V or 5 V inputs. Do not substitute a generic 74HC125 without checking
its input-voltage limits. The buffer must share ESP32 GND and its supply.

| Buffer pin, standard 14-pin package | Connection |
|---|---|
| 14 VCC | ESP32 3V3 |
| 7 GND | Common GND |
| 1, 4, 10, 13 (/OE inputs) | GND to enable all four channels |
| 2 (1A) / 3 (1Y) | Receiver CH1 S / ESP32 GPIO12 |
| 5 (2A) / 6 (2Y) | Receiver CH2 S / ESP32 GPIO13 |
| 9 (3A) / 8 (3Y) | Receiver CH5 S / ESP32 GPIO14 |
| 12 (4A) / 11 (4Y) | Receiver CH6 S / ESP32 GPIO15 |

Place 100 nF across buffer VCC/GND and 10 kohm pulldowns at its four receiver
inputs so unplugged lines stay low. Confirm your breakout's actual labels and
package pinout. Outputs need not be enabled during boot for safety because
firmware begins disarmed and motor inputs have their own pulldowns. For verified
3.3 V receiver signals the buffer can be omitted; retain input pulldowns.
Do not use an arbitrary resistor divider on an unknown-level signal: a divider
chosen for 5 V might make an already 3.3 V signal too low to read reliably.

## Common motor slot map

| Physical slot / index | Signal A | Signal B | Extra signal | Two-motor build |
|---|---:|---:|---:|---|
| Left front / 0 | GPIO4 | GPIO5 | GPIO16 | Active |
| Left rear / 1 | GPIO6 | GPIO7 | GPIO17 | Unused |
| Right front / 2 | GPIO8 | GPIO9 | GPIO18 | Active |
| Right rear / 3 | GPIO10 | GPIO11 | GPIO47 | Unused |

`HardwareProfile.h` is the single pin-map definition. The default GPIO map avoids USB, flash/PSRAM, UART0, boot straps and onboard RGB pins. Pin validation rejects duplicate/reserved outputs or conflicts with receiver/BOOT/status pins before configuring outputs. Check your exact board schematic; board variants are not automatically detected.

## Wiring by driver profile

| Profile | A / B for each motor | Extra for each motor | Shared GPIO2 | Logic power / setup |
|---|---|---|---|---|
| MX1508 | Corresponding IN pair | Not connected | Not connected | Driver motor V+ at selected rail |
| DRV8833 | xIN1 / xIN2 | Not connected | All nSLEEP inputs | Remove conflicting nSLEEP ties/pullups if needed; use module schematic |
| TB6612FNG | xIN1 / xIN2 | PWMA or PWMB | All STBY inputs | VCC **3.3 V**, VM selected motor rail; remove conflicting STBY ties |
| BTS7960 module | RPWM / LPWM | **Both R_EN and L_EN of that motor's module** | Not connected | Module logic VCC as specified (commonly 5 V); translate outputs if 3.3 V HIGH is not guaranteed |
| L298N module | Corresponding IN pair | ENA or ENB | Not connected | Logic 5 V; remove ENA/ENB jumpers; follow regulator-jumper instructions for exact board |

Four-motor dual-board assignment: D1 channel A=LF, B=LR; D2 A=RF, B=RR. For **two motors on one dual board**, channel A=LF (GPIO4/5), B=RF (GPIO8/9); do not use LR's GPIO6/7 as the second motor. TB/L298 then use PWM/enable GPIO16 and GPIO18. A BTS paired-half-bridge module drives only one motor, so use two or four complete modules.

One motor connects to one full output pair: AOUT1/AOUT2, OUT1/OUT2 etc. Motor terminals are not fixed GND or positive rails. Do not parallel driver outputs or put multiple motors on one bridge in this standard. Use `MOTOR_INVERT[]` or swap motor wires with power off so positive demand moves all wheels forward.

Install **10 kohm pulldowns** on each used A/B input and each enable/sleep/standby/PWM-extra input, as applicable. External pulls must actually overcome/remove module pullups and hard HIGH jumpers; verify outputs disabled during ESP32 reset and power sequencing. GPIO2 drives the low-current logic enable inputs only. On BTS, join the two enables only within one motor module, then connect to that motor's extra GPIO; keep different motor enable GPIOs separate.

L298 modules must include correctly rated flyback diodes and cooling. Do not power ESP32/receiver from an unverified L298 onboard regulator or connect its 5 V output to the logic buck. For TB, VCC=3.3 V permits compatible logic thresholds. For every module verify input thresholds and power-off backfeeding; do not connect 5 V outputs to ESP32 inputs.

## Recommended two-buck power

For the default MX1508/TT build, both buck inputs connect to the same 2S Li-ion/LiPo battery (8.4 V full).

| Branch | Output | Connections |
|---|---|---|
| Logic buck | Regulated 5 V; 2 A capacity is a useful design allowance | ESP32 5V and FS-iA6 VCC |
| Motor buck | Regulated 5 V; sized from all active simultaneous startup currents | Fuse + motor switch, then both driver power inputs |
| Common negative | Battery/bucks/ESP32/receiver/drivers GND | Star reference with separate motor return wires |

Do not connect the two positive buck outputs together. Route driver current
directly to the motor buck, not through ESP32 headers or breadboard rails.
The receiver shares the **logic** supply, not the motor driver branch. The
ESP32's 3V3 regulator powers only the optional logic buffer, not receiver/motors.

Disconnect external ESP32 positive 5 V before attaching PC USB unless your
specific board has verified power selection. Keep motor power off during upload.
Do not connect raw 2S to ESP32 5V/3V3 or to 3-6 V TT motors. A PWM cap does not
replace correct motor supply voltage, current capacity or thermal checks.

## Suppression and local stop

- 100 nF directly across each motor's two terminals, short leads.
- 470..1000 uF electrolytic (>=10 V) plus 100 nF across each driver's 5 V/GND.
- 220..470 uF electrolytic (>=10 V) near ESP32's regulated 5 V input.
- 100 nF plus 47..100 uF near receiver power if leads are long.
- Twist motor pairs; keep them away from antenna, receiver PWM and ground reference wires.
- GPIO21 -> 330 ohm -> ordinary LED anode; LED cathode -> GND (optional).
- Built-in BOOT held during operation stops/disarms. Release does not resume.
  Physical motor-power switch is the power isolation method; stops otherwise coast.

Observe electrolytic polarity. Capacitor voltage examples above apply only to the 5 V baseline. For other rails, choose capacitors and protection above maximum rail/transient voltage. Select fuse, buck, battery, wire and driver ratings from measured current. A larger buck does not increase driver current capacity. Retain brownout detection; fix supply collapse rather than masking it.

For another profile, motor power may come from a suitable regulated rail or battery only if its full-charge/transient voltage meets both driver/module and motor ratings. Keep receiver/ESP32 on regulated 5 V. See `HARDWARE_PROFILES.md` for regeneration and current limits.

## Baseline BOM

| Quantity | Item |
|---:|---|
| 1 | ESP32-S3 DevKitC-1 |
| 4 (or 2) | Brushed DC motors rated for chosen rail |
| 2 (or 1) | Default MX1508 dual driver; alternative module counts in profile guide |
| 1 | FS-iA6 + compatible transmitter, four signal wires |
| 2 | Buck converters sized independently for logic and motor loads |
| 1 optional | SN74LVC125A + 100 nF for receiver signal conditioning |
| As required | 10 kohm pulldowns, suppression/bulk caps, fuse, motor switch, suitable wiring |

References: FlySky https://www.flysky-cn.com/ia6-canshu ; buffer https://www.ti.com/product/SN74LVC125A ; board https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.1.html ; driver datasheets in `HARDWARE_PROFILES.md`.

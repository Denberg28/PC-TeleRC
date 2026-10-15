# FS-iA6 mini rover wiring

Baseline: ESP32-S3 DevKitC-1, four TT motors rated for the chosen 5 V supply,
two MX1508 dual-driver modules, and FlySky FS-iA6 PWM receiver.

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

## Motor signals — unchanged from v0.1.0

| ESP32-S3 | Driver input | Motor |
|---|---|---|
| GPIO4 / GPIO5 | D1 IN1 / IN2 | Left front |
| GPIO6 / GPIO7 | D1 IN3 / IN4 | Left rear |
| GPIO8 / GPIO9 | D2 IN1 / IN2 | Right front |
| GPIO10 / GPIO11 | D2 IN3 / IN4 | Right rear |

Install **10 kohm from every motor-driver IN pin to GND**, eight total. Each
motor gets one complete driver output pair. Motor terminals are not fixed GND
or power-positive. Never combine driver outputs or put two motors on one
channel. MX1508 PCB terminal labels vary; identify input and output pairs first.
Use `MOTOR_INVERT[]` (LF, LR, RF, RR) or swap a motor's two wires, power off,
so positive demand makes all physical wheels move forward.

## Recommended two-buck power

Both buck inputs connect to the same 2S Li-ion/LiPo battery (8.4 V full).

| Branch | Output | Connections |
|---|---|---|
| Logic buck | Regulated 5 V; 2 A capacity is a useful design allowance | ESP32 5V and FS-iA6 VCC |
| Motor buck | Regulated 5 V; sized from four simultaneous startup currents | Fuse + motor switch, then both driver power inputs |
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

Observe electrolytic polarity. Select fuse, buck, battery and wire ratings from
measured current. MX1508 channels have unequal IC ratings (~0.8 A and 1.5 A
continuous under specified conditions); modules may thermally limit earlier.
TT startup/stall current can exceed a channel rating. This firmware has no
current sensing or current limiting. Check with a current-limited supply and
avoid prolonged stall. A larger buck does not increase driver current capacity.

## Added hardware BOM

| Quantity | Item |
|---:|---|
| 1 | Existing FS-iA6 and compatible transmitter |
| 4 | Receiver signal wires, plus logic power/GND |
| 1 optional | SN74LVC125A buffer/breakout for unknown or 5 V PWM levels |
| 4 | 10 kohm receiver-input pulldowns |
| 1 optional | 100 nF buffer decoupling capacitor |
| 2 | Regulated bucks for logic and motor branches |

Reuse the existing S3, two drivers and motors. The dominant electrical sizing
constraint remains four-motor startup current. No market price or tested
third-party module rating is assumed. See README for primary references.

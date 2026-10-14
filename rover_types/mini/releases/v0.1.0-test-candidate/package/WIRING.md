# Mini rover wiring

Baseline: ESP32-S3 DevKitC-1, 4 individual TT motors rated for approximately
3-6 V, 2 MX1508 dual modules. Verify the exact motor voltage and current first.
Use **one driver channel per motor**, never two motors on a channel.

## Motor signal connections

GPIO numbers are the printed IO numbers, not physical header pin positions.
Use the board's actual pin labels. D1 serves the left side; D2 the right side.

| ESP32-S3 | Driver input | Motor / channel |
|---|---|---|
| GPIO4 | D1 IN1 | Left front, first input |
| GPIO5 | D1 IN2 | Left front, second input |
| GPIO6 | D1 IN3 | Left rear, first input |
| GPIO7 | D1 IN4 | Left rear, second input |
| GPIO8 | D2 IN1 | Right front, first input |
| GPIO9 | D2 IN2 | Right front, second input |
| GPIO10 | D2 IN3 | Right rear, first input |
| GPIO11 | D2 IN4 | Right rear, second input |
| GND | D1 GND and D2 GND | Common reference to supply negative |

Install a **10 kohm pulldown from each IN1..IN4 to GND**: eight resistors total.
These hold the drivers off while the ESP32 resets, boots, or is unplugged.
Software alone cannot establish safe levels before it runs.

Module lettering varies. In this guide `IN1/IN2` means the pair controlling
its first motor output, and `IN3/IN4` the pair controlling its second output.
If your PCB uses `INA1/INB1/INA2/INB2`, map the pairs accordingly. Do not guess
their order from a seller photograph or PCB orientation.

## Motor output connections

| Driver output pair | Connect to |
|---|---|
| D1 Motor A / OUT1+OUT2 | Left-front motor two terminals |
| D1 Motor B / OUT3+OUT4 | Left-rear motor two terminals |
| D2 Motor A / OUT1+OUT2 | Right-front motor two terminals |
| D2 Motor B / OUT3+OUT4 | Right-rear motor two terminals |

Motor terminals connect only to their output pair. **Neither motor terminal
is a fixed GND or battery positive.** Mirrored chassis mounting often makes
right-side polarity opposite to the left. Test each wheel and use
`MOTOR_INVERT[]` or swap its two motor leads to make positive demand move
every wheel forward. Do not tie output pairs together.

## Power: simplest bench arrangement

Use **two separate power sources** for first tests:

| Source | Destination |
|---|---|
| 4x NiMH AA pack (4.8 V nominal), through fuse and motor switch | D1 power + and D2 power + |
| Motor pack negative | Star GND point; D1 GND and D2 GND |
| USB 5 V power bank or PC USB while programming | ESP32-S3 USB power input |
| ESP32-S3 GND | Same star GND point |

Check the four-cell pack's freshly charged voltage against your exact TT motor
rating. This is intended for motors rated up to 6 V, not an unknown 3 V-only
variant. A USB power bank can auto-shut off at low load; verify it stays on.
Use a separate rated motor supply rather than a small rectangular 9 V battery.

**Do not power motors from the ESP32 5 V/3V3 pin or through a breadboard.**
Connect heavy motor return wires directly to the star ground, not through the
ESP32 ground header before returning to the battery. Logic ground still needs
its own wire to that common reference.

## Optional one-battery onboard arrangement

For a 2S Li-ion/LiPo pack (8.4 V fully charged), use **two separate regulators**:

| Battery branch | Regulated output | Destination |
|---|---|---|
| Logic branch | 5.0 V, >=1 A, preferably 2 A headroom | ESP32-S3 5V pin + GND |
| Motor branch through fuse/switch | 5.0 V, sized from measured four-motor current | D1 and D2 power inputs |

All regulator negatives, battery negative, driver grounds, and ESP32 GND join
at the common reference. Do not connect the two positive regulator outputs
together. Do not connect raw 2S or the earlier rover's raw 3S battery to these
TT motors. Do not use PWM limiting as a substitute for the right supply voltage.

Use the ESP32's external 5V input OR USB power at a time unless your exact
board has a verified power-selection arrangement. Disconnect the regulator's
positive 5 V wire before connecting PC USB for upload; keep the motor branch
off. Never apply 5 V to a GPIO or to the 3V3 pin.

## Noise suppression and protection

| Part | Placement / purpose |
|---|---|
| 100 nF ceramic x4 | Directly across each motor's two terminals; short leads |
| 470-1000 uF electrolytic x2, >=10 V | Across each driver's power + / GND, close to PCB |
| 100 nF ceramic x2 | Across each driver's power + / GND, beside bulk capacitor |
| 220-470 uF electrolytic, >=10 V | Across ESP32 regulated 5 V / GND near board |
| 10 kohm x8 | Each driver input to GND, startup/reset protection |
| Appropriately rated fuse | Motor supply positive; select after current measurement and wire/pack checks |
| Accessible motor-power switch | Cuts both drivers' motor supply |

Observe electrolytic polarity. Twist each motor's two wires; keep them away
from the ESP32 antenna and logic inputs. Do not place a single ordinary diode
across a bidirectional motor: it would short the opposite drive polarity.

## Optional status LED and stop

GPIO21 -> 330 ohm resistor -> ordinary LED anode; LED cathode -> GND.
The external LED blinks slowly when disarmed and is solid when armed/ready;
fast blink means armed but waiting for neutral. It indicates firmware state,
not verified physical motor state. Omit it without affecting control.

Built-in BOOT (GPIO0) held during normal operation = stop and DISARM. Release,
send centered controls for 0.3 s, then ARM explicitly to resume. Use the
motor-power switch for a physical stop. Holding BOOT during reset instead
enters the ESP32 ROM download procedure.

## Current budget: check before committing the chassis

The IC datasheet reproduced in the references gives unequal channel ratings:
about **0.8 A continuous** on the lower-rated channel and **1.5 A** on the other,
under its specified conditions. Small clone PCBs can run hotter. Treat
**0.8 A per motor as a conservative upper screening ceiling**, not a promise
that both channels can continuously carry that load on your module.

Obtain or measure each TT motor's stall current at the chosen supply voltage
using a current-limited bench supply and a very short test. Do not hold it
stalled on a battery. Check loaded current and driver temperature with two
motors running per board. If a motor's expected load/stall exceeds the channel
or thermal limits, the MX1508 is unsuitable for that duty; use a suitably rated
driver with current limiting. Firmware has no current sensor and cannot stop
an overload before it happens.

For supply sizing, start with:

`I_motor_supply >= sum of the four simultaneous startup/load currents`

Use measured or manufacturer values. For illustration only, four motors each
drawing 0.7 A at startup require 2.8 A before headroom; this is not a rating
for your motors or permission to stall them. Regulator, battery, fuse, connector,
and wire ratings must agree. For a buck motor rail, approximate battery input:
`I_batt ~= (V_motor * I_motor)/(efficiency * V_batt) + logic input current`.

## Mechanical and electrical BOM

| Quantity | Item |
|---:|---|
| 1 | ESP32-S3 DevKitC-1 and USB data cable |
| 4 | Matched TT DC gearmotors with wheels |
| 2 | MX1508 dual-motor modules |
| 1 set | Chassis, motor brackets, screws, wiring, connectors |
| 1 | 4-cell NiMH pack/holder suitable for measured motor current |
| 1 | USB power bank for ESP32 logic (or regulated 5 V supply) |
| 1 each | Motor fuse/holder and motor-power switch |
| 4 | 100 nF motor ceramics |
| 2 each | Driver bulk electrolytic and 100 nF ceramic |
| 1 | ESP32 bulk electrolytic |
| 8 | 10 kohm input pulldowns |
| optional | Ordinary LED + 330 ohm resistor |

Motor startup current and the power system are the main sizing/cost drivers.
The frugal first prototype reuses the ESP32, a suitable USB power bank, and
an appropriate NiMH pack, avoiding two new buck regulators. No current market
prices are asserted. Add a protected battery and matching charger if choosing
the optional lithium setup.

References: see README. Ratings apply to the cited IC, not a verified rating
for an unidentified module or motor.

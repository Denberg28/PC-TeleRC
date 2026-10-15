# Hardware profiles and scaling

One firmware handles supported **electrical input interfaces**. Every motor has its own full H-bridge. Use one driver family for all active channels; mixed-driver builds are outside this standard.

| ID | Interface / modules for 4 motors (2 motors) | Direction / PWM | Additional control | Declared motor supply range |
|---:|---|---|---|---|
| 1 | MX1508 dual ×2 (×1) | Two PWM inputs per motor | None | 2–8 V, conservative variant limit |
| 2 | DRV8833 dual ×2 (×1) | Two PWM inputs per motor | GPIO2 to all nSLEEP | 2.7–10.8 V |
| 3 | TB6612FNG dual ×2 (×1) | Two direction inputs + PWM per motor | GPIO2 to all STBY | 2.5–13.5 V VM; logic VCC 3.3 V |
| 4 | Paired-BTS7960 H-bridge module ×4 (×2) | RPWM + LPWM per motor | Separate enable GPIO per motor | 5.5–27.5 V; verify module limits |
| 5 | L298N dual module ×2 (×1) | IN pair + EN PWM per motor | Remove ENA/ENB jumpers | 5–46 V IC envelope; actual module may be much lower |

These are compile-time declaration bounds, not blanket module ratings. Account for battery full-charge voltage, transients, capacitor ratings, regulator limits, dropout, cooling and wiring. A nominal 2S battery reaches **8.4 V** and is rejected for the default conservative MX1508 profile; ordinary 3–6 V TT motors also need a suitable regulated rail. L298N wastes substantial motor voltage as heat and is a compatibility option rather than an upgrade for a 5 V TT build.

## Configuration examples

Edit the default `#define` values inside the existing `#ifndef` blocks in `HardwareProfile.h`, or provide compiler definitions. Do not define a macro in only the `.ino` after its includes.

| Build | DRIVER | MOTOR_COUNT | SUPPLY_MAX_MV | MOTOR_RATED_MV | Other |
|---|---:|---:|---:|---:|---|
| Existing 5 V / 6 V-rated TT baseline | 1 | 4 | 5000 | 6000 | Defaults |
| Smaller two-motor MX baseline | 1 | 2 | 5000 | 6000 | Connect LF/RF only |
| 6 V TB6612 motors and supply | 3 | 4 | 6000 | 6000 | VCC 3.3 V; STBY controlled |
| 12 V motor / BTS module example | 4 | 4 | 12000 | 12000 | `TELERC_BTS_LOGIC_VERIFIED=1` after electrical verification |

The 12 V example is a regulated 12 V maximum, not a nominal 12 V battery assumption. The BTS acknowledgement is a declaration by the builder, not a measurement by firmware. A BTS module's input buffer may need a proper 3.3-to-5 V logic translator. Verify exact HIGH/LOW thresholds and default-enable behavior.

`MOTOR_INVERT[4]`, `MOTOR_TRIM_PERCENT[4]` and `MOTOR_DUTY_CAP[4]` use LF/LR/RF/RR order. Trims may only reduce demand (0–100%). Default global cap and individual caps are 180/255. Raising an individual cap above the global cap does not raise mixer output. Trim is not speed synchronization: loaded motors can still run at different speeds.

Default PWM is 20 kHz, L298N 10 kHz; `TELERC_PWM_HZ` accepts 500–20000 Hz. Use a frequency supported by the actual driver/module. ESP32-S3 has eight LEDC channels: two per active motor for MX/DRV/BTS, one for TB/L298. A two-motor build allocates channels contiguously to physical slots 0 and 2 and leaves slots 1/3 unconfigured.

## Driver stop truth

| Driver | Global stop | Zero motor while another moves |
|---|---|---|
| MX1508 | Both inputs LOW | Both inputs LOW |
| DRV8833 | nSLEEP LOW and inputs LOW | Inputs LOW; nSLEEP shared HIGH |
| TB6612FNG | STBY LOW | IN1=IN2=LOW **and PWM=HIGH**, giving high impedance |
| BTS module | Both R_EN/L_EN LOW | That motor's R_EN/L_EN LOW |
| L298N | ENA/ENB LOW | That motor's enable LOW |

Using the same “set all PWM to zero” implementation for every driver would be wrong. TB PWM LOW with STBY HIGH short-brakes; BTS both PWM LOW with enables HIGH also brakes. This layer explicitly requests coast on zero, disarm and faults. During nonzero PWM, recirculation/braking behavior differs by driver; equal duty does not imply equal speed or heating.

TB/DRV wake has a nonblocking 2 ms delay; no command is queued for later execution. The current armed demand is re-evaluated each loop. Reversal has a 30 ms coast minimum; this is a switching guard, not proof that a large rotor has stopped. Every stop is high impedance/coast, not a holding brake; gravity/inertia can continue moving the rover.

## What scaling requires

- **Smaller:** choose two motors, reduce duty/trim, use a suitable lower-voltage rail within driver range, then retest start and stop behavior.
- **Larger:** select a suitable bridge and motor supply, size per-channel continuous/stall current, fuse, wiring, cooling and bulk suppression. A product's advertised peak current is not a tested module continuous rating. MX1508 channels can have unequal current ratings; DRV8833 package current capability varies; do not infer limits from the chip name alone.
- Supply must handle simultaneous motor startup. Buck converters commonly cannot absorb regenerative energy: evaluate motor-rail overshoot and appropriate clamping/absorption with the exact supply. Use a physical power isolation switch appropriate to the build.
- A PWM cap does **not** provide voltage regulation or current limiting. There is no current sensor, battery cutoff, encoder feedback, acceleration ramp, stall timer or closed-loop speed control in this release. Motor current can exceed ratings even at reduced duty.
- Changes to driver, motor, gearing, wheel size, mass, battery or wiring require the bench checklist again. Higher-inertia/power platforms need an independent stop design and measured stop envelope before ground operation.

## Extension boundary

Supported here: two/four brushed DC skid-steer motors, one bridge per motor, same family, ESP32-S3. Encoder inputs are not implemented. No servo steering, BLDC/ESC pulse interface, balance loop, motor pairs sharing a bridge, >4 channels, mixed drivers or automatic current tuning. Those require another reviewed backend/vehicle profile. Keep radio ownership and arming outside any future driver implementation.

## Sources

- MX1508 IC datasheet reproduction: https://uelectronics.com/wp-content/uploads/2018/04/MX1508_Datasheet.pdf (module variants differ; 8 V software ceiling is conservative).
- TI DRV8833: https://www.ti.com/lit/ds/symlink/drv8833.pdf
- Toshiba TB6612FNG: https://toshiba.semicon-storage.com/info/TB6612FNG_datasheet_en_20141001.pdf?did=10660&prodName=TB6612FNG
- Infineon BTS7960: https://www.infineon.com/assets/row/public/documents/10/57/infineon-bts7960-ds-en.pdf
- ST L298: https://www.st.com/resource/en/datasheet/l298.pdf
- Espressif LEDC: https://docs.espressif.com/projects/arduino-esp32/en/latest/api/ledc.html

Use the exact module schematic and motor datasheet in addition to IC specifications.

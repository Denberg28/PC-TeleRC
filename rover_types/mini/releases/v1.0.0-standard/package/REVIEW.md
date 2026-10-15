# Versatility review — 2026-10-15

## Finding

The v0.2.0 direct sketch was suitable as an MX1508/four-TT starting point, but not a generic driver layer. Fixed motor count, two PWM inputs per motor and assumed zero-duty stop behavior coupled the safety logic to that hardware. Swapping a board alone could silently change coast into braking, omit enables, or exceed voltage/current capability.

## Standard implementation

| Concern | v1.0.0 resolution | Remaining boundary |
|---|---|---|
| Driver input topology | Separate `MotorOutputs.h`, five explicit truth tables | Exact PCB/schematic still checked by builder |
| Two/four motors | Active physical slots and contiguous LEDC allocation | Same left/right skid mixer only |
| Stop / reset / partial setup fault | Driver-specific high impedance; enable defaults LOW; initialization fails closed | External pulls/enable wiring and physical behavior require measurement |
| Driver wake | 2 ms nonblocking delay, demand rechecked each tick | Module-specific timing may require revision |
| Pin changes | Central map, conflict/reserved-output validation before initialization | Physical pin labels/board variant not detectable |
| Motor differences | Polarity, reducing trim, per-channel duty caps | Open-loop; no current, torque or wheel-speed control |
| Supply settings | Compile-time ranges and motor-voltage consistency check | No voltage sensor; settings cannot protect miswiring |
| Ownership / source loss | Existing FS-iA6 neutral/explicit-edge gate and independent PC watchdog retained | PWM held-last RF loss needs verified receiver failsafe |
| Safety regression | All 5×2×2 host combinations, sanitizer/fuzz and fault tests; target build matrix | Hardware acceptance pending |

Replaced deprecated volatile increment with an explicit assignment in PWM capture to avoid the core 3 compiler warning. Existing archived candidates and PC application are unchanged.

## Decision

Use this as the **mini standard source release** and keep its default build identical in electrical intent to the original four-TT/MX1508 design. Add future driver backends only with datasheet truth-table review, stop/partial-init tests, actual target compilation, a wiring update and bench evidence. New steering or balancing algorithms belong in their own rover type. “Standard source” does not mean universal hardware compatibility or a completed field qualification.

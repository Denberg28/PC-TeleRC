# Four-wheel steering rover

**Status: planned — documentation only.** No sketch, pin assignment, tested
hardware BOM, compiled binary or sub-release exists for this type yet.

A vehicle with steering control at four wheels. Drive count and independent versus linked steering actuators remain undecided.

## Requirements to resolve

1. Select linkage geometry, actuator count, wheelbase, track and feedback.
2. Define steering endpoints, neutral alignment and geometric limits per wheel.
3. Consider coordinated, crab or counter-phase modes only if the chosen mechanism supports them; no such modes exist in this folder.
4. Bench-test steering alignment and direction before coupling propulsion.

## Future first candidate

Once those decisions are made, record controller/actuator identities, wiring,
input units, arming, link loss, local stop behavior and validation evidence in
`releases/<version>/`. Follow [the sub-release policy](../SUB_RELEASES.md).
The mini firmware is a reference for transport packaging, not a ready-to-use
controller for this vehicle architecture.

[Back to rover catalog](../README.md)


# Two-wheel drive rover

**Status: planned — documentation only.** No sketch, pin assignment, tested
hardware BOM, compiled binary or sub-release exists for this type yet.

A drivetrain with two powered wheels. Differential steering with a caster and conventional steered layouts are different possible architectures.

## Requirements to resolve

1. Select differential drive or a steered axle, wheel support, motors, encoders and drivers.
2. Document the chosen mixing/steering geometry, actuator mapping and power budget.
3. Define coast/brake, disconnect, reset and neutral/arm recovery for the actual build.
4. Validate motor direction, current, traction and stopping on the selected chassis.

## Future first candidate

Once those decisions are made, record controller/actuator identities, wiring,
input units, arming, link loss, local stop behavior and validation evidence in
`releases/<version>/`. Follow [the sub-release policy](../SUB_RELEASES.md).
The mini firmware is a reference for transport packaging, not a ready-to-use
controller for this vehicle architecture.

[Back to rover catalog](../README.md)


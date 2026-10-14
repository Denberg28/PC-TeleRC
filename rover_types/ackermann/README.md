# Ackermann steering rover

**Status: planned — documentation only.** No sketch, pin assignment, tested
hardware BOM, compiled binary or sub-release exists for this type yet.

A conventional steered-wheel layout. Steering linkage, drive count and actuator choice are not yet selected.

## Requirements to resolve

1. Select wheelbase, track, steering linkage/servo, drive arrangement and feedback.
2. Define steering neutral/endpoints and the mechanical geometry before mapping remote input.
3. Document steering saturation, propulsion limits and local stop/recovery behavior.
4. Verify steering travel, wheel alignment and turning geometry on a bench fixture.

## Future first candidate

Once those decisions are made, record controller/actuator identities, wiring,
input units, arming, link loss, local stop behavior and validation evidence in
`releases/<version>/`. Follow [the sub-release policy](../SUB_RELEASES.md).
The mini firmware is a reference for transport packaging, not a ready-to-use
controller for this vehicle architecture.

[Back to rover catalog](../README.md)


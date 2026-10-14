# Tracked rover

**Status: planned — documentation only.** No sketch, pin assignment, tested
hardware BOM, compiled binary or sub-release exists for this type yet.

A planned left/right track platform. Motor count and driver topology are not selected.

## Requirements to resolve

1. Select track mechanics, reduction, motor count and drivers from the intended load.
2. Document current and thermal limits for tight turning and track stalls.
3. Define differential mixing and stop/recovery behavior for the selected drivetrain.
4. Measure turning load, driver temperature and supply sag before increasing demand.

## Future first candidate

Once those decisions are made, record controller/actuator identities, wiring,
input units, arming, link loss, local stop behavior and validation evidence in
`releases/<version>/`. Follow [the sub-release policy](../SUB_RELEASES.md).
The mini firmware is a reference for transport packaging, not a ready-to-use
controller for this vehicle architecture.

[Back to rover catalog](../README.md)


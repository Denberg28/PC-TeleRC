# Mono rover

**Status: planned — documentation only.** No sketch, pin assignment, tested
hardware BOM, compiled binary or sub-release exists for this type yet.

Reserved concept name. It may mean a monowheel, unicycle or another single-wheel arrangement; no interpretation has been selected.

## Requirements to resolve

1. Confirm what mono means mechanically and whether it needs active balance.
2. Specify propulsion, steering, stabilization, feedback and power after the architecture is agreed.
3. Establish the local stop/recovery response and test fixture before choosing any mixer.
4. Create the first firmware candidate only after the concept and hardware are documented.

## Future first candidate

Once those decisions are made, record controller/actuator identities, wiring,
input units, arming, link loss, local stop behavior and validation evidence in
`releases/<version>/`. Follow [the sub-release policy](../SUB_RELEASES.md).
The mini firmware is a reference for transport packaging, not a ready-to-use
controller for this vehicle architecture.

[Back to rover catalog](../README.md)


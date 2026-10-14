# Balancing rover

**Status: planned — documentation only.** No sketch, pin assignment, tested
hardware BOM, compiled binary or sub-release exists for this type yet.

A chassis requiring active balance, with wheel count and balance axis still to be selected.

## Requirements to resolve

1. Confirm the balance axis, chassis mass/geometry, IMU, motor drivers, encoders and power budget.
2. Define a local estimator and balance controller with measured loop timing; Wi-Fi carries bounded motion requests, not the inner balance loop.
3. Define reset, sensor failure, loss-of-link and disarm behavior for this specific mechanism. The mini's immediate coast policy must not be copied without analysis.
4. Use a restrained test rig and verify sensors, actuator signs and controlled stopping before free operation.

## Future first candidate

Once those decisions are made, record controller/actuator identities, wiring,
input units, arming, link loss, local stop behavior and validation evidence in
`releases/<version>/`. Follow [the sub-release policy](../SUB_RELEASES.md).
The mini firmware is a reference for transport packaging, not a ready-to-use
controller for this vehicle architecture.

[Back to rover catalog](../README.md)


# Rover evolution roadmap

This file tracks planned work, not implemented features or promised deadlines.

| Type | Definition / hardware decisions | Controller work later | Evidence needed next |
|---|---|---|---|
| Mini | v1.0.0 standard: 2/4 motors, five driver interfaces; confirm exact motor/module/S3 and power budget | Preserve CH1/CH2 skid mixer and source safety; future feedback only from requirements | Wheels-up bench, exact-board upload, supply/thermal and measured stop tests |
| Balancing | Chassis, IMU, motor/encoder feedback, balance axis and power | Local estimator and closed-loop balance; bounded remote setpoints | Sensor validation, restrained rig, measured loop timing and loss-of-link response |
| Mono | Confirm whether monowheel, unicycle or another architecture | Undecided until architecture is selected | Agreed definition and mechanical feasibility |
| Four-wheel steering | Steering actuator count, wheelbase, track, sensors and drive count | Geometry/angle limits; later mode options if supported mechanically | Steering bench rig, endpoints, direction and alignment |
| Two-wheel drive | Differential plus caster or steered axle; gearing and encoders | Mixer for the selected layout | Motor power budget, direction, traction and stop tests |
| Tracked | Track mechanics, drivers, current and thermal margins | Differential track mixing and actuator limits | Current under turning load, thermal limits and loss-of-link stop |
| Ackermann | Steering servo/linkage, wheelbase, track and drivetrain | Steering calibration and geometry constraints | Endpoint/neutral checks, turning geometry and stop behavior |

## Shared work, once justified by a second implementation

- Define input demand, connection state and per-profile telemetry without
  sharing unsafe assumptions about coast, brake, balance or actuator order.
- Extract common discovery/packet code only after the second profile clarifies
  the common requirements; keep vehicle control loops separate.
- Add a PC vehicle profile picker with explicit Apply/Disconnect behavior and
  no automatic arm/control enable on profile changes.
- Test wheel and keyboard source switching, focus loss, key release, held-key
  reconnect, and Space behavior with the appropriate vehicle stop policy.

No automatic range estimate, camera integration, autonomy or return-to-home
capability is implied by this folder structure.


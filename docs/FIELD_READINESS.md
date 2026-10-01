# PC TeleRC field-readiness baseline — v0.1.0a4

## Simulated operator workflow
Automated tests model these state transitions:
1. Startup without MAVLink → control denied.
2. Healthy heartbeat + selected controller + neutral throttle → preflight passes.
3. Explicit ARM → allowed only with the same healthy preflight.
4. PC Control enable → allowed only from neutral.
5. Active driving → continuous checks run at the control tick.
6. Controller data stale/unplugged → control latches OFF.
7. Controller reconnect while throttle is displaced → re-enable denied.
8. Controller neutral after reconnect → manual re-enable can pass.
9. MAVLink heartbeat stale/Wi-Fi loss → control latches OFF.
10. Calibrated axis unavailable → fail closed.
11. Steering/throttle mapped to the same RC channel → fail closed.
12. Foreign MAVLink vehicle heartbeat → ignored; vehicle identity is not switched.
13. Live settings/controller changes → PC Control drops OFF.
14. Override transmission failure → PC Control drops and latches fail-safe.
15. Shutdown/fail-safe → repeated neutral then RC-override release attempts.

## Field acceptance tests still required
These cannot be proven by software simulation alone:
- PXN Windows driver/mode enumeration and hot-plug behavior.
- Actual pedal electrical/driver neutral values after calibration.
- ESP32-S3 UDP routing and Wi-Fi reconnection behavior.
- ArduRover RC override acceptance on the configured RCMAP/channels.
- Independent ArduRover GCS failsafe action when the PC cannot transmit.
- BTS7960/motor-driver response to neutral, disarm, FC reboot, and power sequencing.
- Measured stop time after PXN USB removal.
- Measured stop time after ESP32/Wi-Fi loss.
- Windows sleep, app crash, firewall change, and network-adapter handover behavior.

## Recommended bench sequence
1. Lift drive wheels clear of the ground.
2. Configure a fixed ESP32 target IP where possible.
3. Run Diagnostics and resolve all FAIL items.
4. Calibrate the PXN and verify live direction.
5. Confirm CH1/CH3 mapping (or actual chosen channels) in ArduRover.
6. Set and test ArduRover GCS failsafe independently.
7. Enable PC Control at 25% throttle authority.
8. Test: wheel unplug, Wi-Fi off, ESP32 power loss, app close, app forced termination, FC reboot.
9. Record measured time from fault injection to motor stop.
10. Only then proceed to low-speed ground testing in a controlled area.

## Release gate
Do not call the module field-ready until every physical failure test above has a recorded pass/fail result and the worst-case stop behavior is acceptable for the vehicle.

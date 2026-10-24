# Unified firmware commissioning — record results before vehicle operation

Use restrained wheels, low authority and an independent local cutoff. Back up
FC parameters, app settings and private provisioning; retain the previous stable
app/firmware pairing. These checks are not recorded as passed by software tests.

1. Flash the privately generated matching BASE/ROVER/NODE set. Confirm actual
   FC system ID, real heartbeat, radio mode and control-channel mapping.
2. With no PC connected, confirm direct/relay discovery. Test NODE1 alone,
   NODE2 alone, both in order and power/reboot sequences; measure route latency.
3. Connect main-screen LORA. Non-neutral enable/ARM must fail. Explicit neutral
   enable must acquire both axes; verify actual steering and drive direction.
4. Inject USB removal, frozen input, lost RF, node reboot, FC reboot, UART loss
   and power disturbance. Record worst-case stop/release timing. Confirm no
   automatic motion on recovery and manual re-enable is required.
5. Repeat manual driving and fault tests through every intended relay path.
   Resolve latency-induced 500 ms stops; do not increase watchdogs to hide loss.
6. Stop, disable, disarm and disconnect manual control. Wait two seconds. Open
   Mission, upload/read back a short route while disarmed. Check wrong ID,
   missing GPS, stale telemetry and mismatched plan all block Start.
7. Arm with independent RC in MANUAL/HOLD; confirm Start once. Verify actual
   ARMED AUTO telemetry, HOLD intervention and missing-ACK UNKNOWN behavior.
8. While in AUTO, manual driving must remain blocked. Verify physical receiver
   intervention; a UI label does not prove receiver ownership or stopping.
9. Confirm HOLD/stationary, close Mission, wait two seconds, select MANUAL,
   reconnect the main window and deliberately re-enable at neutral. Previously
   verified mission-start authorization must not survive manual acquisition.
10. Measure configured GCS-loss behavior, including any explicit AUTO-continuation
    policy. Independently verify every auxiliary ON/OFF event and local cutoff.

Record board revisions, antenna/RF setup, FC/app/firmware versions, parameters,
path, test result and measured times. Stop testing on unexpected movement.

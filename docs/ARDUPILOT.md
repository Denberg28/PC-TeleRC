# ArduRover integration

PC TeleRC sends a GCS heartbeat at 1 Hz and RC_CHANNELS_OVERRIDE for steering/throttle only while PC Control is enabled.

## Vehicle-side fail-safe is mandatory
Do not depend on the Windows app's neutral packet for Wi-Fi-loss safety. Configure ArduRover GCS/telemetry fail-safe (FS_GCS_TIMEOUT / FS_GCS_ENABLE / FS_ACTION) for the actual vehicle and test environment.

## Defaults
- Steering RC channel 1
- Throttle RC channel 3
- Neutral 1500 us
- Nominal 1000–2000 us
- Alpha throttle authority 25% => 1375–1625 us

Confirm actual RCMAP and servo/motor configuration before powered testing.

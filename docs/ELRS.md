# ELRS external transmitter integration (experimental)

The app now offers TeleRC Wi-Fi or ELRS external TX USB MAVLink as separate connections. Select the module's COM port and Apply & Reconnect. Serial uses 460800 baud, DTR/RTS low before opening, bounded reads/writes, surfaced send errors, one physical port, and no automatic reopen. The service retains first vehicle identity, fresh heartbeat/input, neutral prerequisites and explicit manual enable. Bridge ASCII discovery/disconnect is never sent to serial ELRS.

The intended user hardware is HGLRC T ONE ELRS 915 MHz external TX on a RadioMaster Pocket, and GEPRC ELRS DUAL 915M PA500 diversity RX at the flight controller. Their exact firmware and USB COM capability have not been examined. This app option is not a raw CRSF module-bay driver and does not make a firmware-updater-only USB port a MAVLink port.

## Hardware gate

Confirm the T ONE enumerates a usable COM device and both its exact TX target and GEPRC RX target support current ELRS MAVLink firmware. Follow the official ELRS MAVLink configuration for the TX/RX and the specific receiver UART. Do not apply the former ESP32 115200-baud settings blindly to this receiver. No firmware, binding, radio settings, UART wiring or flight-controller parameters are changed by the app.

Official ELRS documentation describes standalone USB MAVLink use without a handset. For PC wheel control, establish and bench-test that standalone path first. A module simultaneously receiving active Pocket stick channels is a competing control source; this release does not implement or verify arbitration between those channels and PC MAVLink overrides. It does not promise automatic Pocket takeover. Ordinary CRSF radio operation remains a separate hardware workflow.

## Bandwidth

ELRS mode transmits PC RC override at 5 Hz rather than the Wi-Fi path's 20 Hz. Each MAVLink 1 override is 26 bytes; five per second plus a 17-byte GCS heartbeat is approximately 147 bytes/second before arm/release bursts. This is a starting point, not a guaranteed radio budget. The T ONE's old 900 MHz packet modes have limited bandwidth: choose and validate an adequate packet rate (200 Hz is the official recommended maximum for legacy 900 MHz), keep telemetry streams low, and inspect receiver/module queue/drop statistics. Slow 25/50 Hz radio modes may be insufficient. USB write success does not prove air-link delivery.

No output is enabled solely by opening a COM port. USB removal, heartbeat loss and local write/backpressure failures inhibit control. RF delivery latency, stale queued commands, neutral/release and RC takeover remain hardware validation items. Bench test with wheels lifted before using ELRS to move the rover.

## Sensitivity

Steering and drive each have a 25–100% slider with a percentage below it. Settings persist independently; old files get 100% drive sensitivity. Drive scales both forward and reverse, then the separate throttle limit applies. Example: drive 50% and throttle limit 25% gives a maximum normalized output of 12.5%. ARM/manual-enable checks use the unscaled pedal input so a low gain cannot hide a pressed pedal. Editing either slider disables PC control and requires Apply Settings and manual re-enable.

## Sources

- ExpressLRS MAVLink and standalone/USB setup: https://www.expresslrs.org/software/mavlink/
- HGLRC T ONE specifications: https://www.hglrc.com/products/hglrc-elrs-t-one-tx-module
- GEPRC receiver: https://geprc.com/product/geprc-elrs-dual-915m-pa500-diversity-receiver/

Automated tests use a fake serial endpoint to verify settings/signals, heartbeat bootstrap, drive/release, closure, write backpressure and missing-port failure. They do not validate the named TX/RX pair physically.

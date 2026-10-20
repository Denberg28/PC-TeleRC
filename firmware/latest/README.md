# TeleRC current firmware folder

This private collection contains the current baseline firmware for the existing TeleRC hardware. Experimental encrypted mission firmware, alternate motor drivers and legacy Android controller architectures are excluded.

| Firmware | Build profiles | Source |
| --- | --- | --- |
| Wi-Fi Mini Rover | MX1508, four motors | Current published TeleRC Android release; firmware 1.2.3 |
| Receiver Mini Rover | MX1508, four motors, FS-iA6 control | Standard 1.0.0 package on PC-TeleRC main |
| Balancer | Two TT motors, MX1508, default IMU mounting | Firmware 0.3.0; directions unverified by default |
| ESP32-S3 Wi-Fi bridge | FC UART / UDP | Published stable PC-TeleRC release; bridge 0.1.5 |
| Four-output PWM converter | Four BTS7960 modules | Published stable PC-TeleRC release; glitch-filter converter 1.0.5 |
| LilyGO SX1262 manual link | BASE/ROVER without relays; BASE/ROVER/NODE1/NODE2 with two relays | Published stable PC-TeleRC release, currently v0.1.3 |

There are **11 board builds**. Compile and host-test success establishes software build verification. Physical motor direction, electrical compatibility, RF range, stopping latency and balancing performance are not established by compilation. The balancer requires its direction and arming checks before use. Receiver Mini and Wi-Fi-only Mini have different control authority and remain separate packages.

## Download and maintenance

After a complete successful Actions build, the private draft release **TeleRC master firmware collection** contains a versioned ZIP. `LATEST.json` selects the last completely successful collection. Earlier archives remain available. Actions also retains build artifacts for 30 days. A failed or incomplete build never advances the latest pointer.

`catalog.json` defines the exact profiles and tracks the latest published numeric Android app release, the latest non-prerelease published PC app release, and the receiver Mini standard package on main. Every package records exact commits and pinned ESP32 core 3.3.2 / RadioLib 7.2.1. Update source paths and approved baseline selections in the same development change when a new working firmware supersedes these versions. Explicit exclusions prevent experimental or alternate architectures from entering the collection automatically.

The **Master firmware collection** workflow checks changes on main, supports **Run workflow**, and checks tracked upstreams nightly at 18:15 UTC / 02:15 Manila. New matching sketch folders outside the explicit included/excluded set require catalog review. The workflow must be installed on the default branch for the nightly schedule. Private source and binaries stay in this repository; no APK or Windows executable is changed.

## Selecting and flashing

Read each profile's `PROFILE.md`, `BUILD.json`, wiring/setup guides and `FLASH.json`. Generic ESP32-S3 targets use 4 MB default partitions, CDC USB and PSRAM disabled. LilyGO builds select the actual SX1262 board revision. Different radio protocols and base/rover/relay topology settings must match.

Disconnect motor power before flashing. Packages provide separate bootloader, partition, boot_app0 and application images with offsets and SHA256 checksums. Whole-flash/NVS images are excluded. Do not erase all flash merely to update: saved gyro calibration and pairing can remain when firmware and partition layouts are compatible. LoRa examples contain no preset private credentials; pair/configure both ends using their existing setup flow.

`build.py resolve`, `build.py compile --group GROUP`, and `build.py package` reproduce the collection. Run `python -m unittest discover -s firmware/latest -p 'test_*.py'` for catalog/package safeguards. These packages remain draft candidates until the required physical acceptance checks are recorded.

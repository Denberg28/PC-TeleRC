# TeleRC master firmware folder

This private folder is the maintained catalog for TeleRC Android and PC firmware. It compiles45 current profiles into one versioned bundle with sketch sources, binaries, wiring guides, dependency versions, flash offsets, build logs and SHA256 checksums.

**Download:** open this repository's Releases and the draft **TeleRC master firmware collection**. `LATEST.json` identifies the newest completely successful bundle; older versioned bundles remain available. The Actions workflow **Master firmware collection** also retains each build for30 days. These are build-verified candidates, not hardware-qualified stable firmware. No APK, Windows release, motor tuning or user credentials are changed.

| Family | Profiles | Select for |
| --- | --- | --- |
| Android controllers/gateways |11| Dedicated motor, Wi-Fi gateway, legacy bridge/hybrid/direct, SX1262/SX1276 BASE/ROVER, paired/four-input PWM converter |
| Wi-Fi Mini Rover |10| Wi-Fi-only mini, five drivers, two/four motors; source1.2.3 |
| Receiver Mini Rover |10| FS-iA6 receiver-gated standard1.0.0, five drivers, two/four motors; distinct authority/firmware family |
| Balancer |2| Standalone0.3.0, IMU mounting0/1, directions unverified by default |
| PC manual links |8| PC Wi-Fi bridge, PWM converter and SX1262 runtime BASE/ROVER/direct/two-relay NODE1/NODE2 |
| Encrypted mission |4| Mission0.2.0rc1 public keyless BASE/ROVER001/NODE1/NODE2 examples; RF stays OFF until private provisioning |

## Maintenance

- `catalog.json` is the source of truth. Android follows the highest published numeric app release. PC runtime tracks `dev/mission-planning-v0.1.5rc1`; receiver Mini tracks `main`. Every bundle records the exact resolved commit for each. When active development moves to a new branch/path, update that family's catalog pointer in the same change. No source is silently merged across incompatible protocols.
- Main-branch firmware/catalog changes trigger checks. Every night at18:15 UTC (02:15 Manila), the workflow checks the tracked upstreams and rebuilds if their content/provenance changed. **Run workflow** forces a manual rebuild. Forks must explicitly configure their own sources; publication is restricted to this private owner repository.
- If any target is missing, fails compilation or lacks required images/checksums, publication stops and `LATEST.json` keeps pointing to the previous complete collection. New Android/PC runtime sketch entrypoints cause a coverage failure until listed. The source family's tests and actual pinned board compilation are separate requirements.
- Add new profiles/families to the catalog and tests; do not copy a newer sketch into an old package. Retired historical versions and private provisioning folders are excluded from the current set. Existing release archives remain rollback references.

## Choosing and flashing

Read each target's `PROFILE.md`, `BUILD.json`, copied wiring/README and `FLASH.json`. Match the exact MCU/driver/radio/partition/USB/PSRAM profile. Generic ESP32-S3 images use4MB default partitions with PSRAM disabled; LilyGO builds specify their real radio revision. A 16MB/N16R8 board is not permission to change the partition map or flash a different target.

Disconnect motor power before flashing. Binaries are separate bootloader/partition/application/boot_app0 images, with declared offsets; merged whole-flash/NVS images are excluded. Do not erase all flash merely to update. Saved calibration/pairing can remain only when the selected firmware and partition layout are compatible. No universal firmware-selection or physical voltage/direction validation is implied.

Mission example binaries intentionally contain zero keys and keep RF OFF. Use the supplied provisioning source to generate one matching private fleet set and compile that set locally. Never upload private generated Config.h, passphrases or device NVS to this collection. GPIO/power/driver/radio families differ; the three LoRa protocols are not interchangeable. Current Android Waypoint remains planning-only for the mission family. Hardware/field reliability, current, stopping latency and balance tuning remain NOT TESTED; execute each copied HIL guide before operation.

`build.py resolve`, `build.py compile --group GROUP`, and `build.py package` are the reproducible entrypoints. Run `python -m unittest discover -s firmware/latest -p 'test_*.py'` for catalog/package safeguards. Default release/toolchain/signing policies elsewhere remain unchanged.

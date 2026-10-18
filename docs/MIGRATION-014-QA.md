# PC TeleRC 0.1.4rc1 verification record

## Baseline and design

Desktop baseline: v0.1.3, `0edd09475dd4668a8793caf1402b15d3f35d0a1b`. TeleRC reference: release/elrs-recovery-081-20261018, `38b2310342f510b344ee4e6413e142a8f6533424`. Owner requested beneficial workflow/connection/telemetry migration and a DJI-style UI/release build on 18 October 2026. Repository contents override older chat claims.

Acceptance: preserve wheel/keyboard safety and original transport contracts; native Backpack must remain handset-authority/PING-only, resume bounded registration after telemetry loss, reject foreign endpoints before parsing, retain FC identity, and never send commands on stop/reconnect. Camera retries must retain exact source, cancel on Stop and leave control untouched. Camera/map swap/minimize must reuse instances and preserve offline behavior. Live telemetry must not renew heartbeat/GPS freshness indirectly. Firmware/preset sources must be identical to baseline.

## Software evidence

- PASS: 215 pytest checks on Linux/Python 3.12 with pinned PySide6 6.11.2, pymavlink 2.4.50, pygame-ce 2.5.8 and pyserial 3.5. Includes real localhost Backpack UDP/MAVLink retry and peer-rejection integration, PING-only command guards, camera retry cancellation/backoff/source retention, GPS-fix expiry and cockpit swap/collapse. No attached radio or rover was used.
- PASS: 13 Node release-verification regression checks; Python compileall and pip check.
- Tests isolate operator settings/cache into a temporary directory and replace the map tile endpoint with localhost. Localhost video/UDP integration remains enabled; no external map service receives test locations.
- PASS: all five unchanged firmware host suites (PWM/bridge, LoRa protocol, LilyGO Wi-Fi/LoRa, runtime and relays). These are host simulations, not newly measured board/RF behavior.
- Windows run `39131072472` passed all 215 application cases, 13 release-verification cases, executable/installer builds and all 20 frozen app checks. Its optional Actions artifact upload failed because account storage quota was full. Delivery now attaches the same required package types directly to the candidate release draft, after repeating the gates for the final commit; no older artifacts/releases are deleted.
- PASS: visual review of camera-first view, expanded-map view, 900×580 compact view and 900×580 Backpack settings drawer. Same camera/map objects remain connected; settings scroll to preserve operator access. Latest UI adds top-level Connect/Disconnect.
- Required cloud evidence: complete Windows regression, executable packaging, frozen real HTTP video decode, offline tile decode/no-network/no-fake-GPS, map swap/minimize/restore, command-lock check, installer and source packages, provenance and SHA256. The candidate workflow provides the authoritative results for its exact commit.
- Firmware is app-only unchanged. Host firmware suites are regression evidence only; prior v0.1.3 target builds remain the matching firmware baseline. Cloud verifies a zero diff for `firmware` and `stable_config`.

## Gates

| Gate | Status | Evidence |
| --- | --- | --- |
| A source / dependency | PASS locally; Windows workflow required | Review, compileall, pip check |
| B behavioral regression | PASS software | 215 pytest cases; 13 Node cases |
| C UI / media | PASS locally; frozen Windows required | Offscreen Qt render, real HTTP video, offline tiles |
| D compatibility | Software tested; hardware NOT TESTED | Existing profiles retained, firmware zero diff required |
| E restrained-wheel / installation / RF | BLOCKED | No PXN, Windows host, receiver, Backpack, F405 or rover attached |
| F package | Windows workflow required | Frozen app checks, installer, portable/source ZIPs and SHA256 |

No stable or physical reliability claim follows from software checks. Keep the candidate as a draft under the repository's candidate policy; v0.1.3 remains the rollback release. No extra firmware reflash or FC parameter patch is included.

## Review findings

Fixed an existing GPS freshness gap: a continuous GLOBAL_POSITION_INT stream could keep coordinates current after GPS_RAW_INT stopped. It now needs a fix timestamp no older than five seconds. Invalid/new low-quality fixes still inhibit position immediately. The prior test fixture was updated to model an actually received fix rather than inventing fix_type alone.

Old heartbeat age is checked before processing a newly received heartbeat and after receive time is resampled. This preserves a latched control stop through recovery. Camera errors/stalls have independent state and generation guards. The Backpack transport validates MAVLink checksum/type/source/target and rejects heartbeat/override/command/proprietary writes, including teardown.

Backpack and original Wi-Fi cannot bind the same local port in separate applications simultaneously. Configured PC listen address is visible for both UDP profiles. Profile edits save drafts without redirecting a live session; Apply & Reconnect closes old authority before the selected profile starts. Automatic registration does not scan for new peers, reopen serial devices, enable control or arm.

## Next check and rollback

Verify the Windows workflow's exact commit/provenance/checksums, install on Windows, then execute the six-step restrained-wheel acceptance in `docs/releases/v0.1.4rc1.md`. Roll back to v0.1.3 and restore the settings backup if needed. Retain existing independent FC and motor watchdogs and measure their actual stop behavior.

# v1.0 ecosystem baseline — release candidate

This branch establishes independent product ownership and versioned build inputs.
It is not a stable or field-qualified release. Existing release history is retained.

| Product | Role | Link | Current release scope |
| --- | --- | --- | --- |
| TeleRC | Base Android field controller | Wi-Fi | Single rover; setup, controls, diagnostics, waypoints, FPV |
| TeleRC Go | Consumer Android controller | Wi-Fi | Compact manual driving; explicit supported vehicle profiles |
| PC TeleRC | Industrial development baseline | LoRa Mission / local diagnostic links | Independent offline plans for IDs 1–20; one active mission session |

TeleRC is version 1.0.0/code1000. Go remains in the 1.0 family at
1.0.4/code1000 so upgrading from 1.0.3 does not reverse version ordering.
PC is 1.0.0rc1. Release-channel metadata remains candidate/prerelease even
where an Android package uses a numeric version name. Stable promotion is separate.

## Changes

- Base neutral checks now guard manual authority acquisition, including an already
  armed vehicle. Telemetry alone cannot restore driving authority.
- Go has an independent Gradle product; the legacy full-app source is retained as
  the source for explicitly shared modules/resources but is not a second app build.
- Editable Go four-motor/TT-car firmware is recovered from the versioned source
  packages. Four-motor/PWM failure regressions are included in its build gates.
- PC retains reviewed rc3 Windows packaging fixes and adds isolated per-rover
  offline drafts. Switching rover clears verification, old map telemetry and
  continuation/auxiliary authorization. It does not send a command.
- Every application records an ecosystem manifest, compatibility boundary, exact
  source/build provenance, checksums and independent release artifacts.

## Compatibility and security

MAVLink manual Wi-Fi, Go ownership telemetry, dedicated motor UART, legacy LoRa
manual transport and LoRa Mission TM2 are separate profiles. Never mix roles
because their filenames or application versions look similar. Firmware remains
independently versioned; this baseline does not alter a wire version to match 1.0.

Preserve CH1 steering/CH2 drive, 1500 us neutral, sparse PC override semantics,
local watchdogs, pre-arm checks and explicit authority reacquisition. Physical
ELRS takeover requires validated receiver wiring, channel/switch configuration
and a separate mode intervention for autonomous operation. A UI label is not
proof of receiver ownership. Unsupported ownership is UNKNOWN, not confirmed.

Legacy Wi-Fi MAVLink is not end-to-end authenticated. Endpoint locking and CRC
do not authenticate commands or prevent replay. Use it only within the restricted
test envelope; production command authentication is an unresolved release gate.
No private keys, keystores or generated provisioned fleet configurations belong
in source/release archives. Mission examples keep RF disabled until provisioned.

The PC mission network uses matched per-rover cryptographic provisioning and
fixed routes. It currently supports one active addressed rover session, not
simultaneous fleet monitoring or dynamic mesh routing. Twenty is the offline
identity/planning capacity and architecture target, not verified RF capacity.
Do not switch away from a running rover as a substitute for managing its GCS
failsafe: each vehicle's actual configured loss policy remains authoritative.

## Verification and promotion gates

Record source review, host tests, ASan/UBSan, JVM/Python tests, lint, actual-board
compilation, native Windows/frozen checks, signer continuity and package hashes
separately. Missing checks remain BLOCKED/NOT TESTED. Local LeakSanitizer can be
blocked by runtime ptrace restrictions; full default sanitizers remain required in CI.

Hardware/installed-device checks are BLOCKED without measurements: wheel mapping,
RC takeover in both directions, timeout and motion response, power/stall behavior,
mission continuation, F output OFF behavior, upgrade retention and field RF tests.
Use each repository's restrained-wheel procedure. No stable promotion until
critical gates pass for each advertised app/firmware/hardware pairing.

## Installation and rollback

Use the same Android application ID and signing identity, with increasing version
codes. A debug APK cannot upgrade a signed installed application. Unsigned release
output is diagnostic build output, not an installable release. Never substitute a
new signing key to make an upgrade pass. Go's dedicated private repository needs
its existing release signing secrets provisioned before signed publication.

Back up settings, plans, FC parameters and private radio provisioning. Preserve
NVS; never distribute or flash merged whole-chip images as an upgrade convenience.
Install only the matching board/profile's images at its recorded offsets.
Android downgrade normally needs uninstall and may erase application data; keep
the prior signed package and export plans first. PC keeps prior settings and
release downloads. Restore the whole tested app/firmware pairing when required.

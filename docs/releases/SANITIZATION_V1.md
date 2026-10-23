# v1.0.0 release packaging sanitation — 23 October 2026

Baseline: f976264d3bc8f0309f4ec3b76c5582e185182236, release/publish-v1.0.0.

## Changes and scope
- Source and final nested release archives reject private signing file formats,
  non-example .env variants, local machine configuration and provisioned/ambiguous
  mission headers. Public certificate files and explicit example configuration
  remain permitted.
- Reject traversal/absolute/Windows-drive paths, symlinks, encrypted archive
  members, duplicate entries and excessive archive nesting/expanded size.
  Android APK resources retain their valid case-sensitive namespace.
- PC source snapshots omit old ZIP/APK build output. Existing public mission hash allowlists and frozen Windows report requirements are retained.
- The final staged assets must pass sanitation before gh release create.
  Signing continuity, application/firmware builds and prerelease-only publication
  remain mandatory; an infrastructure failure cannot produce a release.
- No vehicle-control code, wiring, watchdog thresholds or firmware sources changed.
  Previous releases and the independent legacy/manual firmware catalog are retained.

## Evidence
- PASS: 17 standard-library packaging tests per product, including real source
  packager subprocesses rejecting accidental environment/signing/private-fleet
  inputs and excluding legacy archived binaries.
- PASS: Python syntax and workflow publication gate ordering review.
- PASS: archive checker exercised against the existing verified Base signed APK,
  source, evidence and six-profile firmware release set. This is a compatibility
  check of the shared archive checker, not a fresh Go or PC application build.
- BLOCKED pending CI: full signed Go and native Windows publication gates.
  Previous attempts failed before runner steps/logs. The new source commit
  will rerun all required build and packaging gates; no prior binary is relabeled.
- NOT TESTED: hardware failsafes/takeover, installed-device retention, electrical
  and field RF qualification. Stable promotion remains blocked.

This check detects the documented file/configuration classes and unsafe archive
structure; it is not an exhaustive credential scanner or firmware security
qualification. Existing Wi-Fi authentication and PC fleet-capacity limitations
remain documented in REALIGNMENT_V1.md. Next: inspect the new workflow's actual
jobs, restore Actions execution if it fails before steps, then complete signing/
native packaging and hardware qualification before stable promotion.

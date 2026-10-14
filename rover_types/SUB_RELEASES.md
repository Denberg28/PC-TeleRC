# Sub-release policy

Rover versions are independent of the Windows PC TeleRC version. Registering
mini v0.1.0 does not change the app version, rebuild an EXE, or publish a stable
application release. No Git tag is created by this documentation change.

## Identity and status

- Folder: `rover_types/<type>/releases/v<version>-<status>/`.
- Record ID: `rover-<type>-v<version>-<status>`.
- Status progression: `planned` -> `source-candidate` -> `test-candidate` ->
  `hardware-validated` -> `stable`, only when the corresponding evidence exists.
- Version increments: patch for compatible corrections, minor for compatible
  features/hardware variants, major for incompatible control or wiring contracts.
- A future published tag can use `rover-mini-v0.1.0-test-candidate`. Check CI tag
  filters before creating it; never repurpose the app's `v*` tags for a rover.

The mini's prior internal firmware string is `0.1.0-test-candidate`; registering
it in this catalog preserves those exact source bytes and version. The catalog
entry's date describes documentation, not a new firmware build.

## Required contents for a candidate

| Record | Required information |
|---|---|
| Type profile | Vehicle dimensions, drivetrain, steering, balancing needs, maturity |
| Hardware | Exact controller board, motor/driver versions, power and current budget |
| Wiring | Pin table, power/ground paths, startup-safe levels, per-actuator directions |
| Control contract | Units, ranges, neutral, channel mapping, mixing, arming and release |
| Safety response | Timeout, disconnect, reset, local stop, recovery and physical stop behavior |
| PC compatibility | Source/build tested, wheel/keyboard status, connection procedure |
| Reproduction | Build/upload instructions, dependencies and checksums |
| Evidence | Automated results plus measured hardware acceptance results or explicit gaps |

## Preservation

Keep the original release ZIP and its SHA-256 in the version's `archives/` and
`release.json`. The extracted `package/` must match that archive. New wrappers
such as `RELEASE.md` stay outside `package/`; do not silently revise a released
snapshot or regenerate its checksum list to conceal changes.

Corrections to a candidate's executable source or wiring create a new candidate
version. Append new hardware test evidence with its date and hardware identity;
do not rewrite old results into claims of hardware verification.

## Promotion gates

1. Requirements and failure response defined for the specific vehicle.
2. Actual target-board compilation/upload completes; API doubles alone are insufficient.
3. Automated control/packet checks pass for changed behavior.
4. Hardware direction, current/voltage/temperature, reset, stop and link-loss tests pass.
5. PC wheel and any advertised keyboard paths are tested with named app versions.
6. Review remaining limitations before a stable label or public stable release.

The mini currently meets only the documented source/package and host simulation
checks. Exact-board compilation and all hardware promotion gates remain open.

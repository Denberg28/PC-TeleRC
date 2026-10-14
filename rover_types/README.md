# Rover types

Vehicle-specific firmware, wiring, validation records and sub-releases for
PC TeleRC. This catalog is documentation and source packaging only: it does
not add a rover selector to the Windows app or change the main app version.

| Folder | Meaning | Status | Current sub-release |
|---|---|---|---|
| [mini](mini/README.md) | Small four-motor TT skid-steer baseline | Test candidate; hardware validation pending | [v0.1.0-test-candidate](mini/releases/v0.1.0-test-candidate/RELEASE.md) |
| [balancing](balancing/README.md) | Vehicle requiring active balance control | Planned; requirements only | None |
| [mono](mono/README.md) | Reserved mono concept; architecture undecided | Planned; definition needed | None |
| [four_wheel_steering](four_wheel_steering/README.md) | Four wheels with controlled steering geometry | Planned; requirements only | None |
| [two_wheel_drive](two_wheel_drive/README.md) | Two driven wheels; steering layout undecided | Planned; requirements only | None |
| [tracked](tracked/README.md) | Left/right track drive | Planned; requirements only | None |
| [ackermann](ackermann/README.md) | Conventional front steering geometry | Planned; requirements only | None |

These names describe different dimensions: `mini` is a size/build class,
`two_wheel_drive` is a drivetrain, and `four_wheel_steering` is a steering
architecture. They can overlap. Each profile records motor count, driven wheels,
steering architecture and balance requirements explicitly; the folder name
alone must never select a mixer or a safety behavior.

The current mini has **four driven wheels with skid steering**. It is not the
four-wheel-steering profile, and it is not a two-wheel-drive implementation.

## Folder convention

Each type has `README.md` and `profile.json`. Once a candidate exists, retain
its complete package beneath `releases/<version>/`. Mini establishes the layout:

- `mini/releases/v0.1.0-test-candidate/RELEASE.md`: scope, validation and compatibility.
- `mini/releases/v0.1.0-test-candidate/release.json`: sub-release record and package checksum.
- `mini/releases/v0.1.0-test-candidate/package/`: original sketch, wiring, diagram and tests.
- `mini/releases/v0.1.0-test-candidate/archives/`: downloadable original ZIP.

Planned profiles have no placeholder firmware, fake releases, or unverified pin
assignments. Add a new version directory when behavior or hardware changes;
preserve prior snapshots. See [SUB_RELEASES.md](SUB_RELEASES.md).

## Operator input and transport boundary

PC wheel/pedal input becomes steering and drive demand. A keyboard input source
must be implemented and verified in the PC app before it is advertised as
available. Firmware cannot add Windows keyboard handling. The mini package
checks the existing CH1/CH2 MAVLink wire contract, not a keyboard-enabled EXE.

Sharing Wi-Fi/UDP framing does not make control algorithms interchangeable.
Balance loops and actuator limits belong in the vehicle firmware. Do not send
raw remote PWM into a future balancing controller without its own validated
control and safety design.

## Next work

1. Compile/upload mini on the exact ESP32-S3 board and complete its bench checklist.
2. Record actual TT motor/driver/supply specifications and measured stop timing.
3. Verify the intended PC TeleRC wheel and keyboard input paths separately.
4. Select the next vehicle architecture and document its hardware before firmware.
5. Add app profile selection only after the per-type contracts are defined.

See [ROADMAP.md](ROADMAP.md) for per-type milestones. No stable-release claim
is made for any new rover type in this catalog.

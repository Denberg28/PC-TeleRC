# PC TeleRC v1.2.0rc9 — Recovery reliability review

Date: 29 October 2026. Source baseline: published rc8,
`37e9dc696f9183317da92bda021c2abe1a32aee3`.
Application-only candidate; firmware and private pairing are unchanged.

## Reproduced defects and changes

| Trigger | Previous behavior | Current behavior |
| --- | --- | --- |
| Open malformed/oversized/future-version/non-UTF-8 saved draft; close untouched | Empty editor overwrote unreadable original | Original bytes remain unchanged |
| Edit after failed draft restore | Next save discarded damaged original | Exclusive per-rover recovery copy precedes replacement |
| Recovery copy fails | No prior copy guard | Replacement is blocked; original remains |
| Standalone rover ID changes while save fails | New rover loaded and old unsaved edit lost | ID reverts; editor and path remain on original rover |
| BASE opens; USB preference write fails | USB owner existed behind Open BASE label and editable port | Close BASE and disabled port correctly reflect ownership; preference error shown |

Recovery copying is streamed to avoid loading oversized drafts into memory.
Incomplete copies are removed on failure; existing recovery files are never
overwritten. Once a replacement saves successfully, later saves do not create
duplicate recovery copies. An untouched failed restore creates no backup and
does not write an empty replacement. Copies preserve data for manual review;
no automatic content repair, route execution or command permission is inferred.

## Verification

The new regression module reproduces all eight initial failures on rc8. Current
coverage includes malformed JSON, invalid UTF-8, future versions, oversized
drafts, editing after restore failure, backup-write failure, failed-save ID
switching and a fake USB owner with a real settings-write exception.

Four new frozen executable checks require untouched draft retention, exact-byte
recovery copying, no command authority from recovery and consistent BASE state
under preference failure. These run through actual Qt editors and filesystem
operations. The BASE lifecycle check uses an in-memory owner and opens no USB.

The complete current Windows suite and frozen checks remain mandatory. Linux
native firmware role guards under ASan/UBSan and the encrypted addressed graph
run again. Original eleven real board-build records are reused only after
unchanged firmware and archive hashes are verified. Source and nested archive
sanitation, exact commit provenance, complete asset inventory and downloaded
SHA-256 verification gate public publication. Current results accompany the
release in test-evidence.zip; historical rc8 results are not current evidence.

## Retained feature scope

The complete UI/function inventory remains in `docs/FEATURE-REVIEW-rc8.md` in the
source package. Fleet planning, native/WPL files, per-rover history, raster maps,
genuine live/stale GPS, verified upload/readback, normal Arm, one-shot Start,
Disarm, HOLD and modeless read-only FC inspection retain their existing gates.
The dark layout/icon and route schema are unchanged. Screenshot DARK-UI.png is
the rc8 preview, reused intentionally. No firmware bytes, pairing, watchdogs,
command protocol, FC parameters or authority policy change.

No integrated video, collision avoidance, synchronized fleet start or automatic
reconnect/arm/start/resume is added. Unknown command outcomes still require
deliberate recovery. HOLD does not guarantee auxiliary OFF. Address bounds do
not establish measured simultaneous RF capacity.

## Qualification and rollback

This is a prerelease. Physical RF, stopping, RC takeover, auxiliary OFF, fleet
capacity and real installed/display-scaling acceptance remain unqualified.
The app remains unsigned. Existing rc8/rc7/rc6 and stable releases are retained.
The designated mission baseline remains rc6. Existing fleet 0.5.0rc1 / converter
1.0.5 private pairing remains valid, with no reflash needed.

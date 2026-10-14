# PC TeleRC 0.1.1rc5 / LilyGO SX1262 0.2.0

Install the new Windows portable build or installer. Flash BASE and ROVER sketches to two LilyGO T3-S3 SX1262 boards, then provision the pair in LoRa Setup.

Read `docs/LILYGO-SX1262-ARDUROVER.md` for wiring, pairing and acceptance tests. BASE connects to PC native USB; ROVER GPIO44 receives FC T3, GPIO43 transmits to FC R3, with common ground. The separate motor PWM converter remains in place.

The new firmware removes Wi-Fi from this control path and reports rover radio stops to the PC. It does not prove that Wi-Fi caused the earlier ground/bump stops. No FC parameter file is applied automatically.

Current release details: `docs/releases/v0.1.1rc5.md`. Historical rc4 review: `REVIEW-DROPOUTS.md` and `docs/evidence/rc4/`. Existing mesh development is preserved separately under `bridge/TeleRCMesh` in GitHub.

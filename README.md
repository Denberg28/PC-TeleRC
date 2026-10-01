# PC TeleRC

PC TeleRC is a Windows-first rover control bridge based on TeleRC: MAVLink comes from the ESP32-S3 Wi-Fi bridge, and a PXN or compatible steering wheel provides steering/pedal input.

**Current version:** `0.1.0a3` — diagnostics/hardware-test milestone.

## Operator flow
1. Connect the PC to the ESP32-S3 rover network.
2. Start PC TeleRC; it listens on UDP 14550 by default.
3. Select the intended PXN/controller. Once a controller GUID is selected, PC TeleRC will not silently fall back to another joystick.
4. Run **Calibrate wheel & pedals**. Capture neutral, steering extremes, and pedal extremes.
5. Verify live Steer/Drive values and apply settings.
6. Confirm MAVLink heartbeat and neutral pedals.
7. ARM explicitly if needed, then enable PC control.
8. Drive. Stale controller data or heartbeat latches PC control OFF.
9. Disable/exit sends neutral, then releases steering/throttle overrides when the link is still available.

## Included
- MAVLink UDP receive/transmit with pymavlink.
- PXN/SDL-compatible wheel discovery with pygame-ce.
- Guided calibration with automatic axis detection and inversion.
- Read-only troubleshooting diagnostics with copyable report.
- Separate/combined pedal modes, steering deadzone/expo, and throttle limiting.
- Explicit Apply Settings vs. Apply & Reconnect workflow.
- Configurable CH1 steering / CH3 throttle defaults.
- Explicit ARM/DISARM; never auto-arm.
- 20 Hz RC override only while control is explicitly enabled.
- 350 ms controller watchdog and 3 s heartbeat watchdog.
- 25% default throttle authority for first tests.
- Atomic local settings at `%LOCALAPPDATA%\PC-TeleRC\settings.json`.
- Windows CI, PyInstaller portable EXE and SHA-256 artifact.

## Database decision
No cloud/server database is used in the control path. Configuration is local JSON. If session history is added later, local SQLite is the recommended first persistence layer.

## Diagnostics
Use **Diagnostics** to inspect MAVLink worker state, heartbeat age, RX/TX counts, vehicle identity/mode, detected and selected controller GUID, controller freshness, throttle-neutral state, axis mapping validity, RC channel mapping, pending settings, fail-safe state, and throttle limit. The report is read-only and can be copied to the clipboard for troubleshooting.

## Safety
The PC cannot guarantee a final neutral packet after Wi-Fi disappears. Configure ArduRover's independent GCS/telemetry fail-safe before powered testing. See `docs/ARDUPILOT.md`.

Calibration always runs with PC control disabled and does not ARM the vehicle.

## Run from source
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
python -m pctelerc
```

## Build
```powershell
pyinstaller --noconfirm --clean PC-TeleRC.spec
```
Output: `dist\PC-TeleRC.exe`.

Every push to main runs syntax checks, unit tests and the Windows build. The resulting EXE and `SHA256.txt` are uploaded as Actions artifacts. A `v*` tag publishes a GitHub Release, so tags are reserved for deliberate release publication.

## Acceptance criteria
- Windows CI installs Python 3.12 dependencies and passes tests.
- CI emits PC-TeleRC.exe + SHA256.txt.
- App stays open without hardware and reports missing wheel/link.
- Guided calibration rejects insufficient movement and saves detected axes/inversion.
- A selected controller disappearing cannot cause an unrelated joystick to take control.
- Heartbeat makes link Connected immediately after receipt.
- Control cannot enable with unapplied settings, unhealthy MAVLink, stale wheel input, or non-neutral throttle.
- Active output is bounded to 1000–2000 us, with throttle limited to 1375–1625 us by default.
- Controller >350 ms stale or heartbeat >3 s stale disables/latches PC control.
- Reconnect never resumes PC control automatically.
- Disable/exit sends neutral and releases the two RC overrides if network remains available.
- No credentials, Wi-Fi passwords, signing keys or user-specific paths are committed.

## First powered test
Raise the driven wheels so the rover cannot propel itself. Verify calibration and axis directions before motor power. Then test wheel unplug and Wi-Fi loss independently. The rover-side ArduRover fail-safe must provide the safe action even if the PC cannot send another packet.

See `AGENTS.md`, `docs/DECISIONS.md`, `docs/BUTTON_AUDIT.md`, and `docs/TESTING.md` for continuity.

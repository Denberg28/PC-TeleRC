# PC TeleRC

PC TeleRC is a Windows-first rover control bridge based on the TeleRC direction: MAVLink comes from the ESP32-S3 Wi-Fi bridge, and a PXN or compatible steering wheel provides steering/pedal input.

**Current version:** `0.1.0a1` — test milestone.

## MVP flow
1. Connect the PC to the ESP32-S3 rover network.
2. Start PC TeleRC; it listens on UDP 14550.
3. Plug in the PXN wheel and verify live axis values.
4. Map steering, throttle and brake axes; invert if required.
5. Confirm heartbeat and neutral pedals.
6. Arm explicitly if needed, then enable PC control.
7. Drive. Stale controller data or heartbeat latches PC control OFF.
8. Disable/exit sends neutral, then releases steering/throttle overrides.

## Included
- MAVLink UDP receive/transmit with pymavlink.
- PXN/SDL-compatible wheel discovery with pygame-ce.
- Separate/combined pedal modes, inversion, steering deadzone/expo.
- Configurable CH1 steering / CH3 throttle defaults.
- Explicit ARM/DISARM; never auto-arm.
- 20 Hz RC override only while control is explicitly enabled.
- 350 ms controller watchdog and 3 s heartbeat watchdog.
- 25% default throttle authority for first tests.
- Atomic local settings at `%LOCALAPPDATA%\PC-TeleRC\settings.json`.
- Windows CI, PyInstaller portable EXE and SHA-256 artifact.

## Database decision
No cloud/server database in the MVP. Control reliability improves by removing that dependency. Configuration is local JSON. If session history is needed later, use local SQLite first.

## Safety
The PC cannot guarantee a final neutral packet after Wi-Fi disappears. Configure ArduRover's independent GCS/telemetry failsafe before powered testing. See `docs/ARDUPILOT.md`.

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
- Heartbeat makes link Connected immediately after receipt.
- Control cannot enable without healthy MAVLink, fresh wheel input and neutral throttle.
- Active output is bounded to 1000–2000 us, with throttle limited to 1375–1625 us by default.
- Controller >350 ms stale or heartbeat >3 s stale disables/latches PC control.
- Disable/exit sends neutral and releases the two RC overrides if network remains available.
- No credentials, Wi-Fi passwords, signing keys or user-specific paths are committed.

## First powered test
Raise the driven wheels so the rover cannot propel itself. Verify axes before motor power. Then test wheel unplug and Wi-Fi loss independently. The rover-side ArduRover failsafe must provide the safe action even if the PC cannot send another packet.

See `AGENTS.md`, `docs/DECISIONS.md`, and `docs/TESTING.md` for continuity.

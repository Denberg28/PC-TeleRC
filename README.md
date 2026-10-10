# PC TeleRC

## Radio dropdown candidate — v0.1.1rc1

Built directly from the stable [v0.1.0a10](https://github.com/Denberg28/PC-TeleRC/releases/tag/v0.1.0a10) commit `7b84b7882c4010c34f158304cc9c8c8cc4cba77b`. The stable release remains the recommended download. This candidate adds three connection profiles without importing later controller or UDP implementations.

| Connection dropdown | PC connection | Required radio path |
| --- | --- | --- |
| ESP32-S3 · Wi-Fi | Existing MAVLink UDP, port 14550 | PC Wi-Fi → ESP32-S3 bridge → rover |
| LilyGO T3S3 SX1262 · LoRa | Native USB CDC, 115200 | PC → paired BASE → LoRa → paired ROVER → TeleRC DIRECT motor controller |
| HGLRC T ONE 900 MHz · ELRS | USB MAVLink, 460800 | PC → compatible ELRS TX → bound MAVLink RX → flight controller |

Choose a profile, set its endpoint, then **Apply & Reconnect**. Wi-Fi remains the default for existing a10 settings. Each radio has its own saved COM port. Changing a field disables PC Control; Apply Settings saves a connection draft without switching the live link. Disconnect cancels a pending reconnect. Every reopened session requires a fresh vehicle heartbeat and manual control enable.

**LoRa:** Use current [TeleRC paired firmware](https://github.com/Denberg28/TeleRC/tree/67b2cf5137989c1a6a65a4b02af960105d04afa3/bridge), not Meshtastic or transparent serial firmware. The app verifies an active SX1262 BASE before driving. LoRa Setup reads/provisions one board at a time; pairing secrets are masked and kept in memory only. The driving profile requires CH1 steering / CH2 drive and DIRECT motor control; AUTOPILOT driving through this LoRa profile is not implemented. Center the wheel and release pedals before enabling. Initial motor FAILSAFE allows only neutral commands while waiting for DIRECT; ARM remains blocked until DIRECT and PC Control are confirmed.

**ELRS:** This is a USB MAVLink transport, not CRSF output to a module bay. Both radios need compatible ExpressLRS 3.5+ firmware and MAVLink mode; the T ONE's exact USB data path must be verified physically. No RF flashing or transmitter arbitration is performed. Controls run at 5 Hz to reduce 900 MHz traffic. Select a sufficiently fast RF packet mode and keep vehicle telemetry low; a fast USB baud rate does not increase RF capacity. The [official ExpressLRS MAVLink guide](https://www.expresslrs.org/software/mavlink/) documents setup and throughput. Pocket takeover has not been validated.

See [candidate notes](docs/releases/v0.1.1rc1.md) for test evidence and hardware checks.



PC TeleRC is a Windows-first rover control bridge based on TeleRC: MAVLink comes from the ESP32-S3 Wi-Fi bridge, and a PXN or compatible steering wheel provides steering/pedal input.

**Current version:** `0.1.0a10` — Android-aligned CH1 steering / CH2 drive mapping.

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
- Minimal, modeless read-only diagnostics with four live checks and a copyable support report.
- Separate/combined pedal modes, steering deadzone/expo, adjustable steering sensitivity, and throttle limiting.
- Explicit Apply Settings vs. Apply & Reconnect workflow.
- Configurable CH1 steering / CH2 drive defaults, matching Android TeleRC.
- Explicit ARM/DISARM; never auto-arm.
- 20 Hz RC override only while control is explicitly enabled.
- 350 ms controller watchdog and 3 s heartbeat watchdog.
- Session vehicle-ID lock: foreign MAVLink vehicle heartbeats are ignored.
- Fail-closed controller-axis validation and duplicate RC-channel blocking.
- Multi-attempt neutral/release sequence on control shutdown/fail-safe.
- Any live configuration edit disables PC Control and requires manual re-enable.
- 25% default throttle authority for first tests.
- Atomic local settings at `%LOCALAPPDATA%\PC-TeleRC\settings.json`.
- Windows CI, PyInstaller portable EXE, Inno Setup installer, and SHA-256 artifacts.
- Single-instance application guard to prevent duplicate UDP listeners.
- Targeted Windows socket diagnostics for UDP bind errors 10048 and 10013.
- Reconnect waits briefly for the previous UDP listener to release before rebinding.

## Database decision
No cloud/server database is used in the control path. Configuration is local JSON. If session history is added later, local SQLite is the recommended first persistence layer.

## Diagnostics
Use **Diagnostics** for four live field checks only: **Link, Controller, Mapping, Safety**. The window is modeless and refreshes every 2 seconds, so it does not block ARM/DISARM or PC Control. Detailed technical context is generated only when **Copy Report** is pressed.

## Controller sensitivity
**Steering sensitivity** adjusts steering authority from 25–100%. At 100% the configured deadzone/expo curve can command full steering; lower values proportionally reduce maximum steering command. **Steering expo** remains the independent control for center-response curvature. Throttle authority remains controlled separately by **Throttle limit**.

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

## Field-readiness status
The software workflow is simulated and CI-tested, but real field readiness is not claimed until the PXN, ESP32-S3, SpeedyBee/ArduRover, motor drivers, and Wi-Fi failure modes are physically exercised. See `docs/FIELD_READINESS.md`.

## First powered test
Raise the driven wheels so the rover cannot propel itself. Verify calibration and axis directions before motor power. Then test wheel unplug and Wi-Fi loss independently. The rover-side ArduRover fail-safe must provide the safe action even if the PC cannot send another packet.

See `AGENTS.md`, `docs/DECISIONS.md`, `docs/BUTTON_AUDIT.md`, and `docs/TESTING.md` for continuity.


## Code-review baseline
The v0.1.0a6 review verifies feature/documentation alignment, exact runtime/dev dependency pins, `pip check`, version consistency, headless Qt UI construction, equal main-card column geometry, modeless diagnostics, unit/integration tests, and the Windows PyInstaller build.


## Windows UDP troubleshooting
- **WinError 10048** is shown as: UDP port already in use. Close Mission Planner, another PC TeleRC instance, MAVProxy/QGroundControl, or another MAVLink listener.
- **WinError 10013** is shown as: Windows denied access to the UDP port. Check excluded UDP port ranges or security/network software.
- PC TeleRC now prevents a second application instance from starting.


## v0.1.0a8 networking architecture
PC TeleRC now keeps one bound UDP socket for the application session and uses that same socket for MAVLink receive/transmit. Changing only the ESP32 target IP/port updates the live socket without rebinding UDP 14550. The listener restarts only when the listen address or listen port actually changes.

The installed build now uses PyInstaller **onedir** inside the Inno Setup installer instead of one-file extraction. This removes the normal PyInstaller parent/child process pair from the installed application and gives a cleaner field deployment.


## Bridge control wire format
PC TeleRC receives MAVLink 1 or MAVLink 2 telemetry normally. All bridge-facing control traffic (GCS heartbeat, ARM/DISARM, RC override, neutral and release) is deliberately encoded as MAVLink 1 from system 255 / component 190 so it remains compatible with the TeleRC ESP32-S3 command filter and Android TeleRC control envelope.

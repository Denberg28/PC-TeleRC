# PC TeleRC

PC TeleRC is a Windows-first rover control bridge based on TeleRC: MAVLink comes from the ESP32-S3 Wi-Fi bridge, and a PXN or compatible steering wheel provides steering/pedal input.

**Current version:** `0.1.0a13` — sensitivity slider and reviewed connection/control reliability.

## Operator flow
1. Connect the PC to the ESP32-S3 rover network.
2. Start PC TeleRC; it listens on UDP 14550 by default.
3. Select the intended PXN/controller. Once a controller GUID is selected, PC TeleRC will not silently fall back to another joystick.
4. Run **Calibrate wheel & pedals**. Capture neutral, steering extremes, and pedal extremes.
5. Verify live Steer/Drive values and apply settings.
6. Confirm MAVLink heartbeat and neutral pedals.
7. ARM explicitly if needed, then enable PC control.
8. Drive. Stale controller data or heartbeat latches PC control OFF.
9. **Disable PC Control** sends neutral, then releases CH1/CH2 for transmitter handover. The telemetry connection stays open.
10. **Disconnect** sends neutral/release if PC control owns the overrides, stops GCS heartbeats, and closes the UDP socket. Disconnect does not disarm the rover.
11. **Apply & Connect/Reconnect** stops the old session before applying network settings and opening a new session. Wait for a fresh rover heartbeat, verify neutral pedals, and enable control manually.

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
- Reconnect waits for the previous worker to exit and close its UDP socket before rebinding.

## Database decision
No cloud/server database is used in the control path. Configuration is local JSON. If session history is added later, local SQLite is the recommended first persistence layer.

## Diagnostics
Use **Diagnostics** for four live field checks only: **Link, Controller, Mapping, Safety**. The window is modeless and refreshes every 2 seconds, so it does not block ARM/DISARM or PC Control. Detailed technical context is generated only when **Copy Report** is pressed.

## Controller sensitivity
**Steering sensitivity** uses a horizontal slider with the percentage below the bar, like Android TeleRC, to adjust steering authority from 25–100%. At 100% the configured deadzone/expo curve can command full steering; lower values proportionally reduce maximum steering command. **Steering expo** remains the independent control for center-response curvature. Throttle authority remains controlled separately by **Throttle limit**. Moving the slider disables active PC control; click **Apply Settings**, then manually enable PC control with neutral pedals. The applied percentage is saved for the next launch.

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
Output: `dist\PC-TeleRC\PC-TeleRC.exe`; ship the complete folder or installer.

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


## Networking architecture
PC TeleRC keeps one bound UDP socket per connected session for receive/transmit. The first accepted ArduRover autopilot heartbeat locks the vehicle system/component and UDP source endpoint. Fixed ESP32 target IP settings filter received traffic before parsing. Dynamic routing sends only to the accepted vehicle peer and never broadcasts commands to other UDP clients. A changed bridge IP/source port requires explicit reconnect.

**Apply Settings** saves controller settings while leaving pending network changes inactive. Pending network changes block ARM and control enable until **Apply & Connect/Reconnect** starts a new session. A monitor-only session does not send RC neutral/release on disconnect. Use one active controller application at a time; the bridge is not an ownership arbiter.

MAVLink 1 commands remain unsigned and unencrypted. Peer pinning is traffic isolation, not cryptographic authentication. Use the private rover network and a fixed ESP32 IPv4 address. Signing would require a coordinated bridge upgrade; this review does not change the Android app or ESP32 firmware.

The installed build now uses PyInstaller **onedir** inside the Inno Setup installer instead of one-file extraction. This removes the normal PyInstaller parent/child process pair from the installed application and gives a cleaner field deployment.


## Bridge control wire format
PC TeleRC receives MAVLink 1 or MAVLink 2 telemetry normally. All bridge-facing control traffic (GCS heartbeat, ARM/DISARM, RC override, neutral and release) is deliberately encoded as MAVLink 1 from system 255 / component 190 so it remains compatible with the TeleRC ESP32-S3 command filter and Android TeleRC control envelope.


## Reliability review (2026-10-03)
See [docs/REVIEW-2026-10-03.md](docs/REVIEW-2026-10-03.md) for verified defects, fixes, test evidence, compatibility boundaries, and remaining field validation.

## Independent sensitivity and ELRS

Steering and drive now have separate 25–100% sliders. Drive gain applies before the throttle limit; ARM/enable still require unscaled neutral pedals.

Experimental ELRS external TX USB MAVLink mode uses a selected COM port at 460800 baud. It requires compatible module/receiver firmware; it is not a raw CRSF module-bay adapter. HGLRC T ONE USB capability and concurrent Pocket/PC control are not hardware verified. See [ELRS setup and limits](docs/ELRS.md).

## LilyGO T3-S3 SX1262 mesh connection sketch

A separate bench-test firmware candidate is available in [bridge/TeleRCMesh](bridge/TeleRCMesh/README.md). The same sketch configures gateway, relay and rover roles, up to two relay boards per path, and a raw ArduRover or framed TeleRC motor UART backend. It retains the normal PC UDP connection at 192.168.4.1:14550, CH1 steering / CH2 drive. Mesh firmware is a paired upgrade for every radio board; it is not Meshtastic or ELRS compatible. Hardware range, stopping time and paired integration remain unverified; see its setup/wiring guide and verification record.

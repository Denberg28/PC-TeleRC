# Verification record

## Automated
Run:
```powershell
python -m compileall -q src tests main.py
python -m pytest -q
pyinstaller --noconfirm --clean PC-TeleRC.spec
```

Automated coverage includes:
- input shaping and PWM limiting,
- heartbeat/controller watchdog logic,
- settings persistence/clamping,
- separate-pedal calibration,
- reversed driver-axis inversion,
- combined-pedal calibration,
- rejection of insufficient steering movement,
- diagnostics healthy/failure states,
- duplicate RC-channel detection,
- end-to-end field workflow state simulation,
- first-vehicle MAVLink system-ID lock and foreign-heartbeat rejection,
- steering sensitivity gain/clamping behavior,
- targeted four-state diagnostics.

## UI/button review
See `docs/BUTTON_AUDIT.md`.

## Hardware matrix — not yet executed
1. PXN enumerates and reads in background.
2. Selected PXN GUID is retained; removing it does not select another joystick.
3. Calibration detects steering/throttle/brake axes correctly on the actual PXN mode/driver.
4. ESP32-S3 heartbeat arrives over Wi-Fi.
5. Apply & Reconnect restarts the listener and does not resume PC control.
6. ARM/DISARM reaches ArduRover.
7. CH1/CH2 overrides move intended outputs.
8. Wheel unplug causes safe behavior.
9. Wi-Fi loss triggers independent ArduRover GCS fail-safe.
10. Reconnect does not resume drive automatically.
11. Diagnostics correctly identifies heartbeat/controller/mapping faults without sending commands.
12. Copy Diagnostic Report copies the displayed report.
13. Foreign MAVLink heartbeat does not switch vehicle identity.
14. Editing/applying settings while control is active forces PC Control OFF.
15. Override transport failure latches PC Control OFF.
16. Diagnostics window remains modeless while ARM/DISARM/control buttons remain available.
17. Sensitivity changes steering gain only; 100% retains full authority and lower values reduce maximum steering.
18. Exit sends repeated neutral/release attempts while link is available.


## UI/dependency review gate
- `pip check` must pass after installation.
- Headless Qt smoke test must construct MainWindow.
- Dropdown pages must fit the compact window; irrelevant UDP/USB fields must hide for the selected mode. STOP stays visible across pages.
- Diagnostics must instantiate as non-modal.
- Package version must match `pyproject.toml`.


## 0.1.0a7 Windows UDP reliability
- Duplicate application instance must be rejected before creating another MAVLink listener.
- WinError 10048 must produce a targeted "UDP port already in use" operator message.
- WinError 10013 must produce a targeted Windows permission/excluded-port operator message.
- Diagnostics Link row must surface the targeted socket failure.
- Apply & Reconnect must stop the previous worker before starting a new listener.


## Current connection lifecycle
- Exactly one UDP MAVLink socket is bound per connected session.
- All network changes require explicit disconnect/reconnect; pending changes cannot reroute the live socket.
- Disconnect closes the port and reconnect resets vehicle identity/input.
- Duplicate start calls must be idempotent.
- Installed onedir build must launch one normal application process.


## 2026-10-03 review validation
- 80 tests passed locally on Linux/Python 3.12; syntax compilation and pip check passed.
- Real UDP CH1/CH2 output, neutral/release sequence, closed-port reuse, and reconnect tested.
- Concurrent disable/tick, invalid frames, worker stalls, socket send failure, pending network edits, save failures, and ARM/DISARM feedback tested.
- Multi-peer routing, multi-message datagram source integrity, and exclusive listener ownership tested.
- Windows build/installer CI and physical hardware validation remain separate checks. See REVIEW-2026-10-03.md.

## 0.1.0a14 LoRa / dropdown verification
- 110 automated tests pass locally; compileall and pip check pass.
- Native USB CRC/fragments/corruption/expiry, setup parsing/state/timeouts, wrong/inactive board, no persisted key, wheel drive/ARM/release/disconnect/reconnect and navigation-stop tests pass.
- UI visually inspected at 800×720 and 640×600.
- Windows test/build gate is provided by CI; HIL remains NOT TESTED. See [LORA.md](LORA.md).

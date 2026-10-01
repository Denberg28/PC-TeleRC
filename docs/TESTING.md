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
7. CH1/CH3 overrides move intended outputs.
8. Wheel unplug causes safe behavior.
9. Wi-Fi loss triggers independent ArduRover GCS fail-safe.
10. Reconnect does not resume drive automatically.
11. Diagnostics correctly identifies heartbeat/controller/mapping faults without sending commands.
12. Copy Diagnostic Report copies the displayed report.
13. Foreign MAVLink heartbeat does not switch vehicle identity.
14. Editing/applying settings while control is active forces PC Control OFF.
15. Override transport failure latches PC Control OFF.
16. Diagnostics window remains modeless while ARM/DISARM/control buttons remain available.
17. Sensitivity changes steering response only and preserves full steering endpoints.
18. Exit sends repeated neutral/release attempts while link is available.


## UI/dependency review gate
- `pip check` must pass after installation.
- Headless Qt smoke test must construct MainWindow.
- Main three-card layout must retain equal column stretch/minimum widths.
- Diagnostics must instantiate as non-modal.
- Package version must match `pyproject.toml`.

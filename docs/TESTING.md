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
- rejection of insufficient steering movement.

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
11. Exit sends neutral/release while link is available.

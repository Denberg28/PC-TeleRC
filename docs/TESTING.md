# Verification record

## Automated
Run:
```powershell
python -m compileall -q src tests main.py
python -m pytest -q
pyinstaller --noconfirm --clean PC-TeleRC.spec
```

Local pure-logic run on 2026-10-01: 8 tests passed.

## Hardware matrix — not yet executed
1. PXN enumerates and reads in background.
2. Exact steering/pedal axes map correctly.
3. ESP32-S3 heartbeat arrives over Wi-Fi.
4. ARM/DISARM reaches ArduRover.
5. CH1/CH3 overrides move intended outputs.
6. Wheel unplug causes safe behavior.
7. Wi-Fi loss triggers independent ArduRover GCS fail-safe.
8. Reconnect does not resume drive automatically.
9. Exit sends neutral/release while link is available.

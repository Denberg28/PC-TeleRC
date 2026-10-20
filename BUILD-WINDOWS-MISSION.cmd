@echo off
setlocal
cd /d "%~dp0"
py -3.12 -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -e ".[dev]"
if errorlevel 1 goto failed
set QT_QPA_PLATFORM=offscreen
.venv\Scripts\python.exe -m pytest -q
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pytest -q firmware\mission\tests\test_tools.py firmware\mission\tests\test_mission_simulation.py
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean PC-TeleRC.spec
if errorlevel 1 goto failed
.venv\Scripts\python.exe scripts\verify_desktop_package.py
if errorlevel 1 goto failed
dist\PC-TeleRC\PC-TeleRC.exe --self-test-ui windows-frozen-check.json
if errorlevel 1 goto failed
if not exist release-dist mkdir release-dist
xcopy /e /i /y firmware\mission dist\PC-TeleRC\Mission-firmware
if errorlevel 1 goto failed
copy docs\MISSION-PLANNING.md dist\PC-TeleRC\MISSION-PLANNING.md
powershell -NoProfile -Command "Compress-Archive -Path dist\PC-TeleRC\* -DestinationPath release-dist\PC-TeleRC-portable-v0.1.5rc2.zip -Force"
if errorlevel 1 goto failed
echo Verified Windows portable package: release-dist\PC-TeleRC-portable-v0.1.5rc2.zip
exit /b 0
:failed
echo Build or validation failed. No verified Windows release was produced.
pause
exit /b 1

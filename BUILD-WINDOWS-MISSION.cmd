@echo off
setlocal
cd /d "%~dp0"
py -3.12 scripts\build_windows_mission.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo Build or validation failed. No verified Windows release was produced.
pause
exit /b 1

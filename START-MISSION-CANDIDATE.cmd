@echo off
setlocal
cd /d "%~dp0"
py -3.12 -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -e .
if errorlevel 1 goto failed
.venv\Scripts\python.exe main.py
exit /b %errorlevel%
:failed
echo Install Python 3.12 and check the error above. No radio has been opened.
pause
exit /b 1

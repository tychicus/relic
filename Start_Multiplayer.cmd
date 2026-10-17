@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 server.py --host 0.0.0.0
  goto finished
)
where python >nul 2>nul
if not errorlevel 1 (
  python server.py --host 0.0.0.0
  goto finished
)
echo Python 3.11 or newer is needed. Install it from https://www.python.org/downloads/windows/
:finished
echo.
pause

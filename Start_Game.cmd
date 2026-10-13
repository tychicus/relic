@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 server.py
  goto finished
)
where python >nul 2>nul
if not errorlevel 1 (
  python server.py
  goto finished
)
echo.
echo Python 3 is needed once to run this game.
echo Install Python 3.11 or newer from https://www.python.org/downloads/windows/
echo Enable "Add python.exe to PATH" during installation if offered.
echo Then double-click Start_Game.cmd again.
:finished
echo.
pause

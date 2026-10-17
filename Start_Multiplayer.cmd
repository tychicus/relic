@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 goto run_py
where python >nul 2>nul
if not errorlevel 1 goto run_python
echo Python 3.11 or newer is needed. Install it from https://www.python.org/downloads/windows/
goto failed
:run_py
py -3 server.py --host 0.0.0.0
goto finished
:run_python
python server.py --host 0.0.0.0
:finished
if errorlevel 1 goto failed
exit /b 0
:failed
echo.
pause
exit /b 1

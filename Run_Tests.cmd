@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -X utf8 -m unittest discover -s tests -v
) else (
  python -X utf8 -m unittest discover -s tests -v
)
if errorlevel 1 goto failed
if exist "%LOCALAPPDATA%\Author Software\nvm\.shim\node.exe" set "PATH=%LOCALAPPDATA%\Author Software\nvm\.shim;%PATH%"
where node >nul 2>nul
if errorlevel 1 (
  echo Python checks passed. Node helper checks skipped because Node is unavailable.
  pause
  exit /b 0
)
node tests/test_map_tools.js
if errorlevel 1 goto failed
node tests/test_editor_helpers.js
if errorlevel 1 goto failed
echo All checks passed.
pause
exit /b 0
:failed
echo A check failed. See the output above.
pause
exit /b 1

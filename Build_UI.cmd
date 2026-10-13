@echo off
setlocal
cd /d "%~dp0ui"
if exist "%LOCALAPPDATA%\Author Software\nvm\.shim\npm.exe" set "PATH=%LOCALAPPDATA%\Author Software\nvm\.shim;%PATH%"
where npm >nul 2>nul
if errorlevel 1 (
  echo Node and npm are needed to rebuild the interface. Reopen this window after installing Node.
  pause
  exit /b 1
)
if not exist "node_modules\.bin\vite.cmd" (
  call npm ci --no-audit --no-fund
  if errorlevel 1 goto failed
)
call npm run build
if errorlevel 1 goto failed
call npm test
if errorlevel 1 goto failed
echo.
echo Interface built successfully. Refresh the game browser with Ctrl+F5.
pause
exit /b 0
:failed
echo.
echo Build failed. Review the message above.
pause
exit /b 1

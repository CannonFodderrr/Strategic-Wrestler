@echo off
setlocal
title Strategic Wrestler
cd /d "%~dp0"

echo.
echo  Strategic Wrestler
echo  ------------------
echo  Checking for updates from GitHub, then starting...
echo.

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  set PY=py -3
  goto :found
)
where python >nul 2>&1
if %ERRORLEVEL%==0 (
  set PY=python
  goto :found
)
where python3 >nul 2>&1
if %ERRORLEVEL%==0 (
  set PY=python3
  goto :found
)

echo.
echo  ERROR: Python was not found on this computer.
echo.
echo  Install Python 3 from https://www.python.org/downloads/
echo  During setup, check "Add python.exe to PATH".
echo  Then run this Start script again.
echo.
pause
exit /b 1

:found
if not exist "update_and_serve.py" (
  echo  ERROR: update_and_serve.py not found in this folder.
  echo  %cd%
  pause
  exit /b 1
)

%PY% "update_and_serve.py"
echo.
echo  Server stopped.
pause

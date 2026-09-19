@echo off
setlocal EnableExtensions
REM -- ModFlow OrderFlow Analysis Suite - one-command source install (Windows) ------------
REM Creates .venv, installs the app and the dev tooling, and prints how to run it.
REM Safe to re-run: an existing .venv is reused. Nothing needs "activating" - every command
REM below calls the venv's own python.exe by full path, which is the step people get wrong
REM by hand (".venv is not recognized" is that step, done with the wrong shell's syntax).
cd /d "%~dp0"

echo [1/3] Looking for Python 3.11 or newer...
set "PYEXE="
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if not errorlevel 1 set "PYEXE=py -3"
if not defined PYEXE python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if not defined PYEXE if not errorlevel 1 set "PYEXE=python"
if not defined PYEXE goto nopython
echo       using %PYEXE%

echo [2/3] Creating the virtual environment (.venv)...
if exist ".venv\Scripts\python.exe" echo       .venv already exists - reusing it.
if exist ".venv\Scripts\python.exe" goto havevenv
%PYEXE% -m venv .venv
if errorlevel 1 goto venvfail
:havevenv

echo [3/3] Installing the app and dev tooling (this can take a few minutes)...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install -e ".[dev]"
if errorlevel 1 goto pipfail

echo.
echo Done. Start the app with:
echo     run.cmd                          desktop window
echo     run.cmd --headless --port 8099   headless server, UI at http://127.0.0.1:8099/desktop
echo.
pause
exit /b 0

:nopython
echo.
echo    Python 3.11+ was not found on this machine.
echo    Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH",
echo    then run install.cmd again - or use the ready-built installer instead, no Python needed:
echo    https://github.com/ModdySwag/ModFlow-beta-builds/releases
echo.
pause
exit /b 1

:venvfail
echo       Could not create .venv - see the message above.
pause
exit /b 1

:pipfail
echo       Installation failed - see the messages above.
pause
exit /b 1

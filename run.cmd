@echo off
setlocal EnableExtensions
REM -- ModFlow OrderFlow Analysis Suite - run the app from the source checkout -------------
REM Uses the .venv that install.cmd created. Extra arguments pass straight through, e.g.
REM     run.cmd --headless --port 8099
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo No .venv found - run install.cmd first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m orderflow_system.desktop %*
if errorlevel 1 pause

@echo off
REM Double-click to start Praxis for testing. Preflights, launches the app, opens the browser.
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    set "PY=python"
)
echo Starting Praxis...
"%PY%" -m praxis.serve
echo.
echo Praxis stopped. Press any key to close.
pause >nul

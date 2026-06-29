@echo off
REM VHS Web GUI launcher (Windows).
REM First run sets up a local environment and installs dependencies;
REM later runs just start the server. A browser tab opens automatically.
REM Requires Python 3.10+.

setlocal
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

where python >nul 2>nul
if errorlevel 1 (
    echo Error: Python not found. Please install Python 3.10+ from https://python.org
    exit /b 1
)

set "PYBIN=%SCRIPT_DIR%.venv\Scripts\python.exe"
if exist "%PYBIN%" goto run

python -c "import flask" >nul 2>nul
if not errorlevel 1 (
    set "PYBIN=python"
    goto run
)

echo First-time setup: creating a local environment in .venv ...
python -m venv "%SCRIPT_DIR%.venv"
"%SCRIPT_DIR%.venv\Scripts\python.exe" -m pip install --upgrade pip >nul
"%SCRIPT_DIR%.venv\Scripts\python.exe" -m pip install -r "%SCRIPT_DIR%requirements.txt"
echo Setup complete.

:run
echo Starting VHS Web GUI - your browser will open at http://localhost:5001
"%PYBIN%" "%SCRIPT_DIR%assembler\server.py"

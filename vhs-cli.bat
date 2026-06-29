@echo off
REM VHS Assembler CLI launcher (Windows).
REM Uses the project's .venv if present (created by vhs-gui.bat), else system python.

setlocal
set "SCRIPT_DIR=%~dp0"
set "PYBIN=python"
if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" set "PYBIN=%SCRIPT_DIR%.venv\Scripts\python.exe"
"%PYBIN%" "%SCRIPT_DIR%assembler\assembler.py" %*

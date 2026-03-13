@echo off
REM VHS CLI Start Script for Windows
REM This script runs the VHS assembler CLI from the root directory.

SET SCRIPT_DIR=%~dp0
python "%SCRIPT_DIR%assembler\assembler.py" %*

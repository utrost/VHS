@echo off
REM VHS GUI Start Script for Windows
REM This script starts the VHS Web GUI server from the root directory.

SET SCRIPT_DIR=%~dp0

echo Starting VHS Web GUI...
echo Open your browser at: http://localhost:5001
echo.

python "%SCRIPT_DIR%assembler\server.py"

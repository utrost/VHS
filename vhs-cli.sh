#!/bin/bash

# VHS CLI Start Script for macOS/Linux
# This script runs the VHS assembler CLI from the root directory.

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Run the assembler
python3 "$SCRIPT_DIR/assembler/assembler.py" "$@"

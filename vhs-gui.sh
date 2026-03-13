#!/bin/bash

# VHS GUI Start Script for macOS/Linux
# This script starts the VHS Web GUI server from the root directory.

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Starting VHS Web GUI..."
echo "Open your browser at: http://localhost:5001"
echo ""

# Run the server
python3 "$SCRIPT_DIR/assembler/server.py"

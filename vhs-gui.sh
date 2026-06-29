#!/bin/bash
#
# VHS Web GUI launcher (macOS / Linux).
#
# First run sets up a local Python environment and installs dependencies;
# subsequent runs just start the server. A browser tab opens automatically.
# Requires Python 3.10+.

set -e
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

PY="${PYTHON:-python3}"
VENV="$SCRIPT_DIR/.venv"

if ! command -v "$PY" >/dev/null 2>&1; then
    echo "Error: '$PY' not found. Please install Python 3.10+ (https://python.org)." >&2
    exit 1
fi

if [ -x "$VENV/bin/python" ]; then
    # Use the project's local environment if it exists.
    PYBIN="$VENV/bin/python"
elif "$PY" -c "import flask" >/dev/null 2>&1; then
    # Dependencies already available system-wide — no venv needed.
    PYBIN="$PY"
else
    echo "First-time setup: creating a local environment in .venv …"
    "$PY" -m venv "$VENV"
    "$VENV/bin/python" -m pip install --upgrade pip >/dev/null
    "$VENV/bin/python" -m pip install -r "$SCRIPT_DIR/requirements.txt"
    PYBIN="$VENV/bin/python"
    echo "Setup complete."
fi

echo "Starting VHS Web GUI — your browser will open at http://localhost:5001"
exec "$PYBIN" "$SCRIPT_DIR/assembler/server.py"

#!/bin/bash
#
# VHS Assembler CLI launcher (macOS / Linux).
# Uses the project's .venv if present (created by vhs-gui.sh), else the
# system python. The CLI core needs no third-party packages; only --format
# png/pdf and YAML presets require the optional deps in requirements.txt.

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYBIN="$SCRIPT_DIR/.venv/bin/python"
else
    PYBIN="${PYTHON:-python3}"
fi

exec "$PYBIN" "$SCRIPT_DIR/assembler/assembler.py" "$@"

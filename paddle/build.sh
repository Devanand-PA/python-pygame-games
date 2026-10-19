#!/bin/sh
# Build a fully self-contained Paddle executable (see build.py).
#
# Works from any directory and uses the project's local .venv when present.
# Installs PyInstaller into that interpreter automatically if it is missing.
set -eu

cd "$(dirname "$0")"

if [ -x .venv/bin/python ]; then
    PY=.venv/bin/python
elif command -v python3 >/dev/null 2>&1; then
    PY=python3
else
    PY=python
fi

if ! "$PY" -c "import PyInstaller" >/dev/null 2>&1; then
    echo "PyInstaller not found for $PY; installing it..."
    if command -v uv >/dev/null 2>&1; then
        uv pip install --python "$PY" pyinstaller
    else
        "$PY" -m pip install pyinstaller
    fi
fi

exec "$PY" build.py "$@"
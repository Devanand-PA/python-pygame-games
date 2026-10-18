"""Standalone level designer.

A self-contained pygame application for authoring the game's ``content/``:

    .venv/bin/python designer.py

Edit terrain, units, races and levels (with a paint-your-own map grid and a wave
builder), then save straight back to JSON.  See ``level_designer/`` for the
implementation.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from level_designer.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())

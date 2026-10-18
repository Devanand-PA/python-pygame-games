#!/usr/bin/env python3
"""Standalone level designer for Big Tower.

Usage:
    python designer.py

Opens a pygame window with Terrain / Units / Races / Levels / Help tabs and
saves edits back to the ``content/`` JSON the game reads.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from level_designer.app import main  # noqa: E402


if __name__ == "__main__":
    main()

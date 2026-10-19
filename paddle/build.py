#!/usr/bin/env python3
"""Build a fully self-contained Paddle executable.

Mirrors ``bigtower/build.py`` so both games are frozen the same way: a single
self-contained ``--onefile`` executable plus a zip archive for distribution.

Every scene and object module is listed in ``HIDDEN_IMPORTS`` because the game
reaches them lazily -- ``main.py`` resolves saved scenes through
``importlib.import_module`` and the scene classes import ``objects.*`` inside
methods.  PyInstaller's static analysis cannot see those, so listing them here
is what keeps a frozen build from crashing the first time a player opens the
settings menu or loads a save.

Prerequisite: PyInstaller must be importable by the interpreter running this
script (see ``build.sh`` for a convenience wrapper that installs it).

Usage:
    python build.py

Output:
    dist/paddle[.exe]                   the runnable game (self-contained)
    dist/paddle-<os>-<arch>.zip        distributable archive (exe + README)
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
WORK = ROOT / "build"
NAME = "paddle"

# Reached only through deferred imports (importlib / function-local imports), so
# PyInstaller's static analysis misses them.  Listing them explicitly guarantees
# a complete frozen build.
HIDDEN_IMPORTS = [
    "gui_utils.gui_elements",
    "gui_utils.insults",
    "objects.ball",
    "objects.breakable_blocks",
    "objects.buffs",
    "objects.paddle",
    "scenes.difficulty_chooser",
    "scenes.options_screen",
    "scenes.scene_1",
    "scenes.settings_menu",
    "scenes.welcome_screen",
]


def _platform_tag() -> str:
    system = platform.system().lower()
    system = {"windows": "windows", "darwin": "macos"}.get(system, system)
    machine = platform.machine().lower()
    machine = {
        "amd64": "x86_64",
        "x86_64": "x86_64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }.get(machine, machine)
    return "{}-{}".format(system, machine)


def _require_pyinstaller() -> bool:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        sys.stderr.write(
            "PyInstaller is required but not installed for this interpreter.\n"
            "Install it with one of:\n"
            "    uv pip install pyinstaller\n"
            "    {python} -m pip install pyinstaller\n".format(
                python=sys.executable)
        )
        return False
    return True


def main() -> int:
    if not _require_pyinstaller():
        return 1

    entry = ROOT / "main.py"
    if not entry.is_file():
        sys.stderr.write(
            "Expected main.py next to build.py; run the build from the paddle "
            "directory.\n")
        return 1

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile",
        "--name", NAME,
        "--distpath", str(DIST),
        "--workpath", str(WORK),
        "--specpath", str(WORK),
        "--paths", str(ROOT),
    ]
    for module in HIDDEN_IMPORTS:
        cmd += ["--hidden-import", module]
    # Hide the console window on Windows release builds; keep it elsewhere so
    # crashes remain visible during development.
    if platform.system() == "Windows":
        cmd.append("--windowed")
    cmd.append(str(entry))

    print("+ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=str(ROOT), check=True)

    exe = DIST / (NAME + (".exe" if platform.system() == "Windows" else ""))
    if not exe.is_file():
        sys.stderr.write("Build finished but {} was not produced.\n".format(exe))
        return 1

    # Stage the executable (plus the README) and zip it for distribution.
    tag = _platform_tag()
    stage = DIST / "{}-{}".format(NAME, tag)
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    shutil.copy2(str(exe), str(stage / exe.name))
    readme = ROOT / "README.md"
    if readme.is_file():
        shutil.copy2(str(readme), str(stage / readme.name))

    # The game writes its save file to a "saves" directory relative to the
    # working directory, so ship an empty one to give players a known-good
    # location instead of failing on first run.
    (stage / "saves").mkdir(exist_ok=True)

    archive = shutil.make_archive(
        str(DIST / "{}-{}".format(NAME, tag)), "zip", root_dir=str(stage))
    shutil.rmtree(stage)

    print("\nExecutable: {}".format(exe))
    print("Distribution archive: {}".format(archive))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
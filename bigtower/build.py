#!/usr/bin/env python3
"""Build a fully self-contained Big Tower executable.

Everything the game needs at runtime -- the Python code, every file under
``assets/`` and all of ``maps/`` -- is embedded *inside* the PyInstaller
``--onefile`` executable.  The game therefore runs from anywhere, with no
loose asset folder required.

Prerequisite: PyInstaller must be importable by the interpreter running this
script (see ``build.sh`` for a convenience wrapper that installs it).

Usage:
    python build.py

Output:
    dist/bigtower[.exe]              the runnable game (self-contained)
    dist/bigtower-<os>-<arch>.zip    distributable archive (exe + README)
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
NAME = "bigtower"

# Imported dynamically at runtime (importlib) or only from inside methods, so
# PyInstaller's static analysis can occasionally miss them.  Listing them
# explicitly guarantees a complete frozen build.
HIDDEN_IMPORTS = [
    "core.content",
    "core.game",
    "core.paths",
    "core.savestate",
    "core.scene",
    "core.settings",
    "engine.art",
    "engine.camera",
    "engine.game_scene",
    "engine.level",
    "engine.projectiles",
    "engine.stats_panel",
    "engine.units",
    "gui.widgets",
    "menus.campaign_select",
    "menus.career_menu",
    "menus.common",
    "menus.level_select",
    "menus.pause_overlay",
    "menus.settings_overlay",
    "menus.user_selection",
    "menus.welcome_screen",
    "utils.gui_elements",
    "utils.savestate",
]


def _data_arg(src: Path) -> str:
    """PyInstaller --add-data value, using the correct path separator per OS."""
    return "{}{}{}".format(src, os.pathsep, src.name)


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

    assets = ROOT / "assets"
    maps = ROOT / "maps"
    content = ROOT / "content"
    missing = [p.name for p in (assets, maps, content) if not p.is_dir()]
    if missing:
        sys.stderr.write(
            "Expected {} next to build.py; run the build from the bigtower "
            "directory.\n".format(", ".join(missing)))
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
        "--add-data", _data_arg(assets),
        "--add-data", _data_arg(maps),
        "--add-data", _data_arg(content),
    ]
    for module in HIDDEN_IMPORTS:
        cmd += ["--hidden-import", module]
    # Hide the console window on Windows release builds; keep it elsewhere so
    # crashes remain visible during development.
    if platform.system() == "Windows":
        cmd.append("--windowed")
    cmd.append(str(ROOT / "main.py"))

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

    archive = shutil.make_archive(
        str(DIST / "{}-{}".format(NAME, tag)), "zip", root_dir=str(stage))
    shutil.rmtree(stage)

    print("\nExecutable: {}".format(exe))
    print("Distribution archive: {}".format(archive))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

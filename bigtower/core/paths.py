"""Path resolution helpers.

All asset access goes through asset(); all save data through the saves-root
system.  The old game assumed $HOME/Documents/Saves/bigtower always exists and
is writable -- on systems where Documents is read-only (mounts, flatpak sandbox,
perms) the game crashed.  Saves now resolve to the first *writable* candidate
and old read-only save locations are still read for backwards compatibility.
"""
import os
import pathlib

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
MAPS_DIR = BASE_DIR / "maps"
PACK_DIR = ASSETS_DIR / "packs" / "kenney_tower-defense-top-down" / "PNG" / "Default size"


def asset(*parts) -> pathlib.Path:
    """Absolute path to a file under assets/."""
    return ASSETS_DIR.joinpath(*parts)


def map_file(name: str) -> pathlib.Path:
    return MAPS_DIR / name


# --------------------------------------------------------------------------
# Save data locations
# --------------------------------------------------------------------------
def _is_dir_writable(path: pathlib.Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_probe"
        with open(probe, "w") as fh:
            fh.write("ok")
        probe.unlink()
        return True
    except OSError:
        return False


def _candidate_roots():
    roots = []
    env = os.environ.get("BIGTOWER_SAVE_DIR")
    if env:
        roots.append(pathlib.Path(env).expanduser())
    roots.append(pathlib.Path.home() / "Documents" / "Saves" / "bigtower")
    xdg = os.environ.get("XDG_DATA_HOME")
    xdg_dir = pathlib.Path(xdg).expanduser() if xdg else pathlib.Path.home() / ".local" / "share"
    roots.append(xdg_dir / "bigtower")
    roots.append(BASE_DIR / "saves")
    return roots


_SAVES_ROOT = None


def saves_root() -> pathlib.Path:
    """First writable save root (cached)."""
    global _SAVES_ROOT
    if _SAVES_ROOT is None:
        for cand in _candidate_roots():
            if _is_dir_writable(cand):
                _SAVES_ROOT = cand
                break
        else:  # pragma: no cover - last resort
            _SAVES_ROOT = BASE_DIR / "saves"
    return _SAVES_ROOT


def all_known_roots():
    """Every save root that exists on disk (writable or not)."""
    seen = []
    for cand in _candidate_roots():
        if cand.exists() and cand not in seen:
            seen.append(cand)
    return seen


def user_dir(user: str):
    """Writable directory for a user's data (created on demand)."""
    d = saves_root() / user
    d.mkdir(parents=True, exist_ok=True)
    return d


def find_existing_user_dir(user: str):
    """Existing directory holding a user's data, even if read-only."""
    for root in all_known_roots():
        d = root / user
        if d.is_dir():
            return d
    return None


def config_file() -> pathlib.Path:
    return user_dir("_config") / "config.json"

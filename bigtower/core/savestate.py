"""User profiles and persistent stats.

Layout on disk (per user):
    <saves_root>/<user>/user_stats.json

The old implementation crashed with AttributeError (savedir.isdir), wrote
files into directories that did not exist, and had no fallback when
~/Documents is read-only.  All of that is handled here.
"""
import json
import pathlib
import shutil

from core import paths

DEFAULT_STATS = {
    "Campaigns Cleared": 0,
    "Kills": 0,
    "Levels Completed": [],
}

STATS_FILE = "user_stats.json"


def _load_json(path: pathlib.Path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def list_users():
    """All known users across every save root, sorted, deduplicated."""
    users = set()
    for root in paths.all_known_roots():
        try:
            for child in root.iterdir():
                if child.is_dir() and not child.name.startswith("_"):
                    users.add(child.name)
        except OSError:
            continue
    return sorted(users)


def _validate_user_name(user: str) -> str:
    """Normalise and sanity-check a profile name.

    Rejects empty names, anything containing a path separator, ``.``/``..``
    (which would escape the save root) and the leading-underscore names that
    the game reserves for its own bookkeeping (``_config``).
    """
    name = (user or "").strip()
    if not name:
        raise ValueError("empty user name")
    if any(ch in name for ch in "/\\") or name in {".", ".."}:
        raise ValueError("invalid user name")
    if name.startswith("_"):
        raise ValueError("invalid user name")
    return name


def create_user(user: str):
    return paths.user_dir(_validate_user_name(user))


def delete_user(user: str):
    """Erase a user's saved data from every save root that holds it.

    A profile can exist in more than one root (the writable one plus any
    legacy read-only location still on disk), so all of them are removed.
    Returns ``(deleted, errors)``: the number of directories removed and a
    list of human-readable failures, e.g. a read-only save root.
    """
    name = _validate_user_name(user)
    deleted, errors = 0, []
    for root in paths.all_known_roots():
        directory = root / name
        if not directory.is_dir():
            continue
        try:
            shutil.rmtree(directory)
            deleted += 1
        except OSError as exc:
            errors.append("{} ({})".format(
                directory.parent, exc.strerror or exc))
    return deleted, errors


def user_exists(user: str) -> bool:
    return paths.find_existing_user_dir(user) is not None


def load_stats(user: str):
    """Read a user's stats, merged over defaults. Old read-only dirs count."""
    stats = dict(DEFAULT_STATS)
    stats["Levels Completed"] = []
    data = None
    d = paths.find_existing_user_dir(user)
    if d is not None:
        data = _load_json(d / STATS_FILE)
    if isinstance(data, dict):
        for key, value in data.items():
            stats[key] = value
    if not isinstance(stats.get("Levels Completed"), list):
        stats["Levels Completed"] = []
    return stats


def save_stats(user: str, stats: dict) -> bool:
    """Write stats. Returns True on success, False if storage is broken."""
    try:
        d = paths.user_dir(user)
        tmp = d / (STATS_FILE + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(stats, fh, indent=2)
        tmp.replace(d / STATS_FILE)
        return True
    except OSError:
        return False


def update_stats(user: str, **deltas) -> dict:
    """Apply additive updates (e.g. Kills=12) or set list fields directly."""
    stats = load_stats(user)
    for key, value in deltas.items():
        if isinstance(value, (int, float)) and isinstance(stats.get(key), (int, float)):
            stats[key] = stats[key] + value
        else:
            stats[key] = value
    save_stats(user, stats)
    return stats


def record_level_completed(user: str, level_id, kills: int, race_level_ids=None):
    """Persist a victory on ``level_id``; returns the updated stats dict.

    ``race_level_ids`` is the full ordered list of a race's level ids: when the
    player has cleared all of them, the campaign counter ticks up.
    """
    stats = load_stats(user)
    done = set(stats.get("Levels Completed") or [])
    done.add(level_id)
    stats["Levels Completed"] = sorted(done, key=lambda v: str(v))
    stats["Kills"] = stats.get("Kills", 0) + kills
    if race_level_ids:
        race_ids = set(race_level_ids)
        if race_ids and race_ids.issubset(done):
            stats["Campaigns Cleared"] = stats.get("Campaigns Cleared", 0) + 1
    save_stats(user, stats)
    return stats


def levels_completed(user: str):
    """The set of cleared level ids for a user."""
    return set(load_stats(user).get("Levels Completed") or [])

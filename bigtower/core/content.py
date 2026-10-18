"""Data-driven game content: terrain, units, races (campaigns) and levels.

Everything the game plays with lives as editable JSON under ``content/`` (see
``core.paths.content_dir``) so it can be authored without touching Python:

    content/
        terrain.json            the terrain palette (grid char -> tiles + flags)
        units/<unit_id>.json    every unit, defender *and* attacker
        races/<race_id>.json    a campaign: defender roster, enemy roster, levels
        levels/<level_id>.json  grid, economy, shop, enemy pool, waves

``ContentDB`` loads that tree into light wrapper objects (:class:`TerrainType`,
:class:`UnitType`) and race/level dicts, and can write it back (the level
designer uses the same class).  The rest of the engine only ever talks to:

    content.terrain(char)          -> TerrainType | None
    content.unit(unit_id)          -> UnitType | None
    content.race(race_id)          -> dict | None
    content.level(level_id)        -> dict | None
    content.race_levels(race)      -> [level dict, ...]
    content.level_defenders(level) -> [UnitType, ...]
    content.sorted_races()         -> [race dict, ...]

Sprite specs are normalised once by :func:`normalise_sprite`; see ``engine.art``
for how they are turned into surfaces.
"""
import copy
import json
import pathlib

from core import paths

TERRAIN_FILE = "terrain.json"
UNITS_DIR = "units"
RACES_DIR = "races"
LEVELS_DIR = "levels"

DEFAULT_TILE = 226


# ---------------------------------------------------------------------------
# Sprite specs
# ---------------------------------------------------------------------------
def _fallback_sprite():
    return {"kind": "pack", "tile": DEFAULT_TILE}


def normalise_sprite(spec):
    """Return a canonical, JSON-safe sprite spec.

    Accepts any of the documented forms (``pack`` / ``image`` / ``shape`` /
    ``sheet`` / ``anim`` / ``sprites``), an int tile number, a bare sheet dict,
    or ``None`` (an all-purpose placeholder), and fills in the ``kind`` so the
    renderer never has to guess.
    """
    if spec is None:
        return _fallback_sprite()
    if isinstance(spec, int):
        return {"kind": "pack", "tile": int(spec)}
    if not isinstance(spec, dict):
        return _fallback_sprite()

    kind = spec.get("kind")

    if kind == "sprites":
        anims_in = spec.get("animations") or {}
        animations = {}
        for name, sub in anims_in.items():
            animations[str(name)] = _normalise_sheet(sub)
        image = spec.get("image")
        return {
            "kind": "sprites",
            "image": normalise_sprite(image) if image else None,
            "animations": animations,
        }

    if kind == "anim":
        return {
            "kind": "anim",
            "fps": _number(spec.get("fps"), 8),
            "loop": bool(spec.get("loop", True)),
            "frames": [normalise_sprite(f) for f in (spec.get("frames") or [])],
        }

    if kind == "sheet" or (kind is None and "path" in spec and "frames" in spec):
        return _normalise_sheet(spec)

    if kind == "image":
        return {"kind": "image", "path": str(spec.get("path", ""))}

    if kind == "shape":
        color = spec.get("color") or [200, 200, 200]
        return {
            "kind": "shape",
            "shape": str(spec.get("shape", "circle")),
            "color": [int(c) for c in list(color)[:3]],
        }

    if kind == "pack":
        return {"kind": "pack", "tile": int(spec.get("tile", DEFAULT_TILE))}

    # A kind-less spec with a tile behaves like a pack spec.
    if "tile" in spec:
        return {"kind": "pack", "tile": int(spec.get("tile", DEFAULT_TILE))}

    return _fallback_sprite()


def _normalise_sheet(spec):
    """A ``sheet`` spec: keep the frame selection (int or explicit list)."""
    spec = spec if isinstance(spec, dict) else {}
    raw = spec.get("frames", 1)
    if isinstance(raw, (list, tuple)):
        frames = [int(i) for i in raw]
    else:
        frames = max(1, int(raw))
    out = {
        "kind": "sheet",
        "path": str(spec.get("path", "")),
        "frame_w": max(1, int(spec.get("frame_w", 32))),
        "frame_h": max(1, int(spec.get("frame_h", 32))),
        "frames": frames,
        "fps": _number(spec.get("fps"), 8),
        "loop": bool(spec.get("loop", True)),
    }
    for key in ("cols", "rows", "margin", "spacing"):
        if spec.get(key) is not None:
            out[key] = max(0, int(spec.get(key)))
    return out


def _number(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


# ---------------------------------------------------------------------------
# Content objects
# ---------------------------------------------------------------------------
class TerrainType:
    """One entry of the terrain palette (a grid character)."""

    def __init__(self, data):
        self.data = dict(data or {})
        self.char = str(self.data.get("char", "?"))
        self.id = self.data.get("id") or self.char
        self.name = self.data.get("name", self.id)
        self.buildable = bool(self.data.get("buildable", False))
        self.walkable = bool(self.data.get("walkable", False))
        tint = self.data.get("tint")
        self.tint = tuple(int(c) for c in list(tint)[:3]) if tint else None

        sprite = self.data.get("sprite")
        if sprite:
            self.base_spec = normalise_sprite(sprite)
        else:
            self.base_spec = {"kind": "pack",
                              "tile": int(self.data.get("base", 157))}

        overlay = self.data.get("overlay_sprite")
        self.overlay_spec = normalise_sprite(overlay) if overlay else None

    def to_dict(self):
        return copy.deepcopy(self.data)


class UnitType:
    """A unit definition shared by defenders (towers) and attackers (mobs)."""

    def __init__(self, data):
        self.data = dict(data or {})
        self.id = self.data.get("id")
        self.name = self.data.get("name", self.id)
        self.side = self.data.get("side", "defender")
        default_move = "route" if self.side == "attacker" else "static"
        self.movement = self.data.get("movement", default_move)
        self.attack = self.data.get("attack", "none")

        self.speed = _number(self.data.get("speed"), 0.0)
        self.hp = _number(self.data.get("hp"), 100.0)
        self.cost = int(self.data.get("cost", 50))
        self.has_attack = self.attack not in (None, "", "none")
        self.range = _number(
            self.data.get("range"), 140.0 if self.has_attack else 0.0)
        self.damage = _number(
            self.data.get("damage"), 10.0 if self.has_attack else 0.0)
        self.cooldown = max(0.05, _number(self.data.get("cooldown"), 1.0))
        self.bounty = int(self.data.get("bounty", 10))
        self.damage_to_base = int(self.data.get("damage_to_base", 1))
        self.targets = self.data.get("targets", "ground")
        self.projectile = self.data.get("projectile", "bullet")
        self.splash = _number(self.data.get("splash"), 0.0)
        self.sprite_scale = max(0.2, _number(self.data.get("sprite_scale"), 0.9))

        tint = self.data.get("tint")
        self.tint = tuple(int(c) for c in list(tint)[:3]) if tint else None

        if self.data.get("sound"):
            self.sound = self.data["sound"]
        else:
            self.sound = "gun" if self.attack == "projectile" else "sting"

        self.sprite = normalise_sprite(self.data.get("sprite"))
        pspec = self.data.get("projectile_sprite")
        self.projectile_sprite = normalise_sprite(pspec) if pspec else None

    def to_dict(self):
        return copy.deepcopy(self.data)

    def __repr__(self):
        return "<UnitType {} ({})>".format(self.id, self.side)


# ---------------------------------------------------------------------------
# The database
# ---------------------------------------------------------------------------
class ContentDB:
    """Loads (and can save) the whole ``content/`` tree."""

    def __init__(self, root=None):
        self.root = pathlib.Path(root) if root is not None else paths.content_dir()
        self.terrains = {}            # id -> TerrainType
        self.terrain_by_char = {}     # char -> TerrainType
        self.units = {}               # id -> UnitType
        self.races = {}               # id -> dict
        self.levels = {}              # id -> dict
        self.load()

    # -------------------------------------------------------------- loading
    def load(self):
        self.terrains = {}
        self.terrain_by_char = {}
        self.units = {}
        self.races = {}
        self.levels = {}
        self._load_terrain()
        self._load_units()
        self._load_races()
        self._load_levels()

    def _read_json(self, path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return None

    def _load_terrain(self):
        data = self._read_json(self.root / TERRAIN_FILE)
        if isinstance(data, dict):
            data = list(data.values())
        for entry in data or []:
            if not isinstance(entry, dict):
                continue
            terr = TerrainType(entry)
            self.terrains[terr.id] = terr
            self.terrain_by_char[terr.char] = terr

    def _load_units(self):
        for path in sorted((self.root / UNITS_DIR).glob("*.json")):
            data = self._read_json(path)
            if not isinstance(data, dict):
                continue
            data.setdefault("id", path.stem)
            utype = UnitType(data)
            self.units[utype.id] = utype

    def _load_races(self):
        for path in sorted((self.root / RACES_DIR).glob("*.json")):
            data = self._read_json(path)
            if not isinstance(data, dict):
                continue
            data.setdefault("id", path.stem)
            self.races[data["id"]] = data

    def _load_levels(self):
        for path in sorted((self.root / LEVELS_DIR).glob("*.json")):
            data = self._read_json(path)
            if not isinstance(data, dict):
                continue
            data.setdefault("id", path.stem)
            self.levels[data["id"]] = data

    # -------------------------------------------------------------- queries
    def terrain(self, key):
        """Terrain by grid character (or by id as a fallback)."""
        if key is None:
            return None
        return self.terrain_by_char.get(key) or self.terrains.get(key)

    def unit(self, unit_id):
        return self.units.get(unit_id)

    def race(self, race_id):
        return self.races.get(race_id)

    def level(self, level_id):
        return self.levels.get(level_id)

    def race_levels(self, race):
        """The ordered list of level dicts a race owns."""
        if not race:
            return []
        out = []
        for item in race.get("levels") or []:
            level_id = item.get("id") if isinstance(item, dict) else item
            level = self.level(level_id)
            if level is not None:
                out.append(level)
        return out

    def level_defenders(self, level_def):
        """The UnitTypes a level offers in its shop."""
        ids = (level_def or {}).get("available_units")
        if not ids:
            race = self.race((level_def or {}).get("race")) or {}
            ids = race.get("units") or []
        return [u for u in (self.unit(i) for i in ids) if u is not None]

    def level_attackers(self, level_def):
        """The UnitTypes a level can spawn (its enemy pool)."""
        ids = (level_def or {}).get("enemy_pool")
        if not ids:
            race = self.race((level_def or {}).get("race")) or {}
            ids = race.get("enemies") or []
        return [u for u in (self.unit(i) for i in ids) if u is not None]

    def sorted_races(self):
        return sorted(
            self.races.values(),
            key=lambda r: (r.get("order", 0),
                           str(r.get("name", r.get("id", "")))))

    # -------------------------------------------------------------- saving
    def _write_json(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
        tmp.replace(path)

    def save_unit(self, utype):
        if isinstance(utype, UnitType):
            utype = utype.to_dict()
        unit_id = utype.get("id")
        if not unit_id:
            raise ValueError("unit needs an id")
        self._write_json(self.root / UNITS_DIR / f"{unit_id}.json", utype)
        data = dict(utype)
        data.setdefault("id", unit_id)
        self.units[unit_id] = UnitType(data)
        return self.units[unit_id]

    def delete_unit(self, unit_id):
        path = self.root / UNITS_DIR / f"{unit_id}.json"
        try:
            path.unlink()
        except OSError:
            pass
        self.units.pop(unit_id, None)

    def save_race(self, race):
        race = dict(race)
        race_id = race.get("id")
        if not race_id:
            raise ValueError("race needs an id")
        self._write_json(self.root / RACES_DIR / f"{race_id}.json", race)
        self.races[race_id] = race
        return race

    def delete_race(self, race_id):
        try:
            (self.root / RACES_DIR / f"{race_id}.json").unlink()
        except OSError:
            pass
        self.races.pop(race_id, None)

    def save_terrain(self, entries):
        """Write the whole terrain palette (a list of dicts)."""
        entries = list(entries)
        self._write_json(self.root / TERRAIN_FILE, entries)
        self.terrains = {}
        self.terrain_by_char = {}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            terr = TerrainType(entry)
            self.terrains[terr.id] = terr
            self.terrain_by_char[terr.char] = terr
        return entries

    def save_level(self, level):
        level = dict(level)
        level_id = level.get("id")
        if not level_id:
            raise ValueError("level needs an id")
        self._write_json(self.root / LEVELS_DIR / f"{level_id}.json", level)
        self.levels[level_id] = level
        return level

    def delete_level(self, level_id):
        try:
            (self.root / LEVELS_DIR / f"{level_id}.json").unlink()
        except OSError:
            pass
        self.levels.pop(level_id, None)


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------
_content = None


def get_content():
    """The shared ContentDB (built once from the default content directory)."""
    global _content
    if _content is None:
        _content = ContentDB()
    return _content


def reset_content():
    """Forget the cached database (used by tests / the designer)."""
    global _content
    _content = None
    return get_content()

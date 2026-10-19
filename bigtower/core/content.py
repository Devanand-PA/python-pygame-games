"""Data-driven game content: terrain, units, races and levels.

Everything that used to be hardcoded (``engine/levels.py``, ``engine/towers.py``,
``engine/enemies.py``) now lives in JSON under ``content/`` so it can be authored
without touching Python -- in particular by the standalone level designer
(``designer.py``).

Layout::

    content/
        terrain.json          the terrain palette (grid characters -> tiles)
        units/<unit_id>.json  every unit, player *and* enemy, one schema
        races/<race_id>.json  a campaign: unit roster + ordered level ids
        levels/<level_id>.json  one level: grid, economy, available units, waves

The game reads this through :func:`get_content` (a cached :class:`ContentDB`);
the designer edits it through the ``save_*`` methods.  A unit is *either* a
defender (placed by the player, a "tower") or an attacker (spawned by waves);
the engine treats both with the same :class:`UnitType`.
"""
from __future__ import annotations

import json
import pathlib

from core import paths


class ContentError(ValueError):
    """Raised when a content file is malformed."""


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _color(value):
    """Normalise ``[r, g, b]`` / ``[r, g, b, a]`` / ``null`` into a list."""
    if value is None:
        return None
    if isinstance(value, str):
        value = value.lstrip("#")
        if len(value) == 6:
            value = [int(value[i:i + 2], 16) for i in (0, 2, 4)]
    try:
        parts = [max(0, min(255, int(c))) for c in value]
    except (TypeError, ValueError):
        return None
    if len(parts) not in (3, 4):
        return None
    return parts


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


# ---------------------------------------------------------------------------
# terrain
# ---------------------------------------------------------------------------
DEFAULT_TERRAIN = {
    "id": "grass",
    "name": "Grass",
    "char": "g",
    "base": 157,
    "overlay": None,
    "sprite": None,          # custom base sprite spec (overrides `base`)
    "overlay_sprite": None,  # custom overlay sprite spec (overrides `overlay`)
    "buildable": True,
    "walkable": True,
    "tint": None,
    "cost": 0,          # reserved for future build-over-terrain rules
    "description": "",
}


class TerrainType:
    """One paintable terrain cell type.

    ``base`` is the Kenney tile number drawn as the ground; ``overlay`` is an
    optional tile drawn on top (rocks, bushes...).  For custom art, ``sprite``
    and ``overlay_sprite`` hold full sprite specs (an image, a spritesheet
    animation, ...) that override the tile numbers.  ``buildable`` controls
    whether players may place defenders there, ``walkable`` whether enemy
    ground units may path through it.
    """

    def __init__(self, data):
        data = dict(data or {})
        self.id = str(data.get("id") or "terrain")
        self.name = str(data.get("name") or self.id)
        self.char = str(data.get("char") or "?")[:1]
        self.base = _int(data.get("base"), 157)
        self.overlay = (None if data.get("overlay") in (None, "", -1, "none")
                        else _int(data.get("overlay")))
        self.sprite = (normalise_sprite(data.get("sprite"), self.base)
                       if data.get("sprite") is not None else None)
        self.overlay_sprite = (normalise_sprite(data.get("overlay_sprite"))
                               if data.get("overlay_sprite") is not None else None)
        self.buildable = bool(data.get("buildable", False))
        self.walkable = bool(data.get("walkable", True))
        self.tint = _color(data.get("tint"))
        self.description = str(data.get("description") or "")
        known = set(DEFAULT_TERRAIN)
        self.extra = {k: v for k, v in data.items() if k not in known}

    @property
    def base_spec(self):
        """The sprite spec actually drawn for the ground."""
        return self.sprite or {"kind": "pack", "tile": self.base}

    @property
    def overlay_spec(self):
        """The sprite spec drawn on top, or None."""
        if self.overlay_sprite is not None:
            return self.overlay_sprite
        if self.overlay is None:
            return None
        return {"kind": "pack", "tile": self.overlay}

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "char": self.char,
            "base": self.base,
            "overlay": self.overlay,
            "sprite": self.sprite,
            "overlay_sprite": self.overlay_sprite,
            "buildable": self.buildable,
            "walkable": self.walkable,
            "tint": self.tint,
            "description": self.description,
            **self.extra,
        }


# ---------------------------------------------------------------------------
# units
# ---------------------------------------------------------------------------
DEFAULT_UNIT = {
    "id": "unit",
    "name": "Unit",
    "side": "defender",          # defender | attacker
    "role": "",                  # free-form label ("melee", "sniper", ...)
    "sprite": {"kind": "pack", "tile": 226},
    "projectile_sprite": None,
    "sprite_scale": 1.0,
    "tint": None,                # overrides the race tint when set
    "hp": 100,
    "cost": 50,                  # defenders: build cost
    "bounty": 0,                 # attackers: gold granted when killed
    "speed": 0.0,                # 0 == immobile
    "movement": "static",        # static | chase | route | direct | hunt
    "attack": "none",            # none | melee | projectile
    "range": 120.0,
    "damage": 5.0,
    "cooldown": 0.5,
    "projectiles": 1,            # shots fired per attack
    "projectile": "dot",         # dot | rocket
    "splash": 0.0,
    "sound": "gun",
    "targets": "both",           # ground | air | both  (what it can hit)
    "targeting": "",             # "", nearest, first, strongest, weakest
    "is_flying": False,
    "damage_to_base": 1,         # attackers: lives lost if it reaches the base
    "stop_to_attack": True,      # attackers: halt while attacking a defender
    "aggro": 160.0,              # chase / hunt detection radius
    "radius": 16.0,
    "can_be_attacked": True,
    "description": "",
    "upgrade_paths": None,       # None -> DEFAULT_UPGRADE_PATHS
}

UNIT_MOVEMENTS = ("static", "chase", "route", "direct", "hunt")
UNIT_ATTACKS = ("none", "melee", "projectile")
UNIT_TARGETS = ("ground", "air", "both")
UNIT_TARGETING = ("", "nearest", "first", "strongest", "weakest")
UNIT_SIDES = ("defender", "attacker")

# Branches a defender can take instead of one linear ladder.  ``gains`` keys:
# damage / range / rate / hp are multipliers, ``projectiles`` is additive.
DEFAULT_UPGRADE_PATHS = [
    {"id": "damage", "name": "Damage", "gains": {"damage": 1.6}},
    {"id": "range", "name": "Range", "gains": {"range": 1.12}},
    {"id": "rapid", "name": "Rapid Fire", "gains": {"rate": 0.82}},
    {"id": "multi", "name": "Multi Shot",
     "gains": {"projectiles": 1, "damage": 0.92}},
    {"id": "vitality", "name": "Vitality", "gains": {"hp": 1.25}},
]
UPGRADE_GAIN_KEYS = ("damage", "range", "rate", "hp")

# The named states a unit can animate.  The engine plays a matching animation
# automatically: idle when still, walk when moving, attack when firing, death
# when killed.  A missing state falls back to the static image / idle / first
# animation (see :func:`engine.art.sprite_frames`).
ANIMATION_STATES = ("idle", "walk", "attack", "death")

# Sprite specs are shared by units and terrain.  A spec is one of::
#
#     {"kind": "pack",  "tile": 226}
#     {"kind": "image", "path": "units/foo/bar.png"}
#     {"kind": "shape", "shape": "circle", "color": [200, 120, 120]}
#     {"kind": "sheet", "path": "units/foo.png", "frame_w": 32, "frame_h": 32,
#      "frames": 6, "fps": 8, "loop": true, "margin": 0, "spacing": 0}
#     {"kind": "anim",  "fps": 8, "loop": true, "frames": [<spec>, <spec>, ...]}
#     {"kind": "sprites",                       # a static fallback + animations
#      "image": <spec or null>,
#      "animations": {"idle": <animation>, "walk": <animation>, ...}}
#
# ``sheet`` slices a spritesheet left-to-right, then top-to-bottom; ``frames``
# is either a count or an explicit list of frame indices.  ``anim`` is an
# explicit list of frames (each any other spec).  ``sprites`` is the animated
# unit sprite: named animations cut from one spritesheet, with an optional
# static image used for any state that has no animation.
SPRITE_KINDS = ("pack", "image", "shape", "sheet", "anim", "sprites")


def _frames_value(value):
    """Frame selection: an explicit list of indices, or a count (int)."""
    if isinstance(value, (list, tuple)):
        return [max(0, _int(v)) for v in value]
    return max(1, _int(value, 1))


def normalise_animation(spec):
    """One named animation: frames cut from a spritesheet."""
    spec = dict(spec or {})
    return {
        "kind": "sheet",
        "path": str(spec.get("path") or ""),
        "frame_w": max(1, _int(spec.get("frame_w"), 32)),
        "frame_h": max(1, _int(spec.get("frame_h"), 32)),
        "margin": max(0, _int(spec.get("margin"), 0)),
        "spacing": max(0, _int(spec.get("spacing"), 0)),
        "frames": _frames_value(spec.get("frames")),
        "fps": max(0.1, _num(spec.get("fps"), 8.0)),
        "loop": bool(spec.get("loop", True)),
    }


def normalise_upgrade_paths(spec):
    """Normalise a unit's upgrade branches.

    ``None``/empty falls back to :data:`DEFAULT_UPGRADE_PATHS` so every
    defender can always be upgraded along several distinct axes.  Each entry
    becomes ``{"id", "name", "gains"}`` where gains hold multipliers for
    ``damage``/``range``/``rate``/``hp`` and an additive ``projectiles``.
    """
    if not spec:
        return [dict(p, gains=dict(p["gains"])) for p in DEFAULT_UPGRADE_PATHS]
    out = []
    for raw in spec:
        if not isinstance(raw, dict):
            continue
        pid = str(raw.get("id") or "").strip()
        if not pid:
            continue
        gains = {}
        raw_gains = raw.get("gains")
        if isinstance(raw_gains, dict):
            for key in UPGRADE_GAIN_KEYS:
                if raw_gains.get(key) is not None:
                    gains[key] = max(0.01, _num(raw_gains.get(key), 1.0))
            if raw_gains.get("projectiles") is not None:
                gains["projectiles"] = _int(raw_gains.get("projectiles"), 0)
        if not gains:
            continue                      # a branch that changes nothing is useless
        out.append({"id": pid, "name": str(raw.get("name") or pid.title()),
                    "gains": gains})
    return out or [dict(p, gains=dict(p["gains"])) for p in DEFAULT_UPGRADE_PATHS]


def normalise_sprite(spec, default_tile=226):
    """Normalise any sprite spec into a well-formed ``{"kind": ...}`` dict."""
    if spec is None:
        return {"kind": "pack", "tile": default_tile}
    if isinstance(spec, int):
        return {"kind": "pack", "tile": spec}
    if not isinstance(spec, dict):
        return {"kind": "pack", "tile": default_tile}
    kind = spec.get("kind") or "pack"
    if kind == "image":
        return {"kind": "image", "path": str(spec.get("path") or "")}
    if kind == "shape":
        return {"kind": "shape",
                "shape": str(spec.get("shape") or "circle"),
                "color": _color(spec.get("color")) or [200, 200, 200]}
    if kind == "anim":
        frames = [normalise_sprite(f, default_tile)
                  for f in (spec.get("frames") or [])]
        return {"kind": "anim",
                "fps": max(0.1, _num(spec.get("fps"), 8.0)),
                "loop": bool(spec.get("loop", True)),
                "frames": frames or [{"kind": "pack", "tile": default_tile}]}
    if kind == "sheet":
        return {"kind": "sheet",
                "path": str(spec.get("path") or ""),
                "frame_w": max(1, _int(spec.get("frame_w"), 32)),
                "frame_h": max(1, _int(spec.get("frame_h"), 32)),
                "frames": _frames_value(spec.get("frames")),
                "cols": max(0, _int(spec.get("cols"), 0)),
                "rows": max(0, _int(spec.get("rows"), 0)),
                "fps": max(0.1, _num(spec.get("fps"), 8.0)),
                "loop": bool(spec.get("loop", True)),
                "margin": max(0, _int(spec.get("margin"), 0)),
                "spacing": max(0, _int(spec.get("spacing"), 0))}
    if kind == "sprites":
        animations = {}
        for name, anim in (spec.get("animations") or {}).items():
            animations[str(name)] = normalise_animation(anim)
        image = spec.get("image")
        return {"kind": "sprites",
                "image": normalise_sprite(image) if image else None,
                "animations": animations}
    return {"kind": "pack", "tile": _int(spec.get("tile"), default_tile)}


class UnitType:
    """A customisable unit definition, used for defenders and attackers alike."""

    def __init__(self, data):
        data = dict(data or {})
        self.id = str(data.get("id") or "unit")
        self.name = str(data.get("name") or self.id)
        self.side = data.get("side") if data.get("side") in UNIT_SIDES else "defender"
        self.role = str(data.get("role") or "")
        self.sprite = self._sprite(data.get("sprite"))
        self.projectile_sprite = (None if data.get("projectile_sprite") in (None, "", "none")
                                  else self._sprite(data.get("projectile_sprite")))
        self.sprite_scale = max(0.1, _num(data.get("sprite_scale"), 1.0))
        self.tint = _color(data.get("tint"))
        self.hp = max(1, _int(data.get("hp"), 100))
        self.cost = max(0, _int(data.get("cost"), 50))
        self.bounty = max(0, _int(data.get("bounty"), 0))
        self.speed = max(0.0, _num(data.get("speed"), 0.0))
        self.movement = data.get("movement") if data.get("movement") in UNIT_MOVEMENTS else "static"
        self.attack = data.get("attack") if data.get("attack") in UNIT_ATTACKS else "none"
        self.range = max(0.0, _num(data.get("range"), 120.0))
        self.damage = max(0.0, _num(data.get("damage"), 5.0))
        self.cooldown = max(0.01, _num(data.get("cooldown"), 0.5))
        self.projectiles = max(1, _int(data.get("projectiles"), 1))
        self.projectile = data.get("projectile") if data.get("projectile") in ("dot", "rocket") else "dot"
        self.splash = max(0.0, _num(data.get("splash"), 0.0))
        self.sound = str(data.get("sound") or "gun")
        self.targets = data.get("targets") if data.get("targets") in UNIT_TARGETS else "both"
        self.targeting = data.get("targeting") if data.get("targeting") in UNIT_TARGETING else ""
        self.is_flying = bool(data.get("is_flying", False))
        self.damage_to_base = max(0, _int(data.get("damage_to_base"), 1))
        self.stop_to_attack = bool(data.get("stop_to_attack", True))
        self.aggro = max(0.0, _num(data.get("aggro"), 160.0))
        self.radius = max(4.0, _num(data.get("radius"), 16.0))
        self.can_be_attacked = bool(data.get("can_be_attacked", True))
        self.description = str(data.get("description") or "")
        self.upgrade_paths = normalise_upgrade_paths(data.get("upgrade_paths"))
        known = set(DEFAULT_UNIT)
        self.extra = {k: v for k, v in data.items() if k not in known}

    def upgrade_path(self, path_id):
        """The branch with this id, or ``None``."""
        for path in self.upgrade_paths:
            if path["id"] == path_id:
                return path
        return None

    def upgrade_path_ids(self):
        return [p["id"] for p in self.upgrade_paths]

    @staticmethod
    def _sprite(spec):
        """Normalise a sprite spec into ``{"kind": ...}`` form."""
        return normalise_sprite(spec)

    @property
    def is_defender(self):
        return self.side == "defender"

    @property
    def is_attacker(self):
        return self.side == "attacker"

    @property
    def default_targeting(self):
        return self.targeting or ("first" if self.is_defender else "nearest")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "side": self.side,
            "role": self.role,
            "sprite": self.sprite,
            "projectile_sprite": self.projectile_sprite,
            "sprite_scale": self.sprite_scale,
            "tint": self.tint,
            "hp": self.hp,
            "cost": self.cost,
            "bounty": self.bounty,
            "speed": self.speed,
            "movement": self.movement,
            "attack": self.attack,
            "range": self.range,
            "damage": self.damage,
            "cooldown": self.cooldown,
            "projectiles": self.projectiles,
            "projectile": self.projectile,
            "splash": self.splash,
            "sound": self.sound,
            "targets": self.targets,
            "targeting": self.targeting,
            "is_flying": self.is_flying,
            "damage_to_base": self.damage_to_base,
            "stop_to_attack": self.stop_to_attack,
            "aggro": self.aggro,
            "radius": self.radius,
            "can_be_attacked": self.can_be_attacked,
            "description": self.description,
            "upgrade_paths": [
                {"id": p["id"], "name": p["name"], "gains": dict(p["gains"])}
                for p in self.upgrade_paths
            ],
            **self.extra,
        }


# ---------------------------------------------------------------------------
# races & levels
# ---------------------------------------------------------------------------
RACE_DEFAULT = {
    "id": "race",
    "name": "Race",
    "description": "",
    "color": [120, 200, 140],
    "tint": None,            # multiplied onto unit sprites without their own tint
    "order": 0,
    "units": [],             # defender unit ids on offer
    "enemies": [],           # attacker unit ids used when a level has no pool
    "levels": [],            # ordered level ids
    "hero": None,            # defender unit id summoned when the base is hit
}

LEVEL_DEFAULT = {
    "id": "level",
    "race": "race",
    "name": "Level",
    "description": "",
    "gold": 220,
    "gold_per_sec": None,     # passive income; None -> DEFAULT_GOLD_PER_SEC
    "lives": 20,
    "grid": [],
    "terrain_tint": None,
    "available_units": [],   # subset of the race units; empty -> all race units
    "enemy_pool": [],        # subset of the race enemies; empty -> all
    "waves": [],             # [[[unit_id, count, interval], ...], ...]
    "map": "",               # legacy .txt fallback when grid is empty
    "order": 0,
}


class ContentDB:
    """Loads and saves every content file, plus handy queries for the game."""

    def __init__(self, root=None):
        self.root = pathlib.Path(root) if root else paths.content_dir()
        self.terrains = []
        self.terrain_by_char = {}
        self.terrain_by_id = {}
        self.units = {}
        self.races = {}
        self.levels = {}
        self.errors = []
        self.reload()

    # ------------------------------------------------------------- loading
    def _load_json(self, path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            self.errors.append(f"{path.name}: {exc}")
            return None

    def reload(self):
        self.errors = []
        self._load_terrain()
        self._load_units()
        self._load_races()
        self._load_levels()
        return self

    def _load_terrain(self):
        self.terrains = []
        data = self._load_json(self.root / "terrain.json")
        entries = []
        if isinstance(data, dict):
            entries = data.get("terrain") or []
        elif isinstance(data, list):
            entries = data
        for entry in entries:
            try:
                terr = TerrainType(entry)
            except Exception as exc:      # noqa: BLE001 - keep loading the rest
                self.errors.append(f"terrain {entry!r}: {exc}")
                continue
            self.terrains.append(terr)
        if not self.terrains:
            self.terrains = [TerrainType(DEFAULT_TERRAIN)]
        self.terrain_by_char = {t.char: t for t in self.terrains}
        self.terrain_by_id = {t.id: t for t in self.terrains}

    def _load_units(self):
        self.units = {}
        folder = self.root / "units"
        for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
            data = self._load_json(path)
            if not isinstance(data, dict):
                continue
            data.setdefault("id", path.stem)
            unit = UnitType(data)
            self.units[unit.id] = unit

    def _load_races(self):
        self.races = {}
        folder = self.root / "races"
        for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
            data = self._load_json(path)
            if not isinstance(data, dict):
                continue
            data.setdefault("id", path.stem)
            race = dict(RACE_DEFAULT)
            race.update(data)
            race["color"] = _color(race.get("color")) or [120, 200, 140]
            race["tint"] = _color(race.get("tint"))
            race["units"] = [str(u) for u in (race.get("units") or [])]
            race["enemies"] = [str(u) for u in (race.get("enemies") or [])]
            race["levels"] = [str(l) for l in (race.get("levels") or [])]
            race["order"] = _int(race.get("order"), 0)
            self.races[race["id"]] = race

    def _load_levels(self):
        self.levels = {}
        folder = self.root / "levels"
        for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
            data = self._load_json(path)
            if not isinstance(data, dict):
                continue
            data.setdefault("id", path.stem)
            level = dict(LEVEL_DEFAULT)
            level.update(data)
            level["gold"] = _int(level.get("gold"), 220)
            level["lives"] = _int(level.get("lives"), 20)
            level["available_units"] = [str(u) for u in (level.get("available_units") or [])]
            level["enemy_pool"] = [str(u) for u in (level.get("enemy_pool") or [])]
            level["terrain_tint"] = _color(level.get("terrain_tint"))
            level["waves"] = self._normalise_waves(level.get("waves") or [])
            level["order"] = _int(level.get("order"), 0)
            self.levels[level["id"]] = level

    @staticmethod
    def _normalise_waves(waves):
        """Accept loose wave data and return [[(unit_id, count, interval), ...]]."""
        out = []
        for wave in waves:
            groups = []
            for group in wave or []:
                if isinstance(group, dict):
                    uid = group.get("unit") or group.get("id") or "grunt"
                    count = _int(group.get("count"), 1)
                    interval = _num(group.get("interval"), 1.0)
                else:
                    try:
                        uid, count, interval = group[0], group[1], group[2]
                    except (TypeError, IndexError):
                        continue
                    count = _int(count, 1)
                    interval = _num(interval, 1.0)
                groups.append([str(uid), max(1, count), max(0.0, interval)])
            out.append(groups)
        return out

    # ------------------------------------------------------------- queries
    def terrain(self, char):
        return self.terrain_by_char.get(char)

    def unit(self, unit_id):
        return self.units.get(unit_id)

    def race(self, race_id):
        return self.races.get(race_id)

    def level(self, level_id):
        return self.levels.get(level_id)

    def sorted_races(self):
        return sorted(self.races.values(),
                      key=lambda r: (r.get("order", 0), r.get("name", r["id"])))

    def sorted_units(self, side=None):
        units = [u for u in self.units.values() if side is None or u.side == side]
        return sorted(units, key=lambda u: (u.side, u.name.lower()))

    def race_levels(self, race):
        """Level dicts for a race, in the order the race lists them."""
        out = []
        for lid in race.get("levels", []):
            level = self.levels.get(lid)
            if level is not None:
                out.append(level)
        if not out:                       # fall back to any level tagged with it
            out = sorted((l for l in self.levels.values() if l.get("race") == race["id"]),
                         key=lambda l: (l.get("order", 0), l["id"]))
        return out

    def race_units(self, race, side="defender"):
        ids = race.get("units" if side == "defender" else "enemies", [])
        return [self.units[u] for u in ids if u in self.units]

    def level_defenders(self, level):
        race = self.race(level.get("race")) or {}
        ids = level.get("available_units") or race.get("units", [])
        return [self.units[u] for u in ids
                if u in self.units and self.units[u].side == "defender"]

    def level_attackers(self, level):
        race = self.race(level.get("race")) or {}
        ids = level.get("enemy_pool") or race.get("enemies", [])
        return [self.units[u] for u in ids
                if u in self.units and self.units[u].side == "attacker"]

    # ------------------------------------------------------------- saving
    def _write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
        tmp.replace(path)

    def save_terrain(self, terrains=None):
        entries = [t.to_dict() if isinstance(t, TerrainType) else dict(t)
                   for t in (terrains if terrains is not None else self.terrains)]
        self._write(self.root / "terrain.json", {"version": 1, "terrain": entries})

    def save_unit(self, unit):
        data = unit.to_dict() if isinstance(unit, UnitType) else dict(unit)
        self._write(self.root / "units" / f"{data['id']}.json", data)

    def delete_unit(self, unit_id):
        (self.root / "units" / f"{unit_id}.json").unlink(missing_ok=True)

    def save_race(self, race):
        self._write(self.root / "races" / f"{race['id']}.json", dict(race))

    def delete_race(self, race_id):
        (self.root / "races" / f"{race_id}.json").unlink(missing_ok=True)

    def save_level(self, level):
        data = {k: level.get(k, v) for k, v in LEVEL_DEFAULT.items()}
        for k, v in level.items():
            data.setdefault(k, v)
        self._write(self.root / "levels" / f"{level['id']}.json", data)

    def delete_level(self, level_id):
        (self.root / "levels" / f"{level_id}.json").unlink(missing_ok=True)

    def save_terrain_entry(self, entry):
        """Create or replace a single terrain entry inside terrain.json."""
        data = entry.to_dict() if isinstance(entry, TerrainType) else dict(entry)
        entries = [t.to_dict() for t in self.terrains]
        for i, existing in enumerate(entries):
            if existing.get("id") == data.get("id"):
                entries[i] = data
                break
        else:
            entries.append(data)
        self.save_terrain(entries)

    def delete_orphans(self, folder, keep_ids):
        """Remove ``folder/*.json`` files whose stem is not in ``keep_ids``.

        Used by the designer's Save/Delete buttons so removing an entry there
        also removes its file.  ``terrain`` lives in a single file, so it has
        nothing to clean up.
        """
        if folder == "terrain":
            return
        directory = self.root / folder
        if not directory.is_dir():
            return
        keep = {str(k) for k in keep_ids}
        for path in directory.glob("*.json"):
            if path.stem not in keep:
                path.unlink(missing_ok=True)

    # ------------------------------------------------------------- ids
    @staticmethod
    def slug(text, fallback="item"):
        keep = [c.lower() if (c.isalnum() or c in "-_") else "_" for c in str(text).strip()]
        slug = "".join(keep).strip("_")
        return slug or fallback

    def unique_unit_id(self, base):
        return self._unique(base, set(self.units))

    def unique_race_id(self, base):
        return self._unique(base, set(self.races))

    def unique_level_id(self, base):
        return self._unique(base, set(self.levels))

    @staticmethod
    def _unique(base, taken):
        base = base or "item"
        if base not in taken:
            return base
        n = 2
        while f"{base}_{n}" in taken:
            n += 1
        return f"{base}_{n}"


# ---------------------------------------------------------------------------
# cached singleton
# ---------------------------------------------------------------------------
_instance = None


def get_content(reload=False):
    """Return the process-wide :class:`ContentDB` (loading it on first use)."""
    global _instance
    if _instance is None or reload:
        _instance = ContentDB()
    return _instance


def set_content(db):
    """Replace the cached database (used by tests and the designer)."""
    global _instance
    _instance = db

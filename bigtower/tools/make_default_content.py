#!/usr/bin/env python3
"""Generate the default ``content/`` tree from the legacy hardcoded data.

This is a one-shot migration / authoring helper: it writes the terrain palette,
the shared unit roster (defenders *and* enemies), three races and their levels
(converted from ``maps/*.txt`` and re-themed per race), then validates that
every level's spawn can still reach its base over walkable terrain.

Run it from the bigtower directory::

    .venv/bin/python tools/make_default_content.py
"""
import json
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"

# --------------------------------------------------------------------------
# terrain
# --------------------------------------------------------------------------
TERRAIN = [
    {"id": "grass", "name": "Grass", "char": "g", "base": 157, "overlay": None,
     "buildable": True, "walkable": True, "tint": None,
     "description": "Plain buildable field."},
    {"id": "road", "name": "Road", "char": ".", "base": 158, "overlay": None,
     "buildable": False, "walkable": True, "tint": None,
     "description": "The path enemies walk along. Not buildable."},
    {"id": "rock", "name": "Rock", "char": "r", "base": 157, "overlay": 136,
     "buildable": False, "walkable": False, "tint": None,
     "description": "Boulder: blocks movement and building."},
    {"id": "bush", "name": "Bush", "char": "t", "base": 157, "overlay": 131,
     "buildable": False, "walkable": False, "tint": None,
     "description": "Leafy cover: blocks movement and building."},
    {"id": "sand", "name": "Sand", "char": "s", "base": 188, "overlay": None,
     "buildable": True, "walkable": True, "tint": None,
     "description": "Warm buildable ground."},
    {"id": "stone", "name": "Stone", "char": "o", "base": 159, "overlay": None,
     "buildable": True, "walkable": True, "tint": None,
     "description": "Cool buildable ground."},
    {"id": "water", "name": "Water", "char": "w", "base": 159, "overlay": None,
     "buildable": False, "walkable": False, "tint": [130, 180, 255],
     "description": "Blocks movement and building."},
    {"id": "ice", "name": "Ice", "char": "n", "base": 188, "overlay": None,
     "buildable": True, "walkable": True, "tint": [198, 222, 255],
     "description": "Frozen buildable ground."},
    {"id": "lava", "name": "Lava", "char": "l", "base": 188, "overlay": None,
     "buildable": False, "walkable": False, "tint": [255, 120, 60],
     "description": "Blocks movement and building."},
]

# --------------------------------------------------------------------------
# units  (defenders then attackers -- one shared schema)
# --------------------------------------------------------------------------
DEFENDERS = [
    dict(id="gun", name="Gun Turret", role="ranged", sprite={"kind": "pack", "tile": 226},
         sprite_scale=0.95, hp=200, cost=50, range=135, damage=9, cooldown=0.40,
         projectile="dot", sound="gun", movement="static", attack="projectile",
         targets="both", description="Cheap all-rounder that shoots ground and air."),
    dict(id="scorpion", name="Scorpion", role="melee", sprite={"kind": "image", "path": "units/towers/forest-towers/scorpion-tower/scorpion-001.png"},
         sprite_scale=0.92, hp=260, cost=80, speed=85, range=46, damage=11, cooldown=0.55,
         movement="chase", attack="melee", targets="ground", sound="sting", aggro=210,
         description="Melee beast: chases the nearest enemy and stings it."),
    dict(id="thornling", name="Thornling", role="melee", sprite={"kind": "pack", "tile": 227},
         sprite_scale=0.9, hp=140, cost=45, speed=120, range=40, damage=6, cooldown=0.35,
         movement="chase", attack="melee", targets="ground", sound="sting", aggro=190,
         description="Fast, cheap melee chaser."),
    dict(id="spitter", name="Spitter", role="ranged", sprite={"kind": "pack", "tile": 228},
         sprite_scale=0.9, hp=190, cost=90, range=150, damage=14, cooldown=0.70,
         movement="static", attack="projectile", projectile="dot", sound="gun",
         description="Steady mid-range shooter."),
    dict(id="tesla", name="Tesla Coil", role="ranged", sprite={"kind": "pack", "tile": 229},
         sprite_scale=0.95, hp=170, cost=130, range=120, damage=7, cooldown=0.12,
         movement="static", attack="projectile", projectile="dot", sound="gun",
         description="Very fast zapper, low damage per bolt."),
    dict(id="missile", name="Missile Silo", role="splash", sprite={"kind": "pack", "tile": 205},
         sprite_scale=0.95, hp=180, cost=110, range=175, damage=30, cooldown=1.30,
         movement="static", attack="projectile", projectile="rocket", splash=56, sound="missile",
         description="Splash rockets that hit groups."),
    dict(id="cannon", name="Cannon", role="splash", sprite={"kind": "pack", "tile": 230},
         sprite_scale=0.95, hp=240, cost=150, range=145, damage=42, cooldown=1.60,
         movement="static", attack="projectile", projectile="rocket", splash=70, sound="missile",
         description="Slow, heavy splash artillery."),
    dict(id="flak", name="Flak Battery", role="anti-air", sprite={"kind": "pack", "tile": 231},
         sprite_scale=0.95, hp=180, cost=100, range=165, damage=13, cooldown=0.45,
         movement="static", attack="projectile", projectile="dot", targets="air", sound="gun",
         description="Rapid anti-air only."),
    dict(id="snakewatch", name="Snakewatch", role="sniper", sprite={"kind": "image", "path": "units/towers/forest-towers/snakewatch-tower/snakewatch-001.png"},
         sprite_scale=0.98, hp=150, cost=160, range=270, damage=70, cooldown=1.80,
         movement="static", attack="projectile", projectile="dot", sound="sniper",
         targets="both", description="Extreme range, huge single shots."),
    dict(id="bulwark", name="Bulwark", role="melee", sprite={"kind": "pack", "tile": 232},
         sprite_scale=1.0, hp=430, cost=140, speed=60, range=44, damage=18, cooldown=0.90,
         movement="chase", attack="melee", targets="ground", sound="sting", aggro=170,
         description="Armoured melee brawler that walks to the enemy."),
]

ATTACKERS = [
    dict(id="grunt", name="Grunt", sprite={"kind": "pack", "tile": 247}, sprite_scale=1.6,
         hp=42, speed=55, bounty=6, damage_to_base=1, radius=16, movement="route",
         attack="none", description="Basic ground trooper."),
    dict(id="runner", name="Runner", sprite={"kind": "pack", "tile": 248}, sprite_scale=1.45,
         hp=30, speed=100, bounty=8, damage_to_base=1, radius=14, movement="route",
         attack="none", description="Fast and fragile."),
    dict(id="swarm", name="Drone", sprite={"kind": "pack", "tile": 276}, sprite_scale=1.0,
         hp=18, speed=150, bounty=4, damage_to_base=1, radius=11, movement="route",
         attack="none", description="Tiny, very fast swarm unit."),
    dict(id="armored", name="Armored", sprite={"kind": "pack", "tile": 249}, sprite_scale=1.25,
         hp=130, speed=40, bounty=15, damage_to_base=2, radius=18, movement="route",
         attack="melee", range=42, damage=7, cooldown=1.1, stop_to_attack=True,
         targets="ground", sound="sting",
         description="Stops to batter nearby defenders on its way past."),
    dict(id="spitter_foe", name="Spitter", sprite={"kind": "pack", "tile": 277}, sprite_scale=1.2,
         hp=60, speed=60, bounty=10, damage_to_base=1, radius=15, movement="route",
         attack="projectile", projectile="dot", range=135, damage=7, cooldown=1.4,
         targets="ground", sound="gun",
         description="Shoots defenders from the path."),
    dict(id="jet", name="Jet", sprite={"kind": "pack", "tile": 270}, sprite_scale=1.1,
         hp=65, speed=130, bounty=13, damage_to_base=1, radius=15, is_flying=True,
         movement="direct", attack="none", description="Flies straight to the base."),
    dict(id="bomber", name="Bomber", sprite={"kind": "pack", "tile": 271}, sprite_scale=1.2,
         hp=90, speed=90, bounty=18, damage_to_base=2, radius=16, is_flying=True,
         movement="direct", attack="projectile", projectile="rocket", range=120,
         damage=12, cooldown=1.6, targets="ground", sound="missile",
         description="Flies over the map bombing defenders."),
    dict(id="brute", name="Brute", sprite={"kind": "pack", "tile": 249}, sprite_scale=1.5,
         tint=[255, 150, 130], hp=220, speed=42, bounty=22, damage_to_base=2, radius=20,
         movement="hunt", attack="melee", range=46, damage=14, cooldown=0.9,
         stop_to_attack=True, aggro=210, targets="ground", sound="sting",
         description="Hunts down the nearest defender and smashes it."),
    dict(id="tank", name="Siege Tank", sprite={"kind": "pack", "tile": 250}, sprite_scale=1.4,
         hp=400, speed=28, bounty=45, damage_to_base=3, radius=21, movement="route",
         attack="projectile", projectile="rocket", range=125, damage=20, cooldown=2.0,
         splash=40, targets="ground", sound="missile",
         description="Slow siege unit that shells defenders."),
    dict(id="warlord", name="Warlord", sprite={"kind": "pack", "tile": 278}, sprite_scale=2.0,
         hp=900, speed=26, bounty=120, damage_to_base=5, radius=24, movement="route",
         attack="projectile", projectile="rocket", range=150, damage=25, cooldown=2.2,
         splash=48, targets="both", sound="missile",
         description="Boss. Soaks damage and shells everything."),
]

# --------------------------------------------------------------------------
# races
# --------------------------------------------------------------------------
RACES = [
    dict(id="woodlanders", name="Woodlanders", order=0,
         color=[110, 200, 120], tint=[185, 255, 185],
         description="Forest folk. Cheap swarms of chasers backed by long-range snipers.",
         units=["gun", "scorpion", "thornling", "spitter", "missile", "snakewatch"],
         enemies=["grunt", "runner", "armored", "jet", "brute", "tank"],
         levels=["woodlanders_01", "woodlanders_02", "woodlanders_03"]),
    dict(id="aliens", name="The Brood", order=1,
         color=[150, 120, 230], tint=[170, 220, 255],
         description="Alien hive. Fragile fast drones, zappers and heavy siege.",
         units=["gun", "tesla", "spitter", "missile", "flak", "bulwark"],
         enemies=["swarm", "spitter_foe", "jet", "bomber", "brute", "warlord"],
         levels=["aliens_01", "aliens_02", "aliens_03"]),
    dict(id="machines", name="Iron Legion", order=2,
         color=[220, 150, 120], tint=[255, 190, 160],
         description="War machines. Slow, armoured and equipped with heavy artillery.",
         units=["gun", "cannon", "missile", "flak", "snakewatch", "bulwark"],
         enemies=["grunt", "armored", "tank", "bomber", "warlord", "runner"],
         levels=["machines_01", "machines_02", "machines_03"]),
]

# --------------------------------------------------------------------------
# level grids: the three legacy maps, re-themed for the other races
# --------------------------------------------------------------------------
def read_map(name):
    rows = []
    for line in (ROOT / "maps" / name).read_text().splitlines():
        line = line.rstrip("\n")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        rows.append(line)
    return rows


def re_theme(rows, mapping):
    return ["".join(mapping.get(ch, ch) for ch in row) for row in rows]


WOOD_GRIDS = [read_map(f"level{n}.txt") for n in (1, 2, 3)]
ALIEN_GRIDS = [re_theme(g, {"g": "s", "t": "w", "r": "w"}) for g in WOOD_GRIDS]
MACHINE_GRIDS = [re_theme(g, {"g": "o", "t": "r", "r": "l"}) for g in WOOD_GRIDS]

LEVEL_META = [
    # level 1 template
    dict(name="Greenfield Road", gold=220, lives=20,
         waves=[("grunt", 6, 1.3), ("grunt", 9, 1.0), ("grunt", 6, 1.0),
                ("armored", 5, 2.0), ("runner", 10, 0.8),
                ("grunt", 8, 0.8), ("jet", 8, 1.1), ("armored", 8, 1.6),
                ("tank", 1, 0), ("tank", 2, 6.0)]),
    # level 2 template
    dict(name="Twin Brooks", gold=250, lives=20,
         waves=[("grunt", 8, 1.1), ("runner", 8, 1.0), ("armored", 5, 1.9),
                ("jet", 7, 1.2), ("runner", 12, 0.7), ("armored", 8, 1.5),
                ("jet", 10, 0.9), ("tank", 1, 0), ("runner", 14, 0.6),
                ("armored", 10, 1.3), ("tank", 2, 5.0), ("tank", 2, 5.0)]),
    # level 3 template
    dict(name="Serpent's Coil", gold=280, lives=15,
         waves=[("grunt", 8, 1.0), ("armored", 6, 1.7), ("runner", 12, 0.7),
                ("jet", 9, 1.0), ("armored", 8, 1.4), ("tank", 1, 0),
                ("jet", 12, 0.8), ("armored", 10, 1.2), ("tank", 2, 4.0),
                ("jet", 12, 0.7), ("armored", 12, 1.1), ("tank", 2, 4.0),
                ("armored", 12, 1.0), ("tank", 3, 3.5), ("tank", 4, 3.0)]),
]

THEMED_NAMES = {
    "aliens": ["Dust Landing", "The Shallows", "Spiral Basin"],
    "machines": ["Cold Foundry", "Rust Flats", "The Coilworks"],
}


def build_waves(template, enemy_ids):
    """Turn a compact [(uid, count, interval), ...] template into wave groups.

    Each evergreen entry becomes its own wave (one group); the roster is
    re-pointed at the race's enemies by cycling its list so every race uses its
    own units while keeping the difficulty curve.
    """
    stats = {
        "grunt": ("grunt", 6, 1.2), "runner": ("runner", 8, 0.9),
        "armored": ("armored", 6, 1.6), "jet": ("jet", 8, 1.0),
        "swarm": ("swarm", 12, 0.6), "spitter_foe": ("spitter_foe", 6, 1.4),
        "bomber": ("bomber", 6, 1.3), "brute": ("brute", 4, 1.7),
        "tank": ("tank", 1, 5.0), "warlord": ("warlord", 1, 8.0),
    }
    # difficulty ramp: index -> how many of the race's units appear together
    waves = []
    for i, (uid, count, interval) in enumerate(template):
        picks = []
        if uid == "tank":
            picks = [e for e in enemy_ids if e in ("tank", "warlord")] or [enemy_ids[-1]]
        elif uid == "jet":
            picks = [e for e in enemy_ids if e in ("jet", "bomber")] or [enemy_ids[0]]
        elif uid == "runner" or uid == "swarm":
            picks = [enemy_ids[1 % len(enemy_ids)]]
        elif uid == "armored":
            picks = [e for e in enemy_ids if e in ("armored", "brute")] or [enemy_ids[1 % len(enemy_ids)]]
        else:
            picks = [enemy_ids[0]]
        groups = []
        for pick in picks:
            base = stats.get(pick, (pick, count, interval))
            scale = 1.0 + 0.12 * i
            groups.append([pick, max(1, int(round(base[1] * scale))), base[2]])
        waves.append(groups)
    return waves


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------
def path_ok(grid, walkable_chars):
    spawn = base = None
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch == "S":
                spawn = (x, y)
            elif ch == "B":
                base = (x, y)
    if spawn is None or base is None:
        return False, "missing S or B"
    seen = {spawn}
    q = deque([spawn])
    while q:
        x, y = q.popleft()
        if (x, y) == base:
            return True, "ok"
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if n in seen:
                continue
            nx, ny = n
            if not (0 <= ny < len(grid) and 0 <= nx < len(grid[0])):
                continue
            ch = grid[ny][nx]
            if ch in walkable_chars:
                seen.add(n)
                q.append(n)
    return False, "no path"


def main():
    walkable = {t["char"] for t in TERRAIN if t["walkable"]} | {"S", "B"}
    race_grids = {
        "woodlanders": WOOD_GRIDS,
        "aliens": ALIEN_GRIDS,
        "machines": MACHINE_GRIDS,
    }
    failures = []
    for race_id, grids in race_grids.items():
        for idx, grid in enumerate(grids):
            ok, why = path_ok(grid, walkable)
            if not ok:
                failures.append(f"{race_id} level {idx + 1}: {why}")
    if failures:
        print("MAP VALIDATION FAILED:")
        for f in failures:
            print("  -", f)
        return 1

    CONTENT.mkdir(parents=True, exist_ok=True)
    (CONTENT / "terrain.json").write_text(
        json.dumps({"version": 1, "terrain": TERRAIN}, indent=2) + "\n")
    for unit in DEFENDERS:
        data = dict(unit)
        data.setdefault("side", "defender")
        (CONTENT / "units").mkdir(parents=True, exist_ok=True)
        (CONTENT / "units" / f"{data['id']}.json").write_text(
            json.dumps(data, indent=2) + "\n")
    for unit in ATTACKERS:
        data = dict(unit)
        data["side"] = "attacker"
        (CONTENT / "units" / f"{data['id']}.json").write_text(
            json.dumps(data, indent=2) + "\n")

    for race in RACES:
        race = dict(race)
        (CONTENT / "races").mkdir(parents=True, exist_ok=True)
        (CONTENT / "races" / f"{race['id']}.json").write_text(
            json.dumps(race, indent=2) + "\n")
        grids = race_grids[race["id"]]
        for i, (meta, grid) in enumerate(zip(LEVEL_META, grids), start=1):
            level_id = f"{race['id']}_{i:02d}"
            name = (THEMED_NAMES.get(race["id"], [meta["name"]] * 3)[i - 1]
                    if race["id"] != "woodlanders" else meta["name"])
            level = {
                "id": level_id,
                "race": race["id"],
                "name": name,
                "description": "",
                "gold": meta["gold"],
                "lives": meta["lives"],
                "order": i,
                "grid": grid,
                "terrain_tint": None,
                "available_units": list(race["units"]),
                "enemy_pool": list(race["enemies"]),
                "waves": build_waves(meta["waves"], race["enemies"]),
            }
            (CONTENT / "levels").mkdir(parents=True, exist_ok=True)
            (CONTENT / "levels" / f"{level_id}.json").write_text(
                json.dumps(level, indent=2) + "\n")
    print(f"Wrote content to {CONTENT}")
    print(f"  terrain: {len(TERRAIN)}  units: {len(DEFENDERS) + len(ATTACKERS)}"
          f"  races: {len(RACES)}  levels: {len(RACES) * 3}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

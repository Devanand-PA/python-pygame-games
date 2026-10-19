#!/usr/bin/env python3
"""Regenerate the shipped ``content/levels/*.json`` grids as large 40x20 maps.

The campaign ships nine levels (three per race) whose original grids were the
tiny 20x10 legacy maps -- exactly the size of the play viewport.  Now that the
game camera can pan over a map that is larger than the screen, the shipped maps
are enlarged to **40 cols x 20 rows** (2560 x 1280 px at 64 px tiles) so the
panning feature is actually exercised by real content.

How the maps are built
----------------------
Every level keeps the *character* of its original 20x10 design (race theme,
where the spawn and the base sit, the general flow of the road) but is redrawn
as a long serpentine road across the bigger field:

1. **Route.**  A level spec describes a polyline: a spawn, a monotone list of
   ``lanes`` (rows for horizontal sweeps, columns for vertical sweeps), the
   sweep ``bounds`` and the base.  The polyline is rasterised into a 4-connected
   road of ``.`` cells.  Level 1 maps sweep east-west across the whole field,
   level 2 maps double back (two long prongs), level 3 maps coil inward.
2. **Buildable pockets.**  The engine resolves the enemy route with a BFS over
   *walkable* terrain, and plain grass is walkable -- a road drawn on an open
   field is decorative only (the shipped 20x10 maps really are shortcut from
   26 cells down to 7).  So the open buildable ground is grown as pockets that
   hug the road, and everything else becomes solid blocking terrain.  A pocket
   cell is only kept when it touches no road cell more than ``SHORTCUT_LIMIT``
   cells away along the route, which keeps the BFS route pinned to the road.
   The base and the spawn are additionally walled in on three sides so the only
   way in is along the road.
3. **Texture.**  Blocking terrain is painted from a seeded value-noise field
   (forest / shallow water / slag, per race) and the pockets get a light
   scatter of boulders and thickets so the buildable ground is not a slab.

Everything is deterministic: the route comes from the specs in this file and
the scenery from a fixed seed, so re-running the script reproduces the exact
same maps.  Only the ``grid`` field of each level JSON is rewritten; every other
field is preserved and the pretty 2-space JSON style is kept.

Usage::

    .venv/bin/python tools/big_maps.py            # regenerate + validate + verify
    .venv/bin/python tools/big_maps.py --dry-run  # build and validate, write nothing
    .venv/bin/python tools/big_maps.py --show     # also print the maps as ASCII
    .venv/bin/python tools/big_maps.py --verify   # only re-check what is on disk

Nothing is written unless every grid passes validation.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
LEVELS_DIR = CONTENT / "levels"
TERRAIN_JSON = CONTENT / "terrain.json"

# --- target map size ------------------------------------------------------
COLS = 40
ROWS = 20

# --- master seed: every level derives its own stream from it --------------
MASTER_SEED = 20260411

SPAWN = "S"
BASE = "B"
ROAD = "."
NEIGH4 = ((1, 0), (-1, 0), (0, 1), (0, -1))

# --- generation tuning ----------------------------------------------------
SHORTCUT_LIMIT = 3      # a pocket cell may not touch road this far along the route
POCKET_WIDTH = 3        # how deep a buildable pocket may grow from the road
BOTH_SIDES = 0.35       # chance a road cell grows pockets on both sides
PLAZA_RADIUS = 4        # occasional wide buildable clearing
PATH_RATIO_MIN = 0.75   # enemy route (BFS) must cover >= this fraction of the road
BUILDABLE_NEAR_MIN = 60  # buildable cells within 2 cells of the route


# ---------------------------------------------------------------------------
# race palettes -- the char vocabulary each race is allowed to use
# ---------------------------------------------------------------------------
PALETTES = {
    "woodlanders": {
        "ground": "g",          # grass: buildable + walkable
        "blockers": (("t", 0.66), ("r", 0.34)),   # bush thicket / boulders
        "pocket_clumps": (("t", 0.7), ("r", 0.3)),
    },
    "aliens": {
        "ground": "s",          # sand: the re-theme of grass
        "accent": ("n", 0.05),  # a little frozen crust in the pockets
        "blockers": (("w", 0.62), ("l", 0.38)),   # water / lava pools
        "pocket_clumps": (("l", 0.55), ("w", 0.45)),
    },
    "machines": {
        "ground": "o",          # stone: the re-theme of grass
        "blockers": (("r", 0.6), ("l", 0.4)),     # scrap rock / slag
        "pocket_clumps": (("r", 0.7), ("l", 0.3)),
    },
}


# ---------------------------------------------------------------------------
# level specs: the shape of the nine enlarged maps
# ---------------------------------------------------------------------------
# axis    'h' -- the road sweeps horizontally along `lanes` rows
#         'v' -- the road sweeps vertically along `lanes` columns
# lanes   sweep coordinates, monotone (increasing or decreasing)
# bounds  sweep end coordinate: a (a, b) tuple to alternate between, or one
#         value per lane when a coil has to spiral inwards
# link    'orth' -- right-angle connectors, 'diag' + diag_shift -- slanted ramps
# start   spawn cell (on the map border, on the first lane)
# base    base cell: always at least two cells past the last lane, so the home
#         run neither crosses nor runs alongside an earlier sweep
LEVEL_SPECS = [
    # ---- level 1: the long east-west highway (the original Greenfield Road)
    dict(level_id="woodlanders_01", race="woodlanders", seed=101,
         axis="h", lanes=[1, 5, 9, 13, 17], bounds=(4, 35), jitter=2,
         start=(0, 1), base=(38, 19), link="orth"),
    dict(level_id="aliens_01", race="aliens", seed=211,
         axis="h", lanes=[1, 4, 7, 11, 14, 17], bounds=(3, 36), jitter=2,
         start=(0, 1), base=(30, 19), link="orth"),
    dict(level_id="machines_01", race="machines", seed=307,
         axis="h", lanes=[18, 12, 6], bounds=(5, 35), jitter=2,
         start=(0, 18), base=(38, 0), link="diag", diag_shift=4),

    # ---- level 2: double back, two long prongs and a home run (Twin Brooks)
    dict(level_id="woodlanders_02", race="woodlanders", seed=113,
         axis="h", lanes=[1, 6, 12, 17], bounds=(5, 36), jitter=1,
         start=(0, 1), base=(3, 19), link="orth"),
    dict(level_id="aliens_02", race="aliens", seed=223,
         axis="v", lanes=[4, 11, 18, 25, 32], bounds=(2, 17), jitter=1,
         start=(0, 18), base=(39, 18), link="orth"),
    dict(level_id="machines_02", race="machines", seed=311,
         axis="h", lanes=[18, 13, 8, 3], bounds=(7, 33), jitter=1,
         start=(0, 18), base=(37, 0), link="diag", diag_shift=3),

    # ---- level 3: the coil (Serpent's Coil / Spiral Basin / The Coilworks)
    dict(level_id="woodlanders_03", race="woodlanders", seed=127,
         axis="h", lanes=[1, 4, 7, 10, 13, 16], bounds=[34, 3, 30, 6, 24, 20],
         jitter=1, start=(0, 1), base=(30, 19), link="orth"),
    dict(level_id="aliens_03", race="aliens", seed=229,
         axis="h", lanes=[1, 5, 9, 13, 17], bounds=[36, 2, 31, 5, 25],
         jitter=1, start=(0, 1), base=(24, 19), link="diag", diag_shift=3),
    dict(level_id="machines_03", race="machines", seed=317,
         axis="v", lanes=[3, 9, 15, 21, 27, 33], bounds=[2, 17, 3, 17, 4, 16],
         jitter=1, start=(0, 18), base=(38, 12), link="orth"),
]


# ---------------------------------------------------------------------------
# terrain palette (read from content/terrain.json -- never hardcoded)
# ---------------------------------------------------------------------------
def load_terrain():
    data = json.loads(TERRAIN_JSON.read_text(encoding="utf-8"))
    terrain = data["terrain"]
    return {
        "chars": {t["char"] for t in terrain},
        "walkable": {t["char"] for t in terrain if t.get("walkable")} | {SPAWN, BASE},
        "buildable": {t["char"] for t in terrain if t.get("buildable")},
    }


def pick_weighted(rng, table, value):
    """Pick a char from ``[(char, weight), ...]`` using ``value`` in [0, 1)."""
    total = sum(w for _, w in table)
    acc = value * total
    upto = 0.0
    for char, weight in table:
        upto += weight
        if acc < upto:
            return char
    return table[-1][0]


# ---------------------------------------------------------------------------
# route: spec polyline -> 4-connected road cells
# ---------------------------------------------------------------------------
def in_bounds(x, y):
    return 0 <= x < COLS and 0 <= y < ROWS


def _line_cells(a, b):
    """Cells of the 4-connected segment from ``a`` to ``b`` (both included).

    Axis-aligned when only one coordinate differs (the usual right-angle road
    connector); otherwise a staircase that only ever steps one axis at a time,
    so the enemy route stays walkable.
    """
    (x, y), (x1, y1) = a, b
    cells = [(x, y)]
    while (x, y) != (x1, y1):
        if abs(x1 - x) > abs(y1 - y):
            x += 1 if x1 > x else -1
        else:
            y += 1 if y1 > y else -1
        cells.append((x, y))
    return cells


def _check_spec(spec):
    """Guard rails on a spec, so a bad edit fails loudly instead of silently."""
    name = spec["level_id"]
    lanes = spec["lanes"]
    if lanes != sorted(lanes) and lanes != sorted(lanes, reverse=True):
        raise ValueError(f"{name}: lanes must be monotone")
    if len(set(lanes)) != len(lanes):
        raise ValueError(f"{name}: lanes must be distinct")
    for cell in (spec["start"], spec["base"]):
        if not in_bounds(*cell):
            raise ValueError(f"{name}: endpoint {cell} is off the map")
    lane_axis = 1 if spec["axis"] == "h" else 0
    sx, sy = spec["start"]
    if sx not in (0, COLS - 1) and sy not in (0, ROWS - 1):
        raise ValueError(f"{name}: the spawn should sit on the map border")
    # the base sits past the last lane, at least two cells clear of it, so the
    # home run neither crosses nor runs alongside an earlier sweep
    last = lanes[-1]
    step = 1 if lanes[-1] >= lanes[0] else -1
    clear = (spec["base"][lane_axis] - last) * step
    if clear < 2:
        raise ValueError(f"{name}: base must sit at least 2 past the last lane")


def route_points(spec, rng):
    """The corner points of the road polyline described by a level spec."""
    lanes = list(spec["lanes"])
    if isinstance(spec["bounds"], tuple):      # (a, b): alternate between the two
        bounds_list = None
        a, b = spec["bounds"]
    else:                                     # list: one sweep end per lane
        bounds_list = list(spec["bounds"])
        a, b = bounds_list[0], bounds_list[1]
        if len(bounds_list) != len(lanes):
            raise ValueError(f"{spec['level_id']}: bounds must be a tuple or one per lane")

    jitter = spec.get("jitter", 0)
    horizontal = spec["axis"] == "h"
    span = COLS if horizontal else ROWS
    lo, hi = 2, span - 3            # keep sweeps clear of the border

    def bound_for(i):
        value = bounds_list[i] if bounds_list else (a if i % 2 == 0 else b)
        value += rng.randint(-jitter, jitter)
        return max(lo, min(hi, value))

    points = [tuple(spec["start"])]
    cursor = points[0]

    def at(along, lane):
        return (along, lane) if horizontal else (lane, along)

    def along_of(cell):
        return cell[0] if horizontal else cell[1]

    for i, lane in enumerate(lanes):
        # get onto the first lane (spawns that are not already on it sit on the border)
        if (cursor[1] if horizontal else cursor[0]) != lane:
            corner = (cursor[0], lane) if horizontal else (lane, cursor[1])
            points.append(corner)
            cursor = corner
        sweep_start = along_of(cursor)
        end = bound_for(i)
        points.append(at(end, lane))
        cursor = points[-1]
        if i + 1 < len(lanes):
            nxt = lanes[i + 1]
            drift = spec.get("diag_shift", 0) if spec.get("link") == "diag" else 0
            next_bound = bound_for(i + 1)
            away = 1 if next_bound > end else -1
            gap = abs(nxt - lane)
            if drift and gap >= 4 and abs(next_bound - end) > drift + 1:
                # A ramp has to reach the next sweep from its open side and must
                # not run alongside the sweep it leaves, or the two merge into
                # one street and the BFS route stops matching the drawing.  So:
                # step two cells clear of the sweep we are leaving, slant across
                # the middle of the gap and drop onto the next sweep between its
                # start and its far end.  Tight gaps fall back to a right angle.
                step = 1 if nxt > lane else -1
                landing = end + away * drift
                points.append(at(end, lane + 2 * step))
                points.append(at(landing, nxt - 2 * step))
                points.append(at(landing, nxt - step))
                points.append(at(landing, nxt))
            else:
                points.append(at(end, nxt))
            cursor = points[-1]
    # home run: perpendicular off the last lane, then along to the base
    base = tuple(spec["base"])
    corner = (cursor[0], base[1]) if horizontal else (base[0], cursor[1])
    if corner != cursor:
        points.append(corner)
    points.append(base)
    return points


def build_route(spec, rng):
    """Rasterise a level spec into the ordered list of road cells."""
    points = route_points(spec, rng)
    cells = []
    for a, b in zip(points, points[1:]):
        segment = _line_cells(a, b)
        cells.extend(segment if not cells else segment[1:])
    return cells


def route_is_simple(route):
    """A route may not revisit a cell nor touch itself out of order.

    Touching would let the engine's BFS skip a loop, so the road would look
    winding but play as a shortcut -- exactly what we are trying to avoid.
    """
    seen = {}
    for i, cell in enumerate(route):
        if cell in seen:
            return False
        seen[cell] = i
    for i, cell in enumerate(route):
        for n in NEIGH4:
            j = seen.get((cell[0] + n[0], cell[1] + n[1]))
            if j is not None and j < i - 1:
                return False
    return True


# ---------------------------------------------------------------------------
# scenery: buildable pockets + painted terrain
# ---------------------------------------------------------------------------
def grow_pockets(route, rng):
    """Grow buildable ground that hugs the road without short-circuiting it.

    A pocket is a patch of walkable buildable terrain next to the road.  The
    engine resolves the enemy route with a BFS over *walkable* cells, so a
    pocket that quietly links two far-apart parts of the road would let the
    horde cut straight across the field and the map would play nothing like it
    looks.  Every pocket therefore tracks the window of route indices it
    touches: a cell is only accepted when the whole patch it would join stays
    within ``SHORTCUT_LIMIT`` steps of the route.  That keeps the corners
    walled in and pins the route to the road.
    """
    idx = {cell: i for i, cell in enumerate(route)}
    road = set(route)
    regions = []                       # list of {"cells": set} pocket patches

    def try_add(cell, anchor):
        """Add ``cell`` to the pockets if the patch it joins stays coherent."""
        if not in_bounds(*cell) or cell in road:
            return None
        touching = []
        merged = {cell}
        for region in regions:
            if any((cell[0] + dx, cell[1] + dy) in region["cells"] for dx, dy in NEIGH4):
                touching.append(region)
                merged |= region["cells"]
        lo = hi = anchor
        for candidate in merged:
            for dx, dy in NEIGH4:
                j = idx.get((candidate[0] + dx, candidate[1] + dy))
                if j is not None:
                    lo = min(lo, j)
                    hi = max(hi, j)
        if hi - lo > SHORTCUT_LIMIT:
            return None
        for region in touching:
            regions.remove(region)
        regions.append({"cells": merged})
        return merged

    for i, cell in enumerate(route):
        prev = route[i - 1] if i else route[1]
        nxt = route[i + 1] if i + 1 < len(route) else route[i - 1]
        dx, dy = nxt[0] - prev[0], nxt[1] - prev[1]
        if dx == 0 and dy == 0:
            continue
        perps = [(-dy, dx), (dy, -dx)]
        rng.shuffle(perps)
        sides = 2 if rng.random() < BOTH_SIDES else 1
        for p in perps[:sides]:
            depth = rng.randint(1, POCKET_WIDTH)
            for k in range(1, depth + 1):
                target = (cell[0] + p[0] * k, cell[1] + p[1] * k)
                if try_add(target, i) is None:
                    break
                # a little chunkiness so pockets read as fields, not ribbons
                if rng.random() < 0.45:
                    for n in NEIGH4:
                        try_add((target[0] + n[0], target[1] + n[1]), i)

    # a handful of wide clearings where a big tower cluster can be planted
    for _ in range(max(1, len(route) // 45)):
        i = rng.randrange(SHORTCUT_LIMIT, len(route) - SHORTCUT_LIMIT)
        cx, cy = route[i]
        radius = PLAZA_RADIUS
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy <= radius * radius:
                    try_add((cx + dx, cy + dy), i)
    pockets = set()
    for region in regions:
        pockets |= region["cells"]
    return pockets


def noise_field(rng, cell):
    """Smooth seeded value noise in [0, 1) over the map."""
    gw, gh = COLS // cell + 2, ROWS // cell + 2
    lattice = [[rng.random() for _ in range(gw)] for _ in range(gh)]

    def sample(x, y):
        fx, fy = x / cell, y / cell
        x0, y0 = int(fx), int(fy)
        tx, ty = fx - x0, fy - y0
        sx = tx * tx * (3 - 2 * tx)
        sy = ty * ty * (3 - 2 * ty)
        v00 = lattice[y0][x0]
        v10 = lattice[y0][x0 + 1]
        v01 = lattice[y0 + 1][x0]
        v11 = lattice[y0 + 1][x0 + 1]
        return (v00 * (1 - sx) + v10 * sx) * (1 - sy) + (v01 * (1 - sx) + v11 * sx) * sy

    return sample


def paint(spec, route, rng):
    """Turn a route into a finished grid of terrain chars."""
    palette = PALETTES[spec["race"]]
    road = set(route)
    pockets = grow_pockets(route, rng)

    # wall the spawn and the base in: the only way in is along the road
    guards = set()
    for anchor, keep in ((route[0], route[1]), (route[-1], route[-2])):
        for n in NEIGH4:
            cell = (anchor[0] + n[0], anchor[1] + n[1])
            if in_bounds(*cell) and cell != keep:
                guards.add(cell)
    pockets -= guards

    ground = palette["ground"]
    accent = palette.get("accent")

    # scatter boulders / thickets through the pockets so they are not slabs
    clumps = set()
    for cell in sorted(pockets):
        if rng.random() < 0.05:
            clumps.add(cell)
            if rng.random() < 0.5:
                for n in NEIGH4:
                    side = (cell[0] + n[0], cell[1] + n[1])
                    if side in pockets and side not in guards:
                        clumps.add(side)
    pockets -= clumps

    coarse = noise_field(rng, 6)
    fine = noise_field(rng, 3)
    rows = []
    spawn = tuple(spec["start"])
    base = tuple(spec["base"])
    for y in range(ROWS):
        line = []
        for x in range(COLS):
            cell = (x, y)
            if cell == spawn:
                line.append(SPAWN)
            elif cell == base:
                line.append(BASE)
            elif cell in road:
                line.append(ROAD)
            elif cell in clumps:
                line.append(pick_weighted(rng, palette["pocket_clumps"], rng.random()))
            elif cell in pockets:
                if accent and rng.random() < accent[1]:
                    line.append(accent[0])
                else:
                    line.append(ground)
            else:
                v = 0.78 * coarse(x, y) + 0.22 * fine(x, y)
                if cell in guards:
                    v = max(v, 0.75)     # keep the wall around spawn/base visible
                line.append(pick_weighted(rng, palette["blockers"], v))
        rows.append("".join(line))
    return rows


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------
def bfs_path(grid, walkable):
    """The route the engine itself would find (same BFS order as engine.level)."""
    h, w = len(grid), len(grid[0])
    start = base = None
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch == SPAWN:
                start = (x, y)
            elif ch == BASE:
                base = (x, y)
    if start is None or base is None:
        return None, start, base
    prev = {start: None}
    queue = deque([start])
    while queue:
        cur = queue.popleft()
        if cur == base:
            break
        x, y = cur
        for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            nxt = (x + dx, y + dy)
            if nxt in prev or not (0 <= nxt[1] < h and 0 <= nxt[0] < w):
                continue
            if grid[nxt[1]][nxt[0]] in walkable:
                prev[nxt] = cur
                queue.append(nxt)
    if base not in prev:
        return None, start, base
    order = []
    node = base
    while node is not None:
        order.append(node)
        node = prev[node]
    order.reverse()
    return order, start, base


def validate_grid(grid, terrain, road_len, level_id):
    """Return stats, or raise ``AssertionError`` with the reason."""
    name = level_id
    assert grid, f"{name}: empty grid"
    width = len(grid[0])
    assert all(len(r) == width for r in grid), f"{name}: ragged rows"
    assert len(grid) == ROWS and width == COLS, f"{name}: expected {COLS}x{ROWS}"

    counts = {}
    for row in grid:
        for ch in row:
            counts[ch] = counts.get(ch, 0) + 1
    assert counts.get(SPAWN, 0) == 1, f"{name}: needs exactly one S"
    assert counts.get(BASE, 0) == 1, f"{name}: needs exactly one B"
    for ch in counts:
        if ch in (SPAWN, BASE):
            continue
        assert ch in terrain["chars"], f"{name}: unknown terrain char {ch!r}"

    path, start, base = bfs_path(grid, terrain["walkable"])
    assert path is not None, f"{name}: no walkable route from S to B"
    assert path[0] == start and path[-1] == base, f"{name}: route does not run S->B"
    assert start[0] < COLS and start[1] < ROWS and base[0] < COLS and base[1] < ROWS

    walkable_cells = sum(c for ch, c in counts.items()
                         if ch in terrain["walkable"])
    assert len(path) >= 0.25 * walkable_cells, (
        f"{name}: route {len(path)} cells is under 25% of {walkable_cells} walkable cells")
    assert len(path) >= 0.12 * COLS * ROWS, (
        f"{name}: route {len(path)} cells is too short for a {COLS}x{ROWS} map")
    assert len(path) >= PATH_RATIO_MIN * road_len, (
        f"{name}: enemy route {len(path)} loses too much of the {road_len}-cell road")

    # buildable ground within reach of the route (towers have ~2-4 tile range)
    near = set()
    for x, y in path:
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                cell = (x + dx, y + dy)
                if in_bounds(*cell):
                    near.add(cell)
    buildable = sum(1 for cell in near if grid[cell[1]][cell[0]] in terrain["buildable"])
    assert buildable >= BUILDABLE_NEAR_MIN, (
        f"{name}: only {buildable} buildable cells near the route")
    # the route starts on S and ends on B, so the grid holds two cells fewer
    assert counts.get(ROAD, 0) == road_len - 2, (
        f"{name}: {counts.get(ROAD, 0)} road cells, expected {road_len - 2}")

    return {
        "size": f"{width}x{len(grid)}",
        "path": len(path),
        "road": road_len,
        "walkable": walkable_cells,
        "buildable_total": sum(c for ch, c in counts.items() if ch in terrain["buildable"]),
        "buildable_near": buildable,
        "coverage": len(path) / max(1, walkable_cells),
    }


# ---------------------------------------------------------------------------
# build / write / verify
# ---------------------------------------------------------------------------
def build_grid(spec, terrain):
    """Build one grid, retrying deterministically if the route comes out tangled."""
    for attempt in range(40):
        rng = random.Random(MASTER_SEED * 1000 + spec["seed"] * 17 + attempt)
        route = build_route(spec, rng)
        if not route_is_simple(route):
            continue
        grid = paint(spec, route, rng)
        try:
            stats = validate_grid(grid, terrain, len(route), spec["level_id"])
        except AssertionError:
            continue
        stats["attempts"] = attempt + 1
        return grid, stats
    raise SystemExit(f"{spec['level_id']}: could not build a valid map after 40 tries")


def level_files():
    return sorted(LEVELS_DIR.glob("*.json"))


def build_all(terrain):
    by_id = {spec["level_id"]: spec for spec in LEVEL_SPECS}
    missing = [p.stem for p in level_files() if p.stem not in by_id]
    if missing:
        raise SystemExit(f"no spec for shipped level(s): {', '.join(missing)}")
    out = {}
    for spec in LEVEL_SPECS:
        _check_spec(spec)
        grid, stats = build_grid(spec, terrain)
        out[spec["level_id"]] = (grid, stats)
    return out


def write_levels(built, dry_run):
    for level_id, (grid, _stats) in built.items():
        path = LEVELS_DIR / f"{level_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("grid") == grid:
            print(f"  = {path.name}: grid already up to date")
            continue
        data["grid"] = grid
        text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        if dry_run:
            print(f"  ~ {path.name}: would rewrite grid ({len(grid)}x{len(grid[0])})")
        else:
            path.write_text(text, encoding="utf-8")
            print(f"  * {path.name}: grid -> {len(grid)}x{len(grid[0])}")


def verify_with_engine():
    """Load every level through the real loader in a headless subprocess."""
    code = r'''
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
sys.path.insert(0, str(root))
import pygame
pygame.display.init()
pygame.display.set_mode((64, 64))
from core.content import get_content
from engine.level import Level
content = get_content()
bad = 0
for path in sorted((root / "content" / "levels").glob("*.json")):
    data = json.loads(path.read_text(encoding="utf-8"))
    try:
        level = Level(data, content=content)
    except Exception as exc:
        print(f"    FAIL {path.name}: {exc}")
        bad += 1
        continue
    ok = (level.spawn_cell and level.base_cell and level.path_cells
          and level.path_cells[0] == level.spawn_cell
          and level.path_cells[-1] == level.base_cell)
    print(f"    engine ok  {path.name}: {level.cols}x{level.rows_n} "
          f"path={len(level.path_cells)} spawn={level.spawn_cell} "
          f"base={level.base_cell}")
    if not ok:
        bad += 1
print("ENGINE CHECK: " + ("FAIL" if bad else "OK"))
sys.exit(1 if bad else 0)
'''
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    proc = subprocess.run([sys.executable, "-c", code, str(ROOT)], env=env,
                          capture_output=True, text=True)
    out = (proc.stdout + proc.stderr).strip()
    for line in out.splitlines():
        if not line.startswith("pygame") and "Hello from" not in line:
            print(line)
    return proc.returncode == 0


def show(built):
    for level_id, (grid, _stats) in built.items():
        print(f"\n{level_id}")
        print("    " + "".join(str(x // 10 or " ") for x in range(COLS)))
        print("    " + "".join(str(x % 10) for x in range(COLS)))
        for y, row in enumerate(grid):
            print(f"{y:3d} {row}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="build and validate but do not touch the level files")
    ap.add_argument("--show", action="store_true", help="print the generated maps")
    ap.add_argument("--verify", action="store_true",
                    help="only re-validate and engine-load what is already on disk")
    args = ap.parse_args(argv)

    terrain = load_terrain()
    print(f"big_maps: target {COLS}x{ROWS} ({COLS * 64}x{ROWS * 64} px at 64px tiles), "
          f"master seed {MASTER_SEED}")

    if args.verify:
        built = {}
        for spec in LEVEL_SPECS:
            data = json.loads((LEVELS_DIR / f"{spec['level_id']}.json")
                              .read_text(encoding="utf-8"))
            grid = data["grid"]
            # the route runs from S to B, so it is two cells longer than the
            # road it is drawn from (validate_grid compares against the route)
            road = sum(row.count(ROAD) for row in grid)
            stats = validate_grid(grid, terrain, road + 2, spec["level_id"])
            built[spec["level_id"]] = (grid, stats)
    else:
        built = build_all(terrain)

    print(f"{'level':<20}{'size':>8}{'path':>7}{'road':>7}{'cover':>8}"
          f"{'buildable':>11}{'near path':>11}")
    ok = True
    for level_id, (_grid, stats) in built.items():
        print(f"{level_id:<20}{stats['size']:>8}{stats['path']:>7}{stats['road']:>7}"
              f"{stats['coverage'] * 100:>7.0f}%{stats['buildable_total']:>11}"
              f"{stats['buildable_near']:>11}")
    print("VALIDATION: OK (all 9 grids rectangular, single S/B, valid terrain, "
          "walkable S->B route, buildable ground along the route)")

    if args.show:
        show(built)

    if not args.verify:
        print("writing:")
        write_levels(built, args.dry_run)
        if args.dry_run:
            print("VALIDATION: OK (dry run, nothing written)")

    print("engine load check (SDL_VIDEODRIVER=dummy):")
    if not verify_with_engine():
        ok = False
    print("RESULT: " + ("OK" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

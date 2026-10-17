"""Level maps: terrain parsing, path waypoints, buildable queries, rendering.

A level is a dict (see ``core.content``) with a ``grid`` of one character per
tile.  ``S`` and ``B`` mark the spawn and the base; every other character maps
to a :class:`core.content.TerrainType` which says whether that cell is walkable
and/or buildable and which Kenney tiles to draw (plus an optional tint).

The route enemies follow is a breadth-first search from the spawn to the base
across walkable cells, so a designer is free to make branching maps -- the
shortest (deterministic) route wins.  Legacy ``maps/*.txt`` files are still
accepted through the level's ``map`` field.
"""
from collections import deque

import pygame

from core import paths
from core import settings as S
from engine import art

# --- Tile numbers from the Kenney "Tower Defense (Top-Down)" pack ----------
TILE_SPAWN = 133          # green disc used as the spawn portal
TILE_BASE = 180           # grey octagon pad under the base
TILE_BASE_TURRET = 226    # grey turret that marks the player base

SPAWN_CHAR = "S"
BASE_CHAR = "B"


class LevelError(ValueError):
    pass


class Level:
    def __init__(self, level_def, content=None):
        self.def_ = level_def or {}
        if content is None:
            from core.content import get_content
            content = get_content()
        self.content = content

        rows = self._grid_rows(level_def)
        if not rows:
            raise LevelError(f"{self.def_.get('id', '?')}: empty map")
        width = len(rows[0])
        if any(len(r) != width for r in rows):
            raise LevelError(f"{self.def_.get('id', '?')}: ragged rows")
        self.rows = rows
        self.cols = width
        self.rows_n = len(rows)

        self.grid = []          # grid[y][x] -> char
        self.spawn_cell = None
        self.base_cell = None
        self._parse()
        self.path_cells = self._find_path()
        self.waypoints = [self.cell_center(c) for c in self.path_cells]
        self.terrain = self._render_terrain()

    # ---------------------------------------------------------------- load
    def _grid_rows(self, level_def):
        grid = level_def.get("grid")
        if grid:
            return [str(row) for row in grid]
        name = level_def.get("map")
        if not name:
            return []
        path = paths.map_file(name)
        rows = []
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                rows.append(line)
        return rows

    def _parse(self):
        for y, row in enumerate(self.rows):
            grid_row = []
            for x, ch in enumerate(row):
                if ch == SPAWN_CHAR:
                    if self.spawn_cell is not None:
                        raise LevelError("multiple spawns")
                    self.spawn_cell = (x, y)
                elif ch == BASE_CHAR:
                    if self.base_cell is not None:
                        raise LevelError("multiple bases")
                    self.base_cell = (x, y)
                elif ch not in (SPAWN_CHAR, BASE_CHAR):
                    if self.content.terrain(ch) is None:
                        raise LevelError(
                            f"unknown terrain '{ch}' at {(x, y)}; add it to "
                            f"terrain.json (valid: "
                            f"{sorted(self.content.terrain_by_char)})")
                grid_row.append(ch)
            self.grid.append(grid_row)
        if self.spawn_cell is None or self.base_cell is None:
            raise LevelError("map needs one S and one B")

    def is_walkable_cell(self, cx, cy):
        ch = self.char_at(cx, cy)
        if ch in (SPAWN_CHAR, BASE_CHAR):
            return True
        terr = self.content.terrain(ch)
        return bool(terr and terr.walkable)

    def _find_path(self):
        start, goal = self.spawn_cell, self.base_cell
        if start == goal:
            return [start]
        prev = {start: None}
        queue = deque([start])
        while queue:
            cur = queue.popleft()
            if cur == goal:
                break
            x, y = cur
            for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
                nxt = (x + dx, y + dy)
                if nxt in prev or not self.in_bounds(*nxt):
                    continue
                if not self.is_walkable_cell(*nxt):
                    continue
                prev[nxt] = cur
                queue.append(nxt)
        if goal not in prev:
            raise LevelError("the base cannot be reached from the spawn over "
                             "walkable terrain")
        order = []
        node = goal
        while node is not None:
            order.append(node)
            node = prev[node]
        order.reverse()
        return order

    # ---------------------------------------------------------------- queries
    def in_bounds(self, cx, cy) -> bool:
        return 0 <= cx < self.cols and 0 <= cy < self.rows_n

    def char_at(self, cx, cy) -> str:
        if not self.in_bounds(cx, cy):
            return " "
        return self.grid[cy][cx]

    def is_buildable(self, cx, cy) -> bool:
        if not self.in_bounds(cx, cy):
            return False
        if (cx, cy) in (self.spawn_cell, self.base_cell):
            return False
        terr = self.content.terrain(self.grid[cy][cx])
        return bool(terr and terr.buildable)

    def cell_rect(self, cell) -> pygame.Rect:
        x, y = cell
        return pygame.Rect(x * S.TILE, y * S.TILE, S.TILE, S.TILE)

    def cell_center(self, cell):
        r = self.cell_rect(cell)
        return (r.centerx, r.centery)

    def cell_of(self, pos):
        return (int(pos[0]) // S.TILE, int(pos[1]) // S.TILE)

    @property
    def pixel_size(self):
        return (self.cols * S.TILE, self.rows_n * S.TILE)

    # ---------------------------------------------------------------- drawing
    def _effective_tint(self, terrain):
        return terrain.tint or self.def_.get("terrain_tint")

    def _render_terrain(self) -> pygame.Surface:
        surf = pygame.Surface(self.pixel_size).convert()
        # cache each terrain's resolved frame list (static frame 0 + optional
        # animated frames drawn later, at the tile positions, every frame)
        cache = {}
        self._anim_cells = []
        for y in range(self.rows_n):
            for x in range(self.cols):
                ch = self.grid[y][x]
                px, py = x * S.TILE, y * S.TILE
                terr = self.content.terrain(ch)
                if terr is None:
                    surf.blit(art.tile(157), (px, py))
                    continue
                tint = self._effective_tint(terr)
                key = (terr.id, None if tint is None else tuple(tint))
                if key not in cache:
                    cache[key] = art.sprite_frames(terr.base_spec, S.TILE, tint)
                frames = cache[key]
                surf.blit(frames[0], (px, py))
                self._track_anim(px, py, frames, terr.base_spec, 0.013, 0.017)

                ospec = terr.overlay_spec
                if ospec is not None:
                    okey = ("overlay", terr.id, None if tint is None else tuple(tint))
                    if okey not in cache:
                        cache[okey] = art.sprite_frames(ospec, S.TILE, tint)
                    oframes = cache[okey]
                    surf.blit(oframes[0], (px, py))
                    self._track_anim(px, py, oframes, ospec, 0.037, 0.029)
        # spawn / base pads
        sx, sy = self.spawn_cell
        surf.blit(art.tile(TILE_SPAWN), (sx * S.TILE, sy * S.TILE))
        bx, by = self.base_cell
        surf.blit(art.tile(TILE_BASE), (bx * S.TILE, by * S.TILE))
        return surf

    def _track_anim(self, px, py, frames, spec, ax, ay):
        if len(frames) > 1:
            offset = (px * ax + py * ay) % 1.0
            self._anim_cells.append((px, py, frames, art.fps(spec),
                                     art.loops(spec), offset))

    def draw(self, canvas):
        canvas.blit(self.terrain, (0, 0))
        if self._anim_cells:
            now = pygame.time.get_ticks() / 1000.0
            for px, py, frames, spec_fps, loop, offset in self._anim_cells:
                i = int((now + offset) * spec_fps)
                idx = i % len(frames) if loop else min(len(frames) - 1, i)
                canvas.blit(frames[idx], (px, py))
        cx, cy = self.cell_center(self.base_cell)
        if len(self.path_cells) >= 2:
            px, py = self.cell_center(self.path_cells[-2])
        else:
            px, py = cx, cy - 1
        angle = art.angle_between((cx, cy), (px, py))
        base_img = art.rot(art.tile(TILE_BASE_TURRET), angle)
        canvas.blit(base_img, base_img.get_rect(center=(cx, cy)))

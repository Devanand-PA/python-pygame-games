"""Level maps: parsing, path waypoints, buildable queries, terrain rendering.

Map files (maps/*.txt) use one character per tile:
    S spawn          B base           . path
    g grass (buildable)               r rock (blocked)
    t tree/bush (blocked)
The path must be a single connected line from S to B (no branches, no 2x2
blocks) -- a small validator below enforces that at load time.
"""
import pygame

from core import paths
from core import settings as S
from engine import art

# --- Tile numbers from the Kenney "Tower Defense (Top-Down)" pack ----------
# (assets/packs/kenney_tower-defense-top-down). The numbers were validated
# against the pack's tilesheet; see tools/contact_sheet.py for a labelled
# index of every tile.
TILE_GRASS = 157          # plain green field (buildable)
TILE_ROAD = 158           # solid brown road/path
TILE_ROCK = 136           # grey boulder (blocked)
TILE_DECOS = (130, 131, 132, 134)   # bushes / leafy plants (blocked)
TILE_SPAWN = 133          # green disc used as the spawn portal
TILE_BASE = 180           # grey octagon pad under the base
TILE_BASE_TURRET = 226    # grey turret that marks the player base


class LevelError(ValueError):
    pass


class Level:
    def __init__(self, filename: str):
        rows = self._read(filename)
        self.rows = rows
        self.cols = len(rows[0])
        self.rows_n = len(rows)
        if (self.cols, self.rows_n) != (S.MAP_COLS, S.MAP_ROWS):
            raise LevelError(
                f"{filename}: expected {S.MAP_COLS}x{S.MAP_ROWS}, got "
                f"{self.cols}x{self.rows_n}")

        self.grid = []          # grid[y][x] -> char
        self.spawn_cell = None
        self.base_cell = None
        self.path_cells = []    # ordered [(x, y), ...] from spawn to base
        self._parse()
        self._order_path()
        self.waypoints = [self.cell_center(c) for c in self.path_cells]
        self.terrain = self._render_terrain()

    # ---------------------------------------------------------------- load
    @staticmethod
    def _read(filename: str):
        path = paths.map_file(filename)
        rows = []
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                rows.append(line)
        if not rows:
            raise LevelError(f"{filename}: empty map")
        width = len(rows[0])
        if any(len(r) != width for r in rows):
            raise LevelError(f"{filename}: ragged rows")
        return rows

    def _parse(self):
        for y, row in enumerate(self.rows):
            grid_row = []
            for x, ch in enumerate(row):
                if ch == "S":
                    if self.spawn_cell is not None:
                        raise LevelError("multiple spawns")
                    self.spawn_cell = (x, y)
                elif ch == "B":
                    if self.base_cell is not None:
                        raise LevelError("multiple bases")
                    self.base_cell = (x, y)
                grid_row.append(ch)
            self.grid.append(grid_row)
        if self.spawn_cell is None or self.base_cell is None:
            raise LevelError("map needs one S and one B")

    def _order_path(self):
        cells = {(x, y)
                 for y in range(self.rows_n)
                 for x in range(self.cols)
                 if self.grid[y][x] in "SB."}
        # single-line validation
        for (x, y) in cells:
            deg = sum(((x + dx, y + dy) in cells)
                      for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            endpoint = (x, y) in (self.spawn_cell, self.base_cell)
            if (endpoint and deg != 1) or (not endpoint and deg != 2):
                raise LevelError(
                    f"path broken at {(x, y)} (degree {deg}); the path must be "
                    f"a single line from S to B with no branches or crossings")
        # walk from spawn
        order = [self.spawn_cell]
        seen = {self.spawn_cell}
        cur = self.spawn_cell
        while cur != self.base_cell:
            x, y = cur
            nxt = None
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                m = (x + dx, y + dy)
                if m in cells and m not in seen:
                    nxt = m
                    break
            if nxt is None:
                raise LevelError("path does not reach the base")
            order.append(nxt)
            seen.add(nxt)
            cur = nxt
        self.path_cells = order

    # ---------------------------------------------------------------- queries
    def in_bounds(self, cx, cy) -> bool:
        return 0 <= cx < self.cols and 0 <= cy < self.rows_n

    def char_at(self, cx, cy) -> str:
        if not self.in_bounds(cx, cy):
            return " "
        return self.grid[cy][cx]

    def is_buildable(self, cx, cy) -> bool:
        return self.char_at(cx, cy) == "g"

    def cell_rect(self, cell) -> pygame.Rect:
        x, y = cell
        return pygame.Rect(x * S.TILE, y * S.TILE, S.TILE, S.TILE)

    def cell_center(self, cell):
        r = self.cell_rect(cell)
        return (r.centerx, r.centery)

    def cell_of(self, pos):
        return (int(pos[0]) // S.TILE, int(pos[1]) // S.TILE)

    # ---------------------------------------------------------------- drawing
    def _render_terrain(self) -> pygame.Surface:
        surf = pygame.Surface((self.cols * S.TILE, self.rows_n * S.TILE))
        grass = art.tile(TILE_GRASS)
        road = art.tile(TILE_ROAD)
        rock = art.tile(TILE_ROCK)
        decos = [art.tile(n) for n in TILE_DECOS]
        for y in range(self.rows_n):
            for x in range(self.cols):
                ch = self.grid[y][x]
                px, py = x * S.TILE, y * S.TILE
                if ch in "SB.":
                    surf.blit(road, (px, py))
                else:
                    surf.blit(grass, (px, py))
                    if ch == "r":
                        surf.blit(rock, (px, py))
                    elif ch == "t":
                        deco = decos[(x * 7 + y * 13) % len(decos)]
                        surf.blit(deco, (px, py))
        # spawn / base pads
        sx, sy = self.spawn_cell
        surf.blit(art.tile(TILE_SPAWN), (sx * S.TILE, sy * S.TILE))
        bx, by = self.base_cell
        surf.blit(art.tile(TILE_BASE), (bx * S.TILE, by * S.TILE))
        return surf

    def draw(self, canvas):
        canvas.blit(self.terrain, (0, 0))
        # base turret marker on the base pad, aimed back along the path
        cx, cy = self.cell_center(self.base_cell)
        if len(self.path_cells) >= 2:
            px, py = self.cell_center(self.path_cells[-2])
        else:
            px, py = cx, cy - 1
        angle = art.angle_between((cx, cy), (px, py))
        base_img = art.rot(art.tile(TILE_BASE_TURRET), angle)
        canvas.blit(base_img, base_img.get_rect(center=(cx, cy)))

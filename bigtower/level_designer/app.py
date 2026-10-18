"""A standalone pygame app for authoring bigtower content (terrain, units,
races, levels) without touching Python or JSON by hand.

Run it with ``python designer.py`` from the bigtower directory.  It has five
tabs: **Terrain**, **Units**, **Races**, **Levels** and **Help**.  The Levels
tab paints the map, previews the spawn->base route, picks the shop and enemy
pool, and builds waves.  Everything saves back to the same ``content/`` JSON
the game reads (see ``core.content.ContentDB``).
"""
from collections import deque

import pygame

from core import paths
from core.content import ContentDB, UnitType
from level_designer import widgets as W

TAB_NAMES = ["Terrain", "Units", "Races", "Levels", "Help"]
TAB_W = 128
TAB_H = 40


# ---------------------------------------------------------------------------
# Small reusable list widget
# ---------------------------------------------------------------------------
class RowList:
    def __init__(self, rect, labels=None, row_h=24, index=0, on_select=None):
        self.rect = pygame.Rect(rect)
        self.labels = list(labels or [])
        self.row_h = row_h
        self.index = index
        self.scroll = 0
        self.on_select = on_select

    def set_labels(self, labels):
        self.labels = list(labels)
        if self.labels:
            self.index = max(0, min(self.index, len(self.labels) - 1))
        else:
            self.index = 0

    def row_at(self, pos):
        if not self.rect.collidepoint(pos):
            return None
        row = (pos[1] - (self.rect.y + 4)) // self.row_h
        idx = self.scroll + row
        if 0 <= idx < len(self.labels):
            return idx
        return None

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(
                getattr(event, "pos", (0, 0))):
            self.scroll = max(0, self.scroll - event.y)
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            idx = self.row_at(event.pos)
            if idx is not None:
                self.index = idx
                if self.on_select:
                    self.on_select(idx)
                return True
        return False

    def on_draw(self, screen, font):  # pragma: no cover - visual only
        pygame.draw.rect(screen, (14, 14, 20), self.rect, border_radius=4)
        pygame.draw.rect(screen, (90, 86, 120), self.rect, 2, border_radius=4)
        max_rows = max(1, (self.rect.height - 8) // self.row_h)
        for row in range(max_rows):
            idx = self.scroll + row
            if idx >= len(self.labels):
                break
            rect = pygame.Rect(self.rect.x + 4, self.rect.y + 4 + row * self.row_h,
                               self.rect.width - 8, self.row_h)
            color = (96, 120, 70) if idx == self.index else (42, 40, 60)
            pygame.draw.rect(screen, color, rect, border_radius=3)
            text = font.render(str(self.labels[idx]), True, (235, 235, 235))
            screen.blit(text, (rect.x + 6, rect.centery - text.get_height() // 2))


# ---------------------------------------------------------------------------
# Map editor (levels tab)
# ---------------------------------------------------------------------------
class MapEditor:
    def __init__(self, content, grid_rows=None, cell=20):
        self.content = content
        self.cell = cell
        self.rows = []
        self.path_ok = True
        self.rect = pygame.Rect(360, 120, cell * 20, cell * 10)
        self.load(grid_rows or [])

    def load(self, grid_rows):
        self.rows = [str(r) for r in grid_rows]
        self.recompute_path()

    @property
    def cols(self):
        return len(self.rows[0]) if self.rows else 0

    @property
    def rows_n(self):
        return len(self.rows)

    def grid_rows(self):
        return list(self.rows)

    def cell_of(self, pos):
        cx = (pos[0] - self.rect.x) // self.cell
        cy = (pos[1] - self.rect.y) // self.cell
        return int(cx), int(cy)

    def in_bounds(self, cx, cy):
        return 0 <= cx < self.cols and 0 <= cy < self.rows_n

    def char_at(self, cx, cy):
        if self.in_bounds(cx, cy):
            return self.rows[cy][cx]
        return " "

    def paint(self, cell, char):
        cx, cy = cell
        if not self.in_bounds(cx, cy):
            return
        row = list(self.rows[cy])
        row[cx] = char
        self.rows[cy] = "".join(row)
        self.recompute_path()

    def _walkable(self, char):
        if char in ("S", "B"):
            return True
        terr = self.content.terrain(char)
        return bool(terr and terr.walkable)

    def _find(self, char):
        for y in range(self.rows_n):
            x = self.rows[y].find(char)
            if x != -1:
                return (x, y)
        return None

    def recompute_path(self):
        self.path_ok = False
        start, goal = self._find("S"), self._find("B")
        if start is None or goal is None:
            return
        if start == goal:
            self.path_ok = True
            return
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
                if not self._walkable(self.char_at(*nxt)):
                    continue
                prev[nxt] = cur
                queue.append(nxt)
        self.path_ok = goal in prev

    def on_draw(self, screen):  # pragma: no cover - visual only
        palette = {}
        for y in range(self.rows_n):
            for x in range(self.cols):
                char = self.rows[y][x]
                terr = self.content.terrain(char)
                color = (120, 120, 120)
                if char == "S":
                    color = (90, 200, 90)
                elif char == "B":
                    color = (220, 120, 90)
                elif terr is not None:
                    spec = terr.base_spec
                    color = (110, 170, 90) if spec.get("tile") == 157 else (150, 120, 90)
                pygame.draw.rect(screen, color,
                                 (self.rect.x + x * self.cell,
                                  self.rect.y + y * self.cell,
                                  self.cell - 1, self.cell - 1))
        pygame.draw.rect(screen, (240, 240, 240), self.rect, 2)
        pygame.draw.rect(screen, (120, 220, 120) if self.path_ok else (240, 90, 90),
                         self.rect, 3)


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
class _Tab:
    name = ""

    def __init__(self, designer):
        self.designer = designer
        self.content = designer.content

    def handle_event(self, event):
        pass

    def on_draw(self, screen, font, big):  # pragma: no cover - visual only
        pass


class TerrainTab(_Tab):
    name = "Terrain"

    def __init__(self, designer):
        super().__init__(designer)
        self.items = [t.to_dict() for t in self.content.terrains.values()]
        self.list = RowList((30, 90, 260, 420),
                            [t.get("name", t.get("id", "?")) for t in self.items],
                            on_select=self._on_select)
        self.current = self.items[0] if self.items else None

    def _on_select(self, _index=None):
        if 0 <= self.list.index < len(self.items):
            self.current = self.items[self.list.index]

    def handle_event(self, event):
        self.list.handle_event(event)

    def new(self):
        data = {"id": "terrain", "name": "Terrain", "char": "x", "base": 157,
                "buildable": False, "walkable": False}
        self.items.append(data)
        self.list.set_labels([t.get("name", t.get("id", "?")) for t in self.items])
        self.list.index = len(self.items) - 1
        self._on_select()

    def save(self):
        self.content.save_terrain(self.items)

    def on_draw(self, screen, font, big):
        self.list.on_draw(screen, font)
        if self.current is None:
            return
        lines = ["id: {}".format(self.current.get("id")),
                 "char: {}".format(self.current.get("char")),
                 "base tile: {}".format(self.current.get("base")),
                 "buildable: {}".format(self.current.get("buildable")),
                 "walkable: {}".format(self.current.get("walkable"))]
        y = 100
        for line in lines:
            text = font.render(line, True, (230, 230, 230))
            screen.blit(text, (320, y))
            y += 26
        hint = font.render("Press S to save the terrain palette", True, (150, 150, 170))
        screen.blit(hint, (320, y + 16))


class UnitsTab(_Tab):
    name = "Units"

    def __init__(self, designer):
        super().__init__(designer)
        self.items = [u.to_dict() for u in self.content.units.values()]
        self.list = RowList((30, 90, 280, 440),
                            [u.get("id") for u in self.items],
                            on_select=self._on_select)
        self.current = self.items[0] if self.items else None

    def _on_select(self, _index=None):
        if 0 <= self.list.index < len(self.items):
            self.current = self.items[self.list.index]

    def _unique_id(self, base):
        ids = {u.get("id") for u in self.items} | set(self.content.units)
        candidate = base
        i = 1
        while candidate in ids:
            i += 1
            candidate = "{}_{}".format(base, i)
        return candidate

    def new(self):
        uid = self._unique_id("new_unit")
        data = {"id": uid, "name": uid, "side": "defender",
                "movement": "static", "attack": "none", "hp": 100, "cost": 50,
                "sprite": {"kind": "pack", "tile": 226}}
        self.items.append(data)
        self.list.set_labels([u.get("id") for u in self.items])
        self.list.index = len(self.items) - 1
        self.current = data
        return data

    def save(self):
        if self.current is None:
            return None
        saved = self.content.save_unit(UnitType(self.current))
        if saved.id not in [u.get("id") for u in self.items]:
            self.items.append(saved.to_dict())
        self.list.set_labels([u.get("id") for u in self.items])
        return saved

    def delete(self):
        if self.current is None:
            return
        uid = self.current.get("id")
        self.content.delete_unit(uid)
        if self.current in self.items:
            self.items.remove(self.current)
        self.list.set_labels([u.get("id") for u in self.items])
        self.current = None

    def handle_event(self, event):
        self.list.handle_event(event)

    def on_draw(self, screen, font, big):
        self.list.on_draw(screen, font)
        if self.current is None:
            return
        lines = ["id: {}".format(self.current.get("id")),
                 "side: {}".format(self.current.get("side")),
                 "movement: {}".format(self.current.get("movement")),
                 "attack: {}".format(self.current.get("attack")),
                 "hp: {}   cost: {}".format(self.current.get("hp"),
                                            self.current.get("cost"))]
        y = 100
        for line in lines:
            screen.blit(font.render(line, True, (230, 230, 230)), (330, y))
            y += 26
        screen.blit(font.render("N = new unit, S = save, Del = delete",
                                True, (150, 150, 170)), (330, y + 16))


class RacesTab(_Tab):
    name = "Races"

    def __init__(self, designer):
        super().__init__(designer)
        self.items = [dict(r) for r in self.content.races.values()]
        self.list = RowList((30, 90, 280, 440),
                            [r.get("name", r.get("id")) for r in self.items],
                            on_select=self._on_select)
        self.current = self.items[0] if self.items else None

    def _on_select(self, _index=None):
        if 0 <= self.list.index < len(self.items):
            self.current = self.items[self.list.index]

    def handle_event(self, event):
        self.list.handle_event(event)

    def on_draw(self, screen, font, big):
        self.list.on_draw(screen, font)
        if self.current is None:
            return
        lines = ["id: {}".format(self.current.get("id")),
                 "units: {}".format(", ".join(self.current.get("units") or [])),
                 "enemies: {}".format(", ".join(self.current.get("enemies") or [])),
                 "levels: {}".format(", ".join(self.current.get("levels") or []))]
        y = 100
        for line in lines:
            screen.blit(font.render(line, True, (230, 230, 230)), (330, y))
            y += 26


class LevelsTab(_Tab):
    name = "Levels"

    def __init__(self, designer):
        super().__init__(designer)
        self.items = [dict(lv) for lv in self.content.levels.values()]
        self.list = RowList((30, 90, 280, 440),
                            [lv.get("name", lv.get("id")) for lv in self.items],
                            on_select=self._on_select)
        self.current = self.items[0] if self.items else None
        self.map = MapEditor(self.content,
                             (self.current or {}).get("grid") or [])
        self.paint_char = "."
        self.wave_index = 0
        self.group_index = 0

    def _on_select(self, _index=None):
        if 0 <= self.list.index < len(self.items):
            self.current = self.items[self.list.index]
            self.map.load(self.current.get("grid") or [])

    def palette_rects(self):
        rects = []
        x = self.map.rect.x
        y = self.map.rect.bottom + 12
        for terr in self.content.terrains.values():
            rects.append((pygame.Rect(x, y, 26, 26), terr.char))
            x += 32
        return rects

    def add_wave(self):
        if self.current is None:
            return
        waves = self.current.setdefault("waves", [])
        waves.append([])
        self.wave_index = len(waves) - 1

    def add_group(self):
        if self.current is None:
            return
        waves = self.current.setdefault("waves", [])
        if not waves:
            waves.append([])
        unit_ids = list(self.content.units)
        default = unit_ids[0] if unit_ids else "runner"
        waves[-1].append([default, 3, 1.0])
        self.group_index = len(waves[-1]) - 1

    def _apply_group_fields(self):
        if self.current is None:
            return
        waves = self.current.get("waves") or []
        if not waves or not waves[-1]:
            return
        idx = min(self.group_index, len(waves[-1]) - 1)
        group = waves[-1][idx]
        group[1] = int(group[1])
        group[2] = float(group[2])

    def save(self):
        if self.current is None:
            return None
        self.current["grid"] = self.map.grid_rows()
        return self.content.save_level(self.current)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, char in self.palette_rects():
                if rect.collidepoint(event.pos):
                    self.paint_char = char
                    return
            if self.map.rect.collidepoint(event.pos):
                self.map.paint(self.map.cell_of(event.pos), self.paint_char)
                return
        self.list.handle_event(event)

    def on_draw(self, screen, font, big):  # pragma: no cover - visual only
        self.list.on_draw(screen, font)
        self.map.on_draw(screen)
        for rect, char in self.palette_rects():
            selected = char == self.paint_char
            pygame.draw.rect(screen, (96, 120, 70) if selected else (58, 54, 84),
                             rect, border_radius=4)
            terr = self.content.terrain(char)
            label = terr.name if terr else char
            text = font.render("{} {}".format(char, label), True, (230, 230, 230))
            screen.blit(text, (rect.right + 4, rect.y + 2))
        status = "route ok" if self.map.path_ok else "NO ROUTE S->B"
        screen.blit(font.render(status, True,
                                (120, 220, 120) if self.map.path_ok else (240, 90, 90)),
                    (self.map.rect.x, self.map.rect.y - 28))


class HelpTab(_Tab):
    name = "Help"

    def on_draw(self, screen, font, big):  # pragma: no cover - visual only
        lines = [
            "bigtower level designer",
            "",
            "Terrain  - edit the terrain palette.",
            "Units    - create / edit / delete units.",
            "Races    - campaigns: rosters + level order.",
            "Levels   - paint the map, pick shop + enemy pool, build waves.",
            "",
            "Everything saves to content/ as JSON the game reads.",
        ]
        y = 100
        for line in lines:
            screen.blit((big if line == lines[0] else font).render(
                line, True, (230, 230, 230)), (60, y))
            y += 34


# ---------------------------------------------------------------------------
# The app
# ---------------------------------------------------------------------------
class _TabButton:
    def __init__(self, name, rect):
        self.name = name
        self.rect = pygame.Rect(rect)


class Designer:
    def __init__(self, content=None):
        pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1200, 760))
        self.screen = pygame.display.get_surface()
        pygame.display.set_caption("Big Tower - Level Designer")
        self.font = pygame.font.Font(None, 22)
        self.big = pygame.font.Font(None, 30)
        self.clock = pygame.time.Clock()
        self.running = True

        self.content = content or ContentDB()
        self.ctx = W.Context(content=self.content, assets=paths.ASSETS_DIR)

        self.tabs = [
            ("Terrain", TerrainTab(self)),
            ("Units", UnitsTab(self)),
            ("Races", RacesTab(self)),
            ("Levels", LevelsTab(self)),
            ("Help", HelpTab(self)),
        ]
        self.tab_buttons = [
            _TabButton(name, (10 + i * (TAB_W + 6), 10, TAB_W, TAB_H))
            for i, (name, _tab) in enumerate(self.tabs)
        ]
        self.active = 0

        self.terrain_tab = self.tabs[0][1]
        self.units_tab = self.tabs[1][1]
        self.races_tab = self.tabs[2][1]
        self.levels_tab = self.tabs[3][1]
        self.help_tab = self.tabs[4][1]

    @property
    def tab(self):
        return self.tabs[self.active][1]

    def set_tab(self, index):
        self.active = max(0, min(len(self.tabs) - 1, int(index)))

    def set_active(self, index):
        self.set_tab(index)

    # -------------------------------------------------------------- events
    def _dispatch(self, event):
        if self.ctx.modal is not None:
            self.ctx.modal.handle_event(event)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for index, button in enumerate(self.tab_buttons):
                if button.rect.collidepoint(event.pos):
                    self.set_tab(index)
                    return
        if event.type == pygame.KEYDOWN:
            if self._key(event):
                return
        self.tab.handle_event(event)

    def _key(self, event):  # pragma: no cover - interactive convenience
        tab = self.tab
        if event.key == pygame.K_s and hasattr(tab, "save"):
            tab.save()
            return True
        if event.key == pygame.K_n and hasattr(tab, "new"):
            tab.new()
            return True
        if event.key == pygame.K_DELETE and hasattr(tab, "delete"):
            tab.delete()
            return True
        if pygame.K_1 <= event.key <= pygame.K_5:
            self.set_tab(event.key - pygame.K_1)
            return True
        return False

    # -------------------------------------------------------------- drawing
    def on_draw(self):  # pragma: no cover - visual only
        self.screen.fill((20, 20, 28))
        for index, button in enumerate(self.tab_buttons):
            color = (96, 120, 70) if index == self.active else (58, 54, 84)
            pygame.draw.rect(self.screen, color, button.rect, border_radius=6)
            pygame.draw.rect(self.screen, (90, 86, 120), button.rect, 2,
                             border_radius=6)
            label = self.font.render(button.name, True, (240, 240, 240))
            self.screen.blit(label, label.get_rect(center=button.rect.center))
        self.tab.on_draw(self.screen, self.font, self.big)
        if self.ctx.modal is not None:
            self.ctx.modal.on_draw(self.screen)
        pygame.display.flip()

    def run(self):  # pragma: no cover - interactive loop
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                else:
                    self._dispatch(event)
            self.on_draw()
            self.clock.tick(60)
        pygame.quit()


def main():  # pragma: no cover - entry point
    Designer().run()


if __name__ == "__main__":  # pragma: no cover
    main()

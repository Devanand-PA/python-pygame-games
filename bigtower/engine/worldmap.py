"""Overworld campaign map: every level as a place on a pannable, zoomable map.

The level list used to be a vertical stack of buttons (one per level).  This
module replaces that with a *map*: the campaign region is drawn once into an
offscreen surface (terrain, lakes, scenery, a road linking the levels, place
names) and the player explores it with a small camera --

* **pan**  -- drag with the mouse, WASD / arrow keys, or click the minimap
* **zoom** -- mouse wheel (towards the cursor), ``+`` / ``-``, ``F`` to fit
* **play** -- click a level marker, then Play (or Enter); ``Tab`` cycles
  markers, ``1``..``9`` jump straight to one, ``Esc`` steps back out

Each level is a *pin* on the map.  A pin is

* **cleared**  -- green, with a check badge (it sits in the player's saves)
* **unlocked** -- gold, gently pulsing: the next level to play
* **locked**   -- grey with a padlock: the level before it is not cleared

Where a pin sits comes from ``content/world/<race>.json``::

    {"id": "woodlanders", "name": "The Greenwood Vale", "size": [2560, 1440],
     "theme": "forest",
     "pins": [{"level": "woodlanders_01", "x": 0.14, "y": 0.80}, ...]}

``x``/``y`` are normalised (0..1) positions on the world surface.  A level
with no pin is laid out automatically on a gentle S-curve, so a race works
even without a world file.  The road through the pins follows the race's
level order and is tinted by progress: green where the destination is
cleared, gold for the next level, grey beyond it.

Everything is deterministic: the world for a race is generated from a seed
derived from its id, so the same campaign always looks the same.
"""
from __future__ import annotations

import math
import random

import pygame

from core import settings as S

# --- theme palettes ---------------------------------------------------------
# ``land`` holds the two endpoints of a noise-blended ground colour; ``growth``
# is what scenery clusters blend towards; the rest are flat colours.
THEMES = {
    "forest": {
        "land": ((92, 138, 74), (120, 162, 92)),
        "water": (52, 98, 140),
        "shore": (198, 192, 148),
        "growth": (44, 88, 50),
        "road": (72, 56, 38),
        "road_core": (208, 178, 114),
        "deco": ("tree", 0.75),
        "label": (58, 44, 28),
        "label_halo": (236, 230, 200),
        "places": ("Mosshollow", "Eldergrove", "Thornwood", "Fernbarrow",
                   "Willowmere", "Greenthicket", "Brackenmoor"),
    },
    "desert": {
        "land": ((206, 178, 126), (228, 204, 152)),
        "water": (44, 106, 150),
        "shore": (240, 226, 180),
        "growth": (148, 126, 96),
        "road": (94, 70, 44),
        "road_core": (222, 196, 138),
        "deco": ("cactus", 0.72),
        "label": (94, 66, 36),
        "label_halo": (248, 240, 210),
        "places": ("Dust Landing", "The Shallows", "Crater Flats",
                   "Hissing Dunes", "Saltbarrow", "Ash Basin"),
    },
    "foundry": {
        "land": ((70, 72, 84), (96, 98, 110)),
        "water": (150, 62, 34),
        "shore": (110, 84, 60),
        "growth": (46, 44, 52),
        "road": (40, 38, 46),
        "road_core": (150, 148, 150),
        "deco": ("rock", 0.75),
        "label": (222, 218, 230),
        "label_halo": (24, 24, 32),
        "places": ("Cold Foundry", "Rust Flats", "Scrapyard Delta",
                   "Ironworks Sprawl", "Slagmoor", "Core Reactor Nine"),
    },
}

STATE_CLEARED = "cleared"
STATE_UNLOCKED = "unlocked"
STATE_LOCKED = "locked"
STATE_COLORS = {
    STATE_CLEARED: (72, 186, 96),
    STATE_UNLOCKED: (255, 205, 66),
    STATE_LOCKED: (94, 94, 110),
}
STATE_TEXT = {
    STATE_CLEARED: "Cleared",
    STATE_UNLOCKED: "Ready to play",
    STATE_LOCKED: "Locked",
}
ROUTE_COLORS = {
    STATE_CLEARED: (108, 214, 128),
    STATE_UNLOCKED: (255, 216, 96),
    STATE_LOCKED: (128, 128, 140),
}

WORLD_DEFAULT_SIZE = (2560, 1440)
DRAG_THRESHOLD = 5         # px of movement before a press counts as a pan
ZOOM_STEP = 1.18           # wheel / button zoom factor per notch
ZOOM_MAX = 2.5
PAN_SPEED = 950.0          # screen px/second for keyboard panning
MINIMAP_W = S.MINIMAP_W
MINIMAP_H = S.MINIMAP_H
EASE = 12.0                # camera catch-up, higher = snappier
THUMB_W = 132              # battle-map thumbnail in the briefing panel
THUMB_H = 66


def _lerp(a, b, t):
    return a + (b - a) * t


def _mix(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return (int(_lerp(c1[0], c2[0], t) + 0.5),
            int(_lerp(c1[1], c2[1], t) + 0.5),
            int(_lerp(c1[2], c2[2], t) + 0.5))


def _hash_seed(text):
    """A stable seed for a race id (same campaign, same world, every run)."""
    value = 2166136261
    for ch in str(text):
        value = ((value ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return value


class _Noise:
    """Smooth seeded value noise sampled on a coarse lattice."""

    def __init__(self, seed, cell, world_w, world_h):
        self.rng = random.Random(seed)
        self.step = max(1, cell) * 32
        gw = world_w // self.step + 4
        gh = world_h // self.step + 4
        self.grid = [[self.rng.random() for _ in range(gw + 1)]
                     for _ in range(gh + 1)]

    def __call__(self, x, y):
        fx, fy = x / self.step, y / self.step
        x0, y0 = int(fx), int(fy)
        tx, ty = fx - x0, fy - y0
        sx = tx * tx * (3 - 2 * tx)
        sy = ty * ty * (3 - 2 * ty)
        g = self.grid
        v00, v10 = g[y0][x0], g[y0][x0 + 1]
        v01, v11 = g[y0 + 1][x0], g[y0 + 1][x0 + 1]
        return _lerp(v00, v10, sx) * (1 - sy) + _lerp(v01, v11, sx) * sy


def _dist_to_segments(px, py, segments):
    """Shortest distance from a point to a list of ``(a, b)`` segments."""
    best = float("inf")
    for (ax, ay), (bx, by) in segments:
        dx, dy = bx - ax, by - ay
        length2 = dx * dx + dy * dy
        if length2 <= 0:
            t = 0.0
        else:
            t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
        cx, cy = ax + t * dx, ay + t * dy
        d = math.hypot(px - cx, py - cy)
        if d < best:
            best = d
    return best


def _fit(text, font, max_w):
    """Truncate ``text`` with an ellipsis so it fits ``max_w``."""
    if max_w <= 0 or font.size(text)[0] <= max_w:
        return text
    while text and font.size(text + "...")[0] > max_w:
        text = text[:-1]
    return (text + "...") if text else ""


def _wrap(text, font, max_w):
    """Greedy word wrap for the info panel."""
    words = str(text).split()
    lines, current = [], ""
    for word in words:
        trial = (current + " " + word).strip()
        if font.size(trial)[0] <= max_w or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


class Pin:
    """One level's marker on the world map."""

    def __init__(self, level, index, pos, state):
        self.level = level
        self.index = index
        self.x, self.y = pos
        self.state = state

    @property
    def level_id(self):
        return self.level.get("id")

    @property
    def name(self):
        return self.level.get("name") or self.level_id or "Level"

    @property
    def description(self):
        return self.level.get("description") or ""


class WorldMap:
    """The pannable, zoomable campaign map for one race."""

    def __init__(self, game, race, content, completed, on_play=None,
                 on_back=None):
        self.game = game
        self.race = race or {}
        self.race_id = self.race.get("id") or "race"
        self.content = content
        self.completed = set(completed or ())
        self.on_play = on_play
        self.on_back = on_back

        spec = content.world(self.race_id) if content else None
        spec = spec if isinstance(spec, dict) else {}
        self.world_name = str(spec.get("name")
                              or "{} Wilds".format(self.race.get("name",
                                                                 self.race_id)))
        size = spec.get("size")
        if isinstance(size, (list, tuple)) and len(size) >= 2:
            self.world_w = max(320, int(size[0]))
            self.world_h = max(320, int(size[1]))
        else:
            self.world_w, self.world_h = WORLD_DEFAULT_SIZE
        self.theme = THEMES.get(str(spec.get("theme") or ""), THEMES["forest"])
        self.seed = _hash_seed(self.race_id)

        self.pins = self._make_pins(spec)

        # --- camera ---------------------------------------------------------
        self.zoom = self._fit_zoom()
        self.x = 0.0
        self.y = 0.0
        self._tx = 0.0
        self._ty = 0.0
        self.selected = None               # Pin whose info panel is open
        self.hover = None                  # Pin under the cursor
        self.mouse_pos = None
        self._drag = None                  # (world point, screen point, moved)
        self._minimap_drag = False
        self.time = 0.0
        self._scaled = None               # whole-region copy at one zoom level
        self._scaled_key = None
        self._thumb = None
        self._mm_thumb = None             # minimap-sized copy of the region
        self._mm_thumb_key = None
        self._thumb_cache = {}            # level id -> battle-map thumbnail
        self._font_cache = {}

        self.font_small = self._font(22)
        self.font_default = self._font(30)
        self.font_big = self._font(40)

        self._layout()
        self.background = self._render_background()
        self._thumb = pygame.transform.smoothscale(
            self.background, (max(1, self.world_w // 4),
                              max(1, self.world_h // 4)))
        self.fit_view()

    # ------------------------------------------------------------------ setup
    def _font(self, size):
        size = int(size)
        if size not in self._font_cache:
            self._font_cache[size] = pygame.font.Font(None, size)
        return self._font_cache[size]

    def _view_size(self):
        return self.game.canvas.get_size()

    def _fit_zoom(self):
        vw, vh = self._view_size()
        return max(0.05, min(vw / self.world_w, vh / self.world_h))

    def _make_pins(self, spec):
        """Levels in race order, each placed by the world file (or auto-laid)."""
        levels = self.content.race_levels(self.race) if self.content else []
        placed = {}
        raw_pins = spec.get("pins")
        if isinstance(raw_pins, list):
            for entry in raw_pins:
                if not isinstance(entry, dict):
                    continue
                try:
                    px, py = float(entry.get("x")), float(entry.get("y"))
                except (TypeError, ValueError):
                    continue
                placed[str(entry.get("level"))] = (max(0.0, min(1.0, px)),
                                                   max(0.0, min(1.0, py)))
        pins = []
        for index, level in enumerate(levels):
            lid = level.get("id")
            if lid in placed:
                fx, fy = placed[lid]
            else:
                # auto layout: a gentle S from the bottom-left to the top-right
                t = index / max(1, len(levels) - 1)
                fx = _lerp(0.16, 0.84, t)
                fy = 0.5 + 0.32 * math.sin(t * math.pi * 1.25)
            pins.append(Pin(level, index, (fx * self.world_w, fy * self.world_h),
                            self._state_for(index, levels)))
        return pins

    def _state_for(self, index, levels):
        lid = levels[index].get("id")
        if lid in self.completed:
            return STATE_CLEARED
        if index == 0:
            return STATE_UNLOCKED
        previous = levels[index - 1].get("id")
        return STATE_UNLOCKED if previous in self.completed else STATE_LOCKED

    # ------------------------------------------------------------- background
    def _render_background(self):
        """Paint the whole region once: terrain, lakes, scenery, road, names."""
        w, h = self.world_w, self.world_h
        theme = self.theme
        surf = pygame.Surface((w, h)).convert()
        rng = random.Random(self.seed)
        moisture = _Noise(self.seed + 11, 2, w, h)
        detail = _Noise(self.seed + 23, 1, w, h)
        growth = _Noise(self.seed + 37, 1, w, h)
        land_lo, land_hi = theme["land"]

        cell = 16
        for gy in range(0, h, cell):
            for gx in range(0, w, cell):
                m = moisture(gx, gy)
                if m > 0.615:
                    color = theme["water"]
                elif m > 0.575:
                    color = theme["shore"]
                else:
                    color = _mix(land_lo, land_hi, detail(gx, gy))
                    g = growth(gx, gy)
                    if g > 0.70:
                        color = _mix(color, theme["growth"],
                                     min(1.0, (g - 0.70) / 0.14))
                pygame.draw.rect(surf, color, (gx, gy, cell, cell))

        self._paint_road(surf)
        self._paint_pin_halos(surf)
        self._paint_scenery(surf, rng)
        self._paint_place_names(surf, rng)
        self._paint_frame(surf)
        return surf

    def _paint_road(self, surf):
        """The campaign road: a dark outline, a light core and a dashed centre."""
        points = [(p.x, p.y) for p in self.pins]
        if len(points) < 2:
            return
        theme = self.theme
        pygame.draw.lines(surf, theme["road"], False, points, 18)
        pygame.draw.lines(surf, theme["road_core"], False, points, 9)
        for px, py in points:               # round the joints
            pygame.draw.circle(surf, theme["road"], (int(px), int(py)), 10)
            pygame.draw.circle(surf, theme["road_core"], (int(px), int(py)), 5)
        dash = (250, 244, 214)
        for a, b in zip(points, points[1:]):
            length = math.hypot(b[0] - a[0], b[1] - a[1])
            if length < 1:
                continue
            steps = max(1, int(length // 26))
            for i in range(0, steps, 2):
                t0, t1 = i / steps, min(1.0, (i + 1) / steps)
                pygame.draw.line(surf, dash,
                                 (_lerp(a[0], b[0], t0), _lerp(a[1], b[1], t0)),
                                 (_lerp(a[0], b[0], t1), _lerp(a[1], b[1], t1)), 3)

    def _paint_pin_halos(self, surf):
        """A soft pale spot under every marker so pins read on any terrain."""
        halo = pygame.Surface((72, 72), pygame.SRCALPHA)
        pygame.draw.circle(halo, (255, 250, 235, 70), (36, 36), 34)
        pygame.draw.circle(halo, (30, 26, 20, 110), (36, 36), 34, 4)
        for pin in self.pins:
            surf.blit(halo, (int(pin.x) - 36, int(pin.y) - 36))

    def _paint_scenery(self, surf, rng):
        """Trees / cacti / rocks scattered over the scenery clusters."""
        deco_kind = self.theme["deco"][0]
        threshold = self.theme["deco"][1]
        growth = _Noise(self.seed + 53, 1, self.world_w, self.world_h)
        if len(self.pins) < 2:
            return
        segments = [((a.x, a.y), (b.x, b.y))
                    for a, b in zip(self.pins, self.pins[1:])]
        step = 48
        for gy in range(90, self.world_h - 90, step):
            for gx in range(70, self.world_w - 70, step):
                if growth(gx, gy) < threshold or rng.random() < 0.35:
                    continue
                jx, jy = gx + rng.randint(-14, 14), gy + rng.randint(-14, 14)
                if _dist_to_segments(jx, jy, segments) < 34:
                    continue
                if any(math.hypot(jx - p.x, jy - p.y) < 78 for p in self.pins):
                    continue
                self._draw_deco(surf, rng, jx, jy, deco_kind)

    def _draw_deco(self, surf, rng, x, y, kind):
        if kind == "tree":
            pygame.draw.ellipse(surf, (26, 46, 26),
                                (x - 11, y - 4, 22, 16))
            pygame.draw.rect(surf, (92, 66, 40), (x - 2, y - 2, 4, 12))
            r = rng.randint(9, 13)
            pygame.draw.circle(surf, (40, 84, 46), (x, y - 6), r)
            pygame.draw.circle(surf, (58, 108, 58),
                               (x - r // 3, y - 6 - r // 3), r // 2)
        elif kind == "cactus":
            dark, green = (52, 96, 58), (74, 130, 78)
            pygame.draw.rect(surf, dark, (x - 4, y - 11, 8, 22),
                             border_radius=4)
            pygame.draw.rect(surf, green, (x - 9, y - 15, 5, 10),
                             border_radius=3)
            pygame.draw.rect(surf, green, (x + 4, y - 11, 5, 9),
                             border_radius=3)
        else:                                   # rock / scrap pile
            r = rng.randint(9, 15)
            pts = []
            for i in range(7):
                ang = i / 7 * math.pi * 2
                rad = r * rng.uniform(0.72, 1.0)
                pts.append((x + rad * math.cos(ang),
                            y - 4 + rad * math.sin(ang)))
            pygame.draw.polygon(surf, (70, 68, 76), pts)
            pygame.draw.polygon(surf, (108, 106, 112),
                                [(px - 2, py - 3) for px, py in pts])

    def _paint_place_names(self, surf, rng):
        """Hand-drawn place labels, kept clear of the road and the pins."""
        names = list(self.theme["places"])
        rng.shuffle(names)
        segments = [((a.x, a.y), (b.x, b.y))
                    for a, b in zip(self.pins, self.pins[1:])]
        font = self._font(34)
        for name in names[:4]:
            label = font.render(name, True, self.theme["label"])
            halo = font.render(name, True, self.theme["label_halo"])
            for _ in range(240):
                x = rng.randint(150, self.world_w - 150)
                y = rng.randint(150, self.world_h - 150)
                if any(math.hypot(x - p.x, y - p.y) < 210 for p in self.pins):
                    continue
                if _dist_to_segments(x, y, segments) < 150:
                    continue
                rect = label.get_rect(center=(x, y))
                for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2),
                               (-2, -2), (2, 2), (-2, 2), (2, -2)):
                    surf.blit(halo, rect.move(dx, dy))
                surf.blit(label, rect)
                break

    def _paint_frame(self, surf):
        """A map-sheet border so the region reads as one drawn chart."""
        w, h = self.world_w, self.world_h
        pygame.draw.rect(surf, (28, 24, 18), (0, 0, w, h), 10)
        pygame.draw.rect(surf, (214, 200, 160), (12, 12, w - 24, h - 24), 2)

    # ---------------------------------------------------------------- camera
    def _clamp_axis(self, value, world, view):
        if world <= view:
            return (world - view) / 2.0
        return max(0.0, min(value, world - view))

    def clamp(self):
        vw, vh = self._view_size()
        self.x = self._clamp_axis(self.x, self.world_w, vw / self.zoom)
        self.y = self._clamp_axis(self.y, self.world_h, vh / self.zoom)

    def clamp_target(self):
        vw, vh = self._view_size()
        self._tx = self._clamp_axis(self._tx, self.world_w, vw / self.zoom)
        self._ty = self._clamp_axis(self._ty, self.world_h, vh / self.zoom)

    def scroll_to(self, x, y):
        self._tx, self._ty = float(x), float(y)
        self.clamp_target()
        self.x, self.y = self._tx, self._ty

    def snap(self):
        self.clamp_target()
        self.x, self.y = self._tx, self._ty

    def pan_by(self, dx, dy):
        self._tx += dx
        self._ty += dy
        self.clamp_target()

    def center_on(self, world_pos):
        vw, vh = self._view_size()
        self.pan_by(world_pos[0] - (self._tx + vw / 2.0 / self.zoom),
                    world_pos[1] - (self._ty + vh / 2.0 / self.zoom))
        self.snap()

    def zoom_by(self, factor, screen_pos=None):
        zoom = max(self._fit_zoom(), min(ZOOM_MAX, self.zoom * factor))
        if abs(zoom - self.zoom) < 1e-6:
            return
        if screen_pos is None:
            vw, vh = self._view_size()
            screen_pos = (vw // 2, vh // 2)
        wx = self.x + screen_pos[0] / self.zoom
        wy = self.y + screen_pos[1] / self.zoom
        self.zoom = zoom
        self.scroll_to(wx - screen_pos[0] / zoom, wy - screen_pos[1] / zoom)

    def fit_view(self):
        """Zoom out to the whole region, centred on the campaign itself."""
        self.zoom = self._fit_zoom()
        if self.pins:
            cx = sum(p.x for p in self.pins) / len(self.pins)
            cy = sum(p.y for p in self.pins) / len(self.pins)
        else:
            cx, cy = self.world_w / 2.0, self.world_h / 2.0
        vw, vh = self._view_size()
        self.scroll_to(cx - vw / 2.0 / self.zoom, cy - vh / 2.0 / self.zoom)

    def update(self, dt):
        self.time += dt
        if dt <= 0:
            return
        k = min(1.0, EASE * dt)
        self.x += (self._tx - self.x) * k
        self.y += (self._ty - self.y) * k
        if abs(self._tx - self.x) < 0.04:
            self.x = self._tx
        if abs(self._ty - self.y) < 0.04:
            self.y = self._ty

    # ----------------------------------------------------------- conversions
    def world_to_screen(self, pos):
        return ((pos[0] - self.x) * self.zoom, (pos[1] - self.y) * self.zoom)

    def screen_to_world(self, pos):
        return (self.x + pos[0] / self.zoom, self.y + pos[1] / self.zoom)

    def visible_world_rect(self):
        vw, vh = self._view_size()
        return pygame.Rect(self.x, self.y, vw / self.zoom, vh / self.zoom)

    def pin_radius(self):
        return max(13.0, min(44.0, 19.0 * self.zoom))

    def pin_screen_pos(self, pin):
        return self.world_to_screen((pin.x, pin.y))

    def hit_pin(self, pos):
        best, best_d = None, None
        r = self.pin_radius() + 8
        for pin in self.pins:
            sx, sy = self.pin_screen_pos(pin)
            d = math.hypot(pos[0] - sx, pos[1] - sy)
            if d <= r and (best_d is None or d < best_d):
                best, best_d = pin, d
        return best

    # ------------------------------------------------------------------ input
    def handle_keypress(self):
        """Held keys pan the map (called every frame by the game loop)."""
        if not pygame.key.get_focused():
            return
        dt = self.game.delta_time
        if dt <= 0:
            return
        keys = pygame.key.get_pressed()
        dx = (1 if keys[pygame.K_d] or keys[pygame.K_RIGHT] else 0) - \
             (1 if keys[pygame.K_a] or keys[pygame.K_LEFT] else 0)
        dy = (1 if keys[pygame.K_s] or keys[pygame.K_DOWN] else 0) - \
             (1 if keys[pygame.K_w] or keys[pygame.K_UP] else 0)
        if dx or dy:
            norm = (dx * dx + dy * dy) ** 0.5
            self.pan_by(dx / norm * PAN_SPEED * dt / self.zoom,
                        dy / norm * PAN_SPEED * dt / self.zoom)
            self.snap()

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.mouse_pos = event.pos
            self.hover = self.hit_pin(event.pos)
            self._mark_drag(event.pos)
            if self._drag is not None and self._drag[2]:
                grab_world, grab_screen, _moved = self._drag
                self.scroll_to(
                    grab_world[0] - (event.pos[0] - grab_screen[0]) / self.zoom,
                    grab_world[1] - (event.pos[1] - grab_screen[1]) / self.zoom)
            elif self._minimap_drag:
                self._minimap_jump(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._drag = (self.screen_to_world(event.pos), event.pos, False)
            if self.minimap_rect.collidepoint(event.pos):
                self._minimap_drag = True
                self._minimap_jump(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                dragged = bool(self._drag and self._drag[2])
                self._drag = None
                self._minimap_drag = False
                if not dragged:
                    self._click(event.pos)
            elif event.button == 3 and self.selected is not None:
                self.selected = None
        elif event.type == pygame.MOUSEWHEEL:
            self.zoom_by(ZOOM_STEP ** event.y, getattr(event, "pos", None))
        elif event.type == pygame.KEYDOWN:
            self._key(event)

    def _mark_drag(self, pos):
        """Record that the press has turned into a pan (called on motion)."""
        if self._drag is not None and not self._drag[2]:
            sx, sy = self._drag[1]
            if math.hypot(pos[0] - sx, pos[1] - sy) >= DRAG_THRESHOLD:
                self._drag = (self._drag[0], self._drag[1], True)

    def _key(self, event):
        key = event.key
        if key == pygame.K_ESCAPE:
            if self.selected is not None:
                self.selected = None
            elif self.on_back is not None:
                self.on_back()
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self.selected is not None and self.selected.state != STATE_LOCKED:
                self._play(self.selected)
        elif key == pygame.K_TAB:
            shift = bool(getattr(event, "mod", 0) & pygame.KMOD_SHIFT)
            self._cycle(-1 if shift else 1)
        elif key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self.zoom_by(ZOOM_STEP)
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.zoom_by(1.0 / ZOOM_STEP)
        elif key in (pygame.K_f, pygame.K_HOME):
            self.fit_view()
        elif pygame.K_1 <= key <= pygame.K_9:
            index = key - pygame.K_1
            if index < len(self.pins):
                self._select(self.pins[index], recenter=True)

    def _cycle(self, step):
        if not self.pins:
            return
        try:
            index = self.pins.index(self.selected)
        except ValueError:
            index = -1
        index = (index + step) % len(self.pins)
        self._select(self.pins[index], recenter=True)

    def _click(self, pos):
        """Resolve a left click that was not a map drag."""
        if self.back_rect.collidepoint(pos):
            self.game.play("click", 0.4)
            if self.on_back is not None:
                self.on_back()
            return
        for rect, factor in ((self.zoom_in_rect, ZOOM_STEP),
                             (self.zoom_out_rect, 1.0 / ZOOM_STEP)):
            if rect.collidepoint(pos):
                self.game.play("click", 0.4)
                self.zoom_by(factor, rect.center)
                return
        if self.fit_rect.collidepoint(pos):
            self.game.play("click", 0.4)
            self.fit_view()
            return
        pin = self.hit_pin(pos)
        if pin is not None:
            self._select(pin, recenter=False)
            self.game.play("click", 0.4)
            return
        if self.selected is not None:
            if self.play_rect.collidepoint(pos):
                if self.selected.state != STATE_LOCKED:
                    self.game.play("click", 0.4)
                    self._play(self.selected)
                else:
                    self.game.play("error", 0.4)
                return
            if self.close_rect.collidepoint(pos):
                self.game.play("click", 0.4)
                self.selected = None
                return
        self.selected = None

    def _select(self, pin, recenter=False):
        self.selected = pin
        if recenter:
            self.center_on((pin.x, pin.y))

    def _play(self, pin):
        if pin.state == STATE_LOCKED:
            self.game.play("error", 0.4)
            return
        if self.on_play is not None:
            self.on_play(pin.level_id)

    def _minimap_jump(self, pos):
        """Centre the view on the world point clicked inside the minimap."""
        box = self.minimap_rect
        if not box.collidepoint(pos):
            return
        fx = (pos[0] - box.x) / box.width
        fy = (pos[1] - box.y) / box.height
        self.center_on((fx * self.world_w, fy * self.world_h))

    # ---------------------------------------------------------------- drawing
    def _layout(self):
        """Screen rects for the chrome; recomputed whenever the map is drawn."""
        cw, ch = self._view_size()
        self.back_rect = pygame.Rect(16, 14, 96, 38)
        self.zoom_in_rect = pygame.Rect(cw - 52, ch // 2 - 60, 36, 36)
        self.zoom_out_rect = pygame.Rect(cw - 52, ch // 2 - 18, 36, 36)
        self.fit_rect = pygame.Rect(cw - 52, ch // 2 + 24, 36, 36)
        self.minimap_rect = pygame.Rect(cw - MINIMAP_W - 14, ch - MINIMAP_H - 14,
                                        MINIMAP_W, MINIMAP_H)
        self.compass_rect = pygame.Rect(14, ch - 86, 64, 64)
        self.header_rect = pygame.Rect(0, 0, cw, 64)
        self.panel_rect = pygame.Rect(0, 0, 470, 172)
        self.panel_rect.centerx = cw // 2
        self.panel_rect.bottom = ch - 96
        self.play_rect = pygame.Rect(self.panel_rect.right - 158,
                                     self.panel_rect.bottom - 52, 140, 40)
        self.close_rect = pygame.Rect(self.panel_rect.x + 18,
                                      self.panel_rect.bottom - 52, 116, 40)

    def draw(self, canvas):
        self._layout()
        canvas.fill((14, 14, 20))
        self._draw_background(canvas)
        self._draw_progress_routes(canvas)
        self._draw_pins(canvas)
        self._draw_header(canvas)
        self._draw_zoom_buttons(canvas)
        self._draw_compass(canvas)
        self._draw_minimap(canvas)
        self._draw_hint(canvas)
        if self.selected is not None:
            self._draw_panel(canvas)

    def _draw_background(self, canvas):
        """Blit the region, scaled by the zoom.

        Panning must stay smooth, and a fresh ``smoothscale`` of a large source
        every frame is not (the dummy-driver benchmark put it near 5 ms).  So
        the whole region is scaled **once per zoom level** into a cached
        surface and panning becomes a plain clipped blit; the per-frame
        crop-and-scale path is only used when zoomed in, where the visible
        slice is small enough to scale cheaply.
        """
        if self.zoom <= 1.25:
            key = round(self.zoom, 4)
            if self._scaled_key != key or self._scaled is None:
                self._scaled = pygame.transform.smoothscale(
                    self.background,
                    (max(1, round(self.world_w * self.zoom)),
                     max(1, round(self.world_h * self.zoom))))
                self._scaled_key = key
            canvas.blit(self._scaled, (round(-self.x * self.zoom),
                                       round(-self.y * self.zoom)))
            return
        vis = self.visible_world_rect()
        left = max(0, int(math.floor(vis.x)))
        top = max(0, int(math.floor(vis.y)))
        right = min(self.background.get_width(), int(math.ceil(vis.right)))
        bottom = min(self.background.get_height(), int(math.ceil(vis.bottom)))
        if right <= left or bottom <= top:
            return
        clip = pygame.Rect(left, top, right - left, bottom - top)
        canvas.blit(pygame.transform.smoothscale(
            self.background.subsurface(clip),
            (max(1, round(clip.width * self.zoom)),
             max(1, round(clip.height * self.zoom)))),
            (round((clip.x - self.x) * self.zoom),
             round((clip.y - self.y) * self.zoom)))

    def _draw_progress_routes(self, canvas):
        """Tint each leg of the road by whether its destination is open."""
        for a, b in zip(self.pins, self.pins[1:]):
            color = ROUTE_COLORS[b.state]
            ax, ay = self.world_to_screen((a.x, a.y))
            bx, by = self.world_to_screen((b.x, b.y))
            width = max(3, int(round(7 * self.zoom)))
            pygame.draw.line(canvas, color, (int(ax), int(ay)),
                             (int(bx), int(by)), width)
            pygame.draw.circle(canvas, color, (int(bx), int(by)), width)

    def _draw_pins(self, canvas):
        r = self.pin_radius()
        label_font = self._font(max(18, min(30, int(24 * self.zoom))))
        for pin in self.pins:
            sx, sy = self.pin_screen_pos(pin)
            sx, sy = int(round(sx)), int(round(sy))
            color = STATE_COLORS[pin.state]
            pygame.draw.circle(canvas, (18, 16, 24), (sx + 2, sy + 3),
                               int(r) + 2)
            pygame.draw.circle(canvas, color, (sx, sy), int(r))
            border = (250, 250, 240) if pin.state != STATE_LOCKED else (40, 40, 50)
            pygame.draw.circle(canvas, border, (sx, sy), int(r),
                               max(2, int(r * 0.14)))
            if pin.state == STATE_UNLOCKED and pin is not self.selected:
                pulse = int(r + 5 + 3 * math.sin(self.time * 4.0))
                pygame.draw.circle(canvas, (255, 240, 180), (sx, sy), pulse,
                                   max(2, int(r * 0.1)))
            if pin is self.selected:
                pygame.draw.circle(canvas, (255, 255, 255), (sx, sy),
                                   int(r + 8), 3)
            self._draw_pin_glyph(canvas, pin, sx, sy, r)
            if pin is self.hover or pin is self.selected:
                name = _fit(pin.name, label_font, 280)
                label = label_font.render(name, True, (246, 246, 236))
                rect = label.get_rect(midbottom=(sx, sy - int(r) - 12))
                backing = rect.inflate(14, 6)
                pygame.draw.rect(canvas, (16, 14, 24), backing, border_radius=5)
                pygame.draw.rect(canvas, color, backing, 2, border_radius=5)
                canvas.blit(label, rect)

    def _draw_pin_glyph(self, canvas, pin, sx, sy, r):
        """The pin's centre: its order number, plus a check or a padlock."""
        if pin.state == STATE_LOCKED:
            lock_r = max(4, int(r * 0.42))
            arc = pygame.Rect(sx - lock_r, int(sy - lock_r * 1.9),
                              2 * lock_r, 2 * lock_r)
            pygame.draw.arc(canvas, (226, 226, 236), arc, math.pi, 2 * math.pi,
                            max(2, int(lock_r * 0.45)))
            body = pygame.Rect(int(sx - lock_r * 1.15), int(sy - lock_r * 0.4),
                               int(lock_r * 2.3), int(lock_r * 1.9))
            pygame.draw.rect(canvas, (214, 214, 226), body, border_radius=3)
            pygame.draw.circle(canvas, (60, 60, 70),
                               (sx, int(sy + lock_r * 0.5)),
                               max(1, int(lock_r * 0.28)))
            return
        number_font = self._font(max(14, int(r * 1.15)))
        ink = (32, 28, 20) if pin.state == STATE_UNLOCKED else (250, 250, 245)
        label = number_font.render(str(pin.index + 1), True, ink)
        canvas.blit(label, label.get_rect(center=(sx, sy)))
        if pin.state == STATE_CLEARED:
            # check badge in the pin's top-right corner
            bx, by = sx + r * 0.66, sy - r * 0.66
            br = max(4, int(r * 0.42))
            pygame.draw.circle(canvas, (250, 250, 245), (int(bx), int(by)), br)
            pygame.draw.circle(canvas, (30, 120, 60), (int(bx), int(by)), br, 2)
            pygame.draw.lines(canvas, (30, 120, 60), False,
                              [(bx - br * 0.5, by),
                               (bx - br * 0.1, by + br * 0.42),
                               (bx + br * 0.55, by - br * 0.4)], 2)

    # ------------------------------------------------------------- chrome bits
    def _draw_header(self, canvas):
        canvas.fill((18, 18, 28), self.header_rect)
        pygame.draw.line(canvas, S.HUD_LINE,
                         (0, self.header_rect.bottom - 1),
                         (self.header_rect.right, self.header_rect.bottom - 1), 2)
        self._draw_button(canvas, self.back_rect, "Back",
                          hover=self._hovered(self.back_rect))
        title = self.font_default.render(self.race.get("name", self.race_id),
                                         True, (246, 246, 236))
        canvas.blit(title, (self.back_rect.right + 16, 10))
        cleared = sum(1 for p in self.pins if p.state == STATE_CLEARED)
        progress = "{} / {} cleared".format(cleared, len(self.pins))
        subtitle = "{}  \u00b7  {}".format(self.world_name, progress)
        canvas.blit(self.font_small.render(subtitle, True, (206, 206, 216)),
                    (self.back_rect.right + 18, 38))

    def _draw_button(self, canvas, rect, text, hover=False, font=None):
        font = font or self.font_default
        bg = (74, 70, 102) if hover else (52, 50, 74)
        pygame.draw.rect(canvas, bg, rect, border_radius=6)
        pygame.draw.rect(canvas, S.PANEL_EDGE, rect, 2, border_radius=6)
        label = font.render(text, True, (238, 238, 226))
        canvas.blit(label, label.get_rect(center=rect.center))

    def _hovered(self, rect):
        return self.mouse_pos is not None and rect.collidepoint(self.mouse_pos)

    def _draw_zoom_buttons(self, canvas):
        for rect, symbol in ((self.zoom_in_rect, "+"),
                             (self.zoom_out_rect, "\u2212"),
                             (self.fit_rect, "\u26f6")):
            self._draw_button(canvas, rect, symbol,
                              hover=self._hovered(rect), font=self.font_big)

    def _draw_compass(self, canvas):
        rect = self.compass_rect
        cx, cy = rect.center
        pygame.draw.circle(canvas, (20, 18, 30), rect.center, 30)
        pygame.draw.circle(canvas, S.PANEL_EDGE, rect.center, 30, 2)
        pygame.draw.polygon(canvas, (232, 90, 80),
                            [(cx, cy - 24), (cx - 7, cy + 6), (cx + 7, cy + 6)])
        pygame.draw.polygon(canvas, (226, 226, 236),
                            [(cx, cy + 24), (cx - 7, cy - 6), (cx + 7, cy - 6)])
        label = self.font_small.render("N", True, (238, 238, 226))
        canvas.blit(label, label.get_rect(midtop=(cx, rect.top + 2)))

    def _draw_minimap(self, canvas):
        box = self.minimap_rect
        pygame.draw.rect(canvas, (12, 12, 20), box, border_radius=6)
        inner = (box.width - 6, box.height - 6)
        if self._mm_thumb is None or self._mm_thumb_key != inner:
            self._mm_thumb = pygame.transform.smoothscale(self._thumb, inner)
            self._mm_thumb_key = inner
        canvas.blit(self._mm_thumb, (box.x + 3, box.y + 3))
        pygame.draw.rect(canvas, S.PANEL_EDGE, box, 2, border_radius=6)
        ox, oy = box.x + 3, box.y + 3
        tw, th = inner
        for pin in self.pins:
            px = ox + pin.x / self.world_w * tw
            py = oy + pin.y / self.world_h * th
            pygame.draw.circle(canvas, STATE_COLORS[pin.state],
                               (int(px), int(py)), 3)
        vis = self.visible_world_rect()
        vx = ox + vis.x / self.world_w * tw
        vy = oy + vis.y / self.world_h * th
        vw = max(4, vis.width / self.world_w * tw)
        vh = max(4, vis.height / self.world_h * th)
        pygame.draw.rect(canvas, (250, 250, 255),
                         pygame.Rect(int(vx), int(vy), int(vw), int(vh)), 1,
                         border_radius=2)

    def _draw_hint(self, canvas):
        lines = ["Drag or WASD to pan \u00b7 scroll to zoom \u00b7 F to fit",
                 "Click a marker to inspect it \u00b7 Enter to play \u00b7 Esc to go back"]
        y = self._view_size()[1] - 54
        for line in lines:
            canvas.blit(self.font_small.render(line, True, (178, 178, 196)),
                        (self.compass_rect.right + 16, y))
            y += 24

    def _draw_panel(self, canvas):
        pin = self.selected
        rect = self.panel_rect
        pygame.draw.rect(canvas, (16, 14, 26), rect, border_radius=10)
        pygame.draw.rect(canvas, STATE_COLORS[pin.state], rect, 3,
                         border_radius=10)
        waves = len(pin.level.get("waves") or [])
        status = "Level {} of {}  \u00b7  {}  \u00b7  {} waves".format(
            pin.index + 1, len(self.pins), STATE_TEXT[pin.state], waves)
        text_w = rect.width - 36 - THUMB_W - 14
        canvas.blit(self.font_big.render(_fit(pin.name, self.font_big, text_w),
                                         True, (246, 246, 236)),
                    (rect.x + 18, rect.y + 12))
        canvas.blit(self.font_small.render(_fit(status, self.font_small,
                                                text_w),
                                           True, STATE_COLORS[pin.state]),
                    (rect.x + 18, rect.y + 54))
        y = rect.y + 80
        for line in _wrap(pin.description or "No briefing for this posting.",
                          self.font_small, text_w)[:3]:
            canvas.blit(self.font_small.render(line, True, (206, 206, 216)),
                        (rect.x + 18, y))
            y += 22
        # the level's own battle map, so the pin is recognisably that place
        thumb = self._level_thumb(pin)
        if thumb is not None:
            box = pygame.Rect(rect.right - THUMB_W - 18, rect.y + 14,
                              THUMB_W, THUMB_H)
            canvas.blit(thumb, box)
            pygame.draw.rect(canvas, (90, 86, 120), box, 2, border_radius=4)
            caption = self._font(16).render("battle map", True, (150, 150, 164))
            canvas.blit(caption, caption.get_rect(midtop=(box.centerx,
                                                          box.bottom + 4)))
        self._draw_button(canvas, self.close_rect, "Close",
                          hover=self._hovered(self.close_rect),
                          font=self.font_small)
        locked = pin.state == STATE_LOCKED
        if locked:
            pygame.draw.rect(canvas, tuple(c // 2 for c in (255, 205, 66)),
                             self.play_rect, border_radius=6)
            pygame.draw.rect(canvas, S.PANEL_EDGE, self.play_rect, 2,
                             border_radius=6)
        else:
            pygame.draw.rect(canvas, (255, 205, 66), self.play_rect,
                             border_radius=6)
            pygame.draw.rect(canvas, (250, 250, 210), self.play_rect, 2,
                             border_radius=6)
        label = self.font_default.render("Play", True, (32, 28, 20))
        canvas.blit(label, label.get_rect(center=self.play_rect.center))

    def _level_thumb(self, pin):
        """A small render of the level's terrain, built once per level.

        It ties the map to the game directly: the pin on the region and the
        playable 40x20 map are the same place.  A level that fails to load
        (bad grid) simply shows no thumbnail.
        """
        key = pin.level_id
        if key not in self._thumb_cache:
            self._thumb_cache[key] = None
            try:
                from engine.level import Level
                terrain = Level(pin.level, self.content).terrain
                self._thumb_cache[key] = pygame.transform.smoothscale(
                    terrain, (THUMB_W, THUMB_H))
            except Exception:                   # noqa: BLE001 - cosmetic only
                self._thumb_cache[key] = None
        return self._thumb_cache[key]

"""Widgets for the standalone level designer: modal stack, file browser,
animation editor, and the sprite-picking flows.

These are deliberately independent of the game's ``Game`` object so the
designer can run on its own; they only need a :class:`Context` (which carries
the content database and the modal stack) and pygame.
"""
import pathlib

import pygame

from core import paths
from core.content import normalise_sprite

ROW_PAD = 4


# ---------------------------------------------------------------------------
# Context / modal plumbing
# ---------------------------------------------------------------------------
class Context:
    """Shared state: the content database and the single open modal."""

    def __init__(self, content=None, assets=None):
        self.content = content
        self.assets = pathlib.Path(assets) if assets else paths.ASSETS_DIR
        self.modal = None
        self._font = None

    @property
    def font(self):
        if self._font is None:
            self._font = pygame.font.Font(None, 22)
        return self._font

    def open_modal(self, modal):
        modal.ctx = self
        self.modal = modal
        return modal

    def close_modal(self):
        self.modal = None


class Modal:
    """Base class: a pop-up that owns input until it closes itself."""

    def __init__(self, ctx=None):
        self.ctx = ctx
        self.rect = pygame.Rect(0, 0, 10, 10)
        self.buttons = []

    def handle_event(self, event):
        pass

    def on_draw(self, screen):  # pragma: no cover - visual only
        veil = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 170))
        screen.blit(veil, (0, 0))
        pygame.draw.rect(screen, (24, 24, 32), self.rect, border_radius=8)
        pygame.draw.rect(screen, (110, 106, 140), self.rect, 2, border_radius=8)


class Chooser(Modal):
    """A tiny modal offering labelled choices (sprite type: static / anim)."""

    def __init__(self, ctx, choices, prompt="Choose sprite type",
                 width=420, height=None):
        super().__init__(ctx)
        self.prompt = prompt
        self._callbacks = {}
        height = height or (110 + 56 * len(choices))
        self.rect = pygame.Rect(0, 0, width, height)
        if pygame.display.get_surface() is not None:
            self.rect.center = pygame.display.get_surface().get_rect().center
        self.buttons = []
        y = self.rect.y + 66
        for label, value, callback in choices:
            rect = pygame.Rect(self.rect.x + 30, y, self.rect.width - 60, 44)
            self.buttons.append((rect, label, value))
            self._callbacks[value] = callback
            y += 56

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, _label, value in self.buttons:
                if rect.collidepoint(event.pos):
                    self._callbacks[value]()
                    return

    def on_draw(self, screen):  # pragma: no cover - visual only
        super().on_draw(screen)
        text = self.ctx.font.render(self.prompt, True, (240, 240, 240))
        screen.blit(text, text.get_rect(midtop=(self.rect.centerx,
                                                self.rect.y + 20)))
        for rect, label, _value in self.buttons:
            pygame.draw.rect(screen, (96, 120, 70), rect, border_radius=6)
            lab = self.ctx.font.render(label, True, (240, 240, 240))
            screen.blit(lab, lab.get_rect(center=rect.center))


# ---------------------------------------------------------------------------
# File browser
# ---------------------------------------------------------------------------
class FileBrowser(Modal):
    """Browse ``assets/`` for a PNG and hand its relative path to a callback."""

    def __init__(self, ctx, callback, start="", assets=None):
        super().__init__(ctx)
        self.callback = callback
        self.assets = pathlib.Path(assets) if assets else (
            ctx.assets if ctx else paths.ASSETS_DIR)
        self.row_h = ctx.font.get_height() + ROW_PAD if ctx else 24
        self.list_rect = pygame.Rect(0, 0, 540, 380)
        if pygame.display.get_surface() is not None:
            self.list_rect.center = pygame.display.get_surface().get_rect().center
        self.scroll = 0
        self.rel = ""
        self.entries = []
        self.rect = self.list_rect.inflate(40, 60)
        self._enter(start)

    # -------------------------------------------------------------- navigation
    def _normalise(self, rel):
        rel = str(rel or "").replace("\\", "/").strip("/")
        parts = [p for p in rel.split("/") if p and p not in (".",)]
        return "/".join(parts)

    def _enter(self, rel):
        self.rel = self._normalise(rel)
        self.entries = self._scan()
        self.scroll = 0

    def _scan(self):
        base = self.assets.joinpath(*self.rel.split("/")) if self.rel else self.assets
        entries = [("up", "..")] if self.rel else []
        try:
            children = sorted(base.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            return entries
        for child in children:
            if child.is_dir():
                entries.append(("dir", child.name))
            elif child.suffix.lower() == ".png":
                entries.append(("img", child.name))
        return entries

    def row_at(self, pos):
        if not self.list_rect.collidepoint(pos):
            return None
        row = (pos[1] - (self.list_rect.y + 4)) // self.row_h
        idx = self.scroll + row
        if 0 <= idx < len(self.entries):
            return idx
        return None

    def _join(self, name):
        return "{}/{}".format(self.rel, name) if self.rel else name

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL and self.list_rect.collidepoint(
                getattr(event, "pos", (0, 0))):
            self.scroll = max(0, self.scroll - event.y)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            idx = self.row_at(event.pos)
            if idx is None:
                return
            kind, name = self.entries[idx]
            if kind == "up":
                self._enter("/".join(self.rel.split("/")[:-1]))
            elif kind == "dir":
                self._enter(self._join(name))
            elif kind == "img":
                rel = self._join(name)
                self.ctx.close_modal()
                self.callback(rel)

    def on_draw(self, screen):  # pragma: no cover - visual only
        super().on_draw(screen)
        title = self.ctx.font.render("assets/" + self.rel, True, (230, 230, 230))
        screen.blit(title, (self.list_rect.x, self.rect.y + 8))
        max_rows = max(1, (self.list_rect.height - 8) // self.row_h)
        for row in range(max_rows):
            idx = self.scroll + row
            if idx >= len(self.entries):
                break
            kind, name = self.entries[idx]
            rect = pygame.Rect(self.list_rect.x + 4,
                               self.list_rect.y + 4 + row * self.row_h,
                               self.list_rect.width - 8, self.row_h)
            color = (90, 86, 110) if kind == "dir" else (58, 54, 84)
            pygame.draw.rect(screen, color, rect, border_radius=3)
            label = ("[dir] " if kind == "dir" else "") + name
            text = self.ctx.font.render(label, True, (235, 235, 235))
            screen.blit(text, (rect.x + 6, rect.centery - text.get_height() // 2))


# ---------------------------------------------------------------------------
# Animation editor
# ---------------------------------------------------------------------------
def load_sheet(rel_or_path):
    path = pathlib.Path(str(rel_or_path))
    if not path.is_absolute():
        path = paths.asset(*str(rel_or_path).replace("\\", "/").split("/"))
    try:
        surf = pygame.image.load(str(path))
        if pygame.display.get_surface() is not None:
            surf = surf.convert_alpha()
        return surf
    except (pygame.error, FileNotFoundError):
        surf = pygame.Surface((64, 64), pygame.SRCALPHA)
        pygame.draw.rect(surf, (180, 90, 90), (4, 4, 56, 56), border_radius=6)
        return surf


class AnimationEditor(Modal):
    """Pick frames out of a spritesheet.

    With ``states`` set (units) it records frames per named state; with
    ``states=None`` (terrain) it records a single looping clip under ``_clip``.
    Saving reports ``(sheet, frame_w, frame_h, margin, spacing, anims)``.
    """

    DEFAULT_STATES = ["idle", "walk", "attack", "death"]

    def __init__(self, ctx, sheet, callback, states="default",
                 frame_w=64, frame_h=64):
        super().__init__(ctx)
        self.sheet_rel = str(sheet).replace("\\", "/")
        self.sheet = load_sheet(self.sheet_rel)
        self.callback = callback
        self.frame_w = int(frame_w)
        self.frame_h = int(frame_h)
        self.margin = 0
        self.spacing = 0
        self.cell = 48
        if states == "default":
            states = list(self.DEFAULT_STATES)
        self.states = list(states) if states else None
        self._names = self.states or ["_clip"]
        self.current_state = self._names[0]
        self.frames = {name: [] for name in self._names}
        self.fps = {name: 8.0 for name in self._names}
        self.scroll = 0

        self.grid = pygame.Rect(30, 96, 900, 360)
        self.save_btn = pygame.Rect(0, 0, 140, 38)
        self.save_btn.topleft = (self.grid.x, self.grid.bottom + 16)
        self.rect = self.grid.union(self.save_btn).inflate(40, 80)

    # -------------------------------------------------------------- geometry
    def _grid_metrics(self):
        cols = max(1, self.sheet.get_width() // self.frame_w)
        rows = max(1, self.sheet.get_height() // self.frame_h)
        visible = max(1, self.grid.height // self.cell)
        return cols, rows, self.cell, visible

    def _state_rows(self):
        rows = []
        if not self.states:
            return rows
        x = self.grid.right + 20
        y = self.grid.y
        for name in self.states:
            rows.append((pygame.Rect(x, y, 150, 30), name))
            y += 38
        return rows

    def _frame_at(self, pos):
        if not self.grid.collidepoint(pos):
            return None
        cols, rows, cell, _vis = self._grid_metrics()
        col = (pos[0] - (self.grid.x + 6)) // cell
        row = (pos[1] - (self.grid.y + 6)) // cell + self.scroll
        if 0 <= col < cols and 0 <= row < rows:
            return int(row * cols + col)
        return None

    # -------------------------------------------------------------- events
    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL and self.grid.collidepoint(
                getattr(event, "pos", (0, 0))):
            self.scroll = max(0, self.scroll - event.y)
            return
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if self.save_btn.collidepoint(event.pos):
            self.save()
            return
        for rect, name in self._state_rows():
            if rect.collidepoint(event.pos):
                self.current_state = name
                return
        index = self._frame_at(event.pos)
        if index is not None:
            frames = self.frames[self.current_state]
            if index in frames:
                frames.remove(index)
            else:
                frames.append(index)
                frames.sort()
            return

    def _anim_dict(self, name):
        return {
            "kind": "sheet",
            "path": self.sheet_rel,
            "frame_w": self.frame_w,
            "frame_h": self.frame_h,
            "frames": list(self.frames[name]),
            "fps": float(self.fps.get(name, 8.0)),
            "loop": True,
        }

    def save(self):
        anims = {name: self._anim_dict(name) for name in self._names}
        self.callback(self.sheet_rel, self.frame_w, self.frame_h,
                      self.margin, self.spacing, anims)

    def on_draw(self, screen):  # pragma: no cover - visual only
        super().on_draw(screen)
        cols, rows, cell, visible = self._grid_metrics()
        clip = screen.get_clip()
        screen.set_clip(self.grid)
        screen.fill((12, 12, 16), self.grid)
        for row in range(visible):
            for col in range(cols):
                index = (row + self.scroll) * cols + col
                if index >= cols * rows:
                    break
                x = self.grid.x + 6 + col * cell
                y = self.grid.y + 6 + (row - self.scroll) * cell
                cell_rect = pygame.Rect(x, y, cell - 2, cell - 2)
                src = pygame.Rect(col * self.frame_w, (row + self.scroll) * self.frame_h,
                                  self.frame_w, self.frame_h)
                thumb = self.sheet.subsurface(src).copy()
                thumb = pygame.transform.smoothscale(thumb, (cell - 6, cell - 6))
                screen.blit(thumb, cell_rect)
                chosen = index in self.frames[self.current_state]
                pygame.draw.rect(screen, (250, 240, 120) if chosen else (70, 66, 90),
                                 cell_rect, 2 if chosen else 1)
                num = pygame.font.Font(None, 16).render(str(index), True, (240, 240, 240))
                screen.blit(num, (cell_rect.x + 1, cell_rect.y + 1))
        screen.set_clip(clip)
        for rect, name in self._state_rows():
            selected = name == self.current_state
            pygame.draw.rect(screen, (96, 120, 70) if selected else (58, 54, 84),
                             rect, border_radius=4)
            label = "{} ({})".format(name, len(self.frames[name]))
            text = self.ctx.font.render(label, True, (240, 240, 240))
            screen.blit(text, text.get_rect(center=rect.center))
        pygame.draw.rect(screen, (96, 120, 70), self.save_btn, border_radius=6)
        text = self.ctx.font.render("Save", True, (240, 240, 240))
        screen.blit(text, text.get_rect(center=self.save_btn.center))


# ---------------------------------------------------------------------------
# Sprite-picking flows
# ---------------------------------------------------------------------------
def _open_png_picker(ctx, callback):
    ctx.open_modal(FileBrowser(ctx, callback))


def open_unit_sprite_flow(ctx, default_spec, on_done):
    """Static image or a named-state animation, then ``on_done(spec)``."""

    def choose_static():
        def picked(path):
            on_done(normalise_sprite({"kind": "image", "path": path}))
            ctx.close_modal()
        _open_png_picker(ctx, picked)

    def choose_anim():
        def picked(path):
            def saved(sheet, fw, fh, margin, spacing, anims):
                on_done({"kind": "sprites", "image": None, "animations": anims})
                ctx.close_modal()
            ctx.open_modal(AnimationEditor(ctx, path, saved,
                                           states=list(AnimationEditor.DEFAULT_STATES)))
        _open_png_picker(ctx, picked)

    ctx.open_modal(Chooser(ctx, [("Static image", "static", choose_static),
                                 ("Animation", "anim", choose_anim)]))


def open_terrain_sprite_flow(ctx, default_spec, on_done):
    """Static image or a single looping clip, then ``on_done(spec)``."""

    def choose_static():
        def picked(path):
            on_done(normalise_sprite({"kind": "image", "path": path}))
            ctx.close_modal()
        _open_png_picker(ctx, picked)

    def choose_anim():
        def picked(path):
            def saved(sheet, fw, fh, margin, spacing, anims):
                on_done(anims.get("_clip"))
                ctx.close_modal()
            ctx.open_modal(AnimationEditor(ctx, path, saved, states=None))
        _open_png_picker(ctx, picked)

    ctx.open_modal(Chooser(ctx, [("Static image", "static", choose_static),
                                 ("Animation", "anim", choose_anim)]))

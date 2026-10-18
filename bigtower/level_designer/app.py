"""The designer application: window, tab bar and main loop.

This mirrors the game's fixed-canvas rendering (draw onto a 1280x860 surface,
letterbox it into the real window) but without the scene stack -- the designer
just swaps between a handful of editor tabs.  Every tab reads and writes the
same ``content/`` JSON the game loads, via :class:`core.content.ContentDB`.

Run it with::

    .venv/bin/python designer.py
"""
from __future__ import annotations

import sys

import pygame

from core.content import ContentDB
from level_designer import tabs as T
from level_designer import widgets as W

# The tab layouts in tabs.py assume a 1280-wide canvas and a list column tall
# enough for its four buttons (bottom edge ~828).
WIDTH = 1280
HEIGHT = 860
TAB_H = 32
BAR_BG = (30, 30, 42)


class Designer:
    """Owns the window, the shared widgets context and the editor tabs."""

    def __init__(self, fullscreen=False):
        pygame.init()
        pygame.display.set_caption("Big Tower - Level Designer")
        self.settings = {"fullscreen": bool(fullscreen)}
        self.window = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        if self.settings["fullscreen"]:
            self._apply_fullscreen()

        self.canvas = pygame.Surface((WIDTH, HEIGHT)).convert()
        self._view_flags = None
        self._view_rect = (0, 0, WIDTH, HEIGHT)
        self._refresh_view_cache()

        self.clock = pygame.time.Clock()
        self.running = True
        self.fonts = {
            "small": pygame.font.Font(None, 22),
            "default": pygame.font.Font(None, 30),
            "big": pygame.font.Font(None, 48),
            "title": pygame.font.Font(None, 60),
        }
        self.ctx = W.Ctx(self.canvas, self.fonts)
        self.content = ContentDB()

        self.status = ""
        self.status_color = W.DIM
        self.set_status("Content: {}".format(self.content.root))

        # tabs
        self.terrain_tab = T.TerrainTab(self)
        self.units_tab = T.UnitsTab(self)
        self.races_tab = T.RacesTab(self)
        self.levels_tab = T.LevelsTab(self)
        self.help_tab = T.HelpTab(self)
        self.tabs = [
            ("Terrain", self.terrain_tab),
            ("Units", self.units_tab),
            ("Races", self.races_tab),
            ("Levels", self.levels_tab),
            ("Help", self.help_tab),
        ]
        self.active = 0
        self.tab_buttons = []
        self._build_tab_bar()

    # ------------------------------------------------------------------ tabs
    def _build_tab_bar(self):
        x = 10
        for index, (name, _tab) in enumerate(self.tabs):
            width = self.fonts["default"].size(name)[0] + 28
            button = W.Btn(self.ctx, (x, 4, width, TAB_H - 8), name,
                           fn=self._switch_to(index))
            self.tab_buttons.append(button)
            x += width + 6
        self._sync_tab_bar()

    def _switch_to(self, index):
        def switch():
            self.set_tab(index)
        return switch

    def _sync_tab_bar(self):
        for index, button in enumerate(self.tab_buttons):
            active = index == self.active
            button.color = W.ACCENT if active else W.PANEL2
            button.fg = W.TEXT

    def set_tab(self, index):
        if 0 <= index < len(self.tabs):
            self.active = index
            self._sync_tab_bar()
            shown = self.tabs[index][1]
            if hasattr(shown, "on_show"):
                shown.on_show()

    @property
    def current_tab(self):
        return self.tabs[self.active][1]

    # ------------------------------------------------------- shared services
    def terrain_lookup(self):
        """``{grid char: terrain dict}`` from the (possibly unsaved) palette."""
        return {t.get("char", "?"): t for t in self.terrain_tab.items}

    def set_status(self, message, color=None):
        self.status = str(message)
        self.status_color = color or W.TEXT
        self.ctx.status = self.status
    # ----------------------------------------------------------------- window
    def _apply_fullscreen(self):
        info = pygame.display.Info()
        self.window = pygame.display.set_mode(
            (info.current_w, info.current_h), pygame.FULLSCREEN)

    def toggle_fullscreen(self):
        self.settings["fullscreen"] = not self.settings["fullscreen"]
        if self.settings["fullscreen"]:
            self._apply_fullscreen()
        else:
            self.window = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        self._refresh_view_cache()

    def _refresh_view_cache(self):
        win = self.window.get_size()
        flags = (win, self.settings["fullscreen"])
        if self._view_flags == flags:
            return
        self._view_flags = flags
        ww, wh = win
        scale = min(ww / WIDTH, wh / HEIGHT)
        w, h = max(1, round(WIDTH * scale)), max(1, round(HEIGHT * scale))
        self._view_rect = ((ww - w) // 2, (wh - h) // 2, w, h)

    def _to_canvas_pos(self, pos):
        x, y, w, h = self._view_rect
        if w <= 0 or h <= 0:
            return (0, 0)
        # No flip() happens in headless/dummy mode, so guard the window size.
        return (int((pos[0] - x) * WIDTH / w), int((pos[1] - y) * HEIGHT / h))

    def _blit(self):
        self._refresh_view_cache()
        x, y, w, h = self._view_rect
        if (w, h) == (WIDTH, HEIGHT):
            self.window.blit(self.canvas, (x, y))
        else:
            scaled = pygame.transform.smoothscale(self.canvas, (w, h))
            self.window.fill((10, 10, 14))
            self.window.blit(scaled, (x, y))
        pygame.display.flip()

    # ----------------------------------------------------------------- events
    def _dispatch(self, event):
        if event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN,
                          pygame.MOUSEBUTTONUP):
            event.pos = self._to_canvas_pos(event.pos)
        elif event.type == pygame.MOUSEWHEEL:
            event.pos = self._to_canvas_pos(pygame.mouse.get_pos())

        if self.ctx.modal is not None:
            self.ctx.modal.handle_event(event)
            return
        for button in self.tab_buttons:
            if button.handle_event(event):
                return
        self.current_tab.handle_event(event)

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                self.toggle_fullscreen()
                continue
            if (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
                    and self.ctx.modal is None):
                self.running = False
                continue
            if (event.type == pygame.KEYDOWN and event.key == pygame.K_s
                    and event.mod & pygame.KMOD_CTRL):
                tab = self.current_tab
                if hasattr(tab, "save"):
                    tab.save()
                continue
            self._dispatch(event)

    # ----------------------------------------------------------------- render
    def _draw_tab_bar(self):
        pygame.draw.rect(self.canvas, BAR_BG, (0, 0, WIDTH, TAB_H))
        pygame.draw.line(self.canvas, W.EDGE, (0, TAB_H), (WIDTH, TAB_H), 2)
        for button in self.tab_buttons:
            button.draw(self.canvas)

    def _draw_status(self):
        if not self.status:
            return
        surf = self.fonts["small"].render(self.status, True, self.status_color)
        self.canvas.blit(surf, surf.get_rect(midright=(WIDTH - 12, TAB_H // 2)))

    def _draw(self):
        self.canvas.fill((0, 0, 0))
        self.current_tab.draw()
        if self.ctx.modal is not None:
            self.ctx.modal.draw(self.canvas)
        self._draw_tab_bar()
        self._draw_status()
        self._blit()

    # -------------------------------------------------------------------- run
    def run(self):
        while self.running:
            self._handle_events()
            self._draw()
            self.clock.tick(60)
        pygame.quit()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    designer = Designer(fullscreen="--fullscreen" in argv)
    try:
        designer.run()
    except KeyboardInterrupt:      # pragma: no cover - interactive only
        pygame.quit()
    return 0


if __name__ == "__main__":         # pragma: no cover
    raise SystemExit(main())

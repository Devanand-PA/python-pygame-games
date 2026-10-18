"""Campaign select overlay: pick a race (campaign) to play.

Lists every race from the content database, shows how many of its levels the
current user has cleared, and opens the level select for the chosen one.
"""
import pygame

from core import savestate
from core.content import get_content
from core.scene import Scene
from gui.widgets import Button
from menus.common import MenuPage


class Scene(MenuPage, Scene):
    scene_type = "menu"

    def __init__(self, game):
        super().__init__(game)
        self.content = get_content()
        self.races = self.content.sorted_races()

        completed = savestate.levels_completed(game.user or "Player")

        rows = max(1, len(self.races))
        self.box = pygame.Rect(0, 0, 640, 150 + 66 * rows + 74)
        self.box.center = (game.canvas.get_width() // 2,
                           game.canvas.get_height() // 2)
        self.title = game.fonts["big"].render("Play Campaign", True,
                                              (250, 250, 240))

        self.buttons = []
        y = self.box.y + 88
        for idx, race in enumerate(self.races):
            levels = self.content.race_levels(race)
            cleared = sum(1 for lv in levels if lv["id"] in completed)
            total = len(levels)
            if total and cleared >= total:
                suffix = "  (cleared)"
            else:
                suffix = "  ({}/{})".format(cleared, total)
            btn = Button(game, (self.box.x + 40, y),
                         (self.box.width - 80, 54),
                         text="{}{}".format(race.get("name", race["id"]),
                                            suffix))
            btn.race = race
            btn.function = self._make_launcher(race)
            btn.sel = idx == 0
            self.buttons.append(btn)
            y += 66

        self.back_btn = Button(game, (self.box.x + 40, y + 4),
                               (self.box.width - 80, 46),
                               text="Back", function=self.close_overlay)
        self.buttons.append(self.back_btn)

    # ---------------------------------------------------------------- actions
    def _make_launcher(self, race):
        def launch():
            self._launch(race)
        return launch

    def _launch(self, race):
        from menus.level_select import Scene as LevelSelect
        self.push_overlay(LevelSelect(self.game, race))

    # ---------------------------------------------------------------- events
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.close_overlay()
            else:
                self.menu_key(self.buttons, event)
        elif event.type == pygame.MOUSEMOTION:
            self.menu_hover(self.buttons, event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.menu_click(self.buttons, event.pos)

    # ---------------------------------------------------------------- drawing
    def on_draw(self):
        veil = pygame.Surface(self.game.canvas.get_size(), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 160))
        self.game.canvas.blit(veil, (0, 0))
        pygame.draw.rect(self.game.canvas, (18, 18, 26), self.box, border_radius=10)
        pygame.draw.rect(self.game.canvas, (90, 86, 120), self.box, 3,
                         border_radius=10)
        self.game.canvas.blit(self.title,
                              self.title.get_rect(midtop=(self.box.centerx,
                                                          self.box.y + 20)))
        for b in self.buttons:
            b.on_draw()

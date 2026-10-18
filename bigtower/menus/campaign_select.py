"""Campaign select: choose a race, then a level.

Campaigns are the races defined in ``content/races/``.  The list on the left
picks a campaign; the panel on the right previews its theme, roster and the
player's progress.
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
        self.completed = savestate.levels_completed(game.user or "Player")

        cw, ch = self.game.canvas.get_size()
        self.mainbox = pygame.Rect(40, 90, 380, 0)
        self.buttons = []
        y = self.mainbox.y
        for race in self.races:
            btn = Button(self.game, (self.mainbox.x + 10, y),
                         (self.mainbox.width - 20, 56),
                         text=race.get("name", race["id"]))
            btn.race = race
            btn.function = self._make_launcher(race)
            self.buttons.append(btn)
            y += 66
        self.back_btn = Button(self.game, (self.mainbox.x + 10, y + 6),
                               (self.mainbox.width - 20, 46), text="Back",
                               function=self.close_overlay)
        self.buttons.append(self.back_btn)
        self.mainbox.height = (y + 62) - self.mainbox.y

        self.framebox = pygame.Rect(self.mainbox.right + 30, 90,
                                    cw - self.mainbox.width - 110, ch - 180)
        self.selected_index = -1
        self.preview_lines = []
        if self.races:
            self._select(0)
            self.buttons[0].sel = True

    # ---------------------------------------------------------------- helpers
    def _make_launcher(self, race):
        def launch():
            self._launch(race)
        return launch

    def _select(self, index):
        if not self.races:
            return
        self.selected_index = max(0, min(index, len(self.races) - 1))
        race = self.races[self.selected_index]
        fonts = self.game.fonts
        self.race_title = fonts["big"].render(
            race.get("name", race["id"]), True,
            tuple(race.get("color") or (240, 240, 230)))
        levels = self.content.race_levels(race)
        done = sum(1 for lv in levels if lv["id"] in self.completed)
        units = self.content.race_units(race, "defender")
        enemies = self.content.race_units(race, "attacker")
        lines = [
            race.get("description", ""),
            "",
            "Levels cleared: {} / {}".format(done, len(levels)),
            "Units available: {}".format(", ".join(u.name for u in units) or "-"),
            "Enemies: {}".format(", ".join(u.name for u in enemies) or "-"),
        ]
        self.preview_lines = [fonts["default"].render(l, True, (230, 230, 224))
                              for l in lines]

    def _launch(self, race):
        from menus.level_select import Scene as LevelSelect
        if self in self.game.subscenes:
            # swap the campaign picker for the level list in the same slot
            self.game.subscenes.remove(self)
            self.game.subscenes.append(LevelSelect(self.game, race))
        else:
            self.game.scene = LevelSelect(self.game, race)

    # ---------------------------------------------------------------- events
    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            for i, b in enumerate(self.buttons):
                if b is not self.back_btn and b.rect.collidepoint(event.pos):
                    self._select(i)
            self.menu_hover(self.buttons, event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.menu_click(self.buttons, event.pos)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.close_overlay()
            self.menu_key(self.buttons, event)

    def on_draw(self):
        veil = pygame.Surface(self.game.canvas.get_size(), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 170))
        self.game.canvas.blit(veil, (0, 0))
        self.draw_menu_box(self.mainbox)
        for b in self.buttons:
            b.on_draw()

        pygame.draw.rect(self.game.canvas, (12, 12, 16), self.framebox,
                         border_radius=8)
        pygame.draw.rect(self.game.canvas, (70, 66, 90), self.framebox, 3,
                         border_radius=8)
        if self.races:
            self.game.canvas.blit(self.race_title,
                                  self.race_title.get_rect(
                                      topleft=(self.framebox.x + 24,
                                               self.framebox.y + 20)))
            y = self.framebox.y + 24 + self.race_title.get_height() + 14
            for line in self.preview_lines:
                self.game.canvas.blit(line, (self.framebox.x + 24, y))
                y += line.get_height() + 10

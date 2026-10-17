"""Career hub: player stats on the right, actions on the left."""
import pygame

from core import paths, savestate
from core.scene import Scene
from menus.common import MenuPage


class Scene(MenuPage, Scene):
    scene_type = "menu"

    def __init__(self, game):
        super().__init__(game)
        self.background = pygame.image.load(
            str(paths.asset("menus", "welcome_background.jpg"))).convert()
        self.background = pygame.transform.scale(
            self.background, (self.game.canvas.get_size()))

        cw, ch = self.game.canvas.get_size()
        self.mainbox = pygame.Rect(40, 40, 360, 0)
        self.buttons = self._make_menu_buttons([
            {"name": "play", "text": "Play Campaign", "function": self.action_play},
            {"name": "settings", "text": "Settings", "function": self.action_settings},
            {"name": "change_user", "text": "Change User", "function": self.action_change_user},
            {"name": "menu", "text": "Back to Main Menu",
             "function": self.action_main_menu},
        ], self.mainbox)

        # --- stats panel -------------------------------------------------
        self.framebox = pygame.Rect(self.mainbox.right + 40, 40,
                                    cw - self.mainbox.width - 120, ch - 80)
        self.stats = savestate.load_stats(game.user or "Player")
        self.user_label = game.fonts["big"].render(game.user or "Player", True,
                                                   (250, 250, 240))
        self.stat_lines = [
            game.fonts["default"].render(
                "{}: {}".format(key, self.stats[key]),
                True, (240, 240, 230))
            for key in ("Campaigns Cleared", "Kills")
        ]
        from core.content import get_content
        content = get_content()
        done = set(self.stats.get("Levels Completed") or [])
        self.stat_lines.append(game.fonts["small"].render(
            "Progress by campaign:", True, (200, 200, 190)))
        for race in content.sorted_races():
            levels = content.race_levels(race)
            cleared = sum(1 for lv in levels if lv["id"] in done)
            line = "  {} - {}/{}".format(race.get("name", race["id"]),
                                         cleared, len(levels))
            self.stat_lines.append(game.fonts["default"].render(line, True,
                                                                (240, 240, 230)))

    # ---------------------------------------------------------------- actions
    def action_play(self):
        from menus.campaign_select import Scene as Campaign
        self.push_overlay(Campaign(self.game))

    def action_settings(self):
        from menus.settings_overlay import Scene as Settings
        self.push_overlay(Settings(self.game))

    def action_change_user(self):
        from menus.user_selection import Scene as UserSelect
        self.push_overlay(UserSelect(self.game, savestate.list_users()))

    def action_main_menu(self):
        from menus.welcome_screen import Scene as Welcome
        self.replace_with(Welcome(self.game))

    # ---------------------------------------------------------------- events
    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.menu_hover(self.buttons, event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.menu_click(self.buttons, event.pos)
        elif event.type == pygame.KEYDOWN:
            self.menu_key(self.buttons, event)

    def on_draw(self):
        self.game.canvas.blit(self.background, (0, 0))
        self.draw_menu_box(self.mainbox)
        for b in self.buttons:
            b.on_draw()

        pygame.draw.rect(self.game.canvas, (12, 12, 16), self.framebox,
                         border_radius=8)
        pygame.draw.rect(self.game.canvas, (70, 66, 90), self.framebox, 3,
                         border_radius=8)
        self.game.canvas.blit(self.user_label,
                              self.user_label.get_rect(
                                  topleft=(self.framebox.x + 30,
                                           self.framebox.y + 24)))
        pygame.draw.line(self.game.canvas, (250, 250, 240),
                         (self.framebox.x + 30,
                          self.framebox.y + 24 + self.user_label.get_height() + 4),
                         (self.framebox.x + 30 + self.user_label.get_width(),
                          self.framebox.y + 24 + self.user_label.get_height() + 4), 2)
        y = self.framebox.y + 90
        for line in self.stat_lines:
            self.game.canvas.blit(line, (self.framebox.x + 30, y))
            y += line.get_height() + 12

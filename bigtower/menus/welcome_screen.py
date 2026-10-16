"""Main menu: background art + Start / Settings / Quit."""
import pygame

from core import paths
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
        self.title = self.game.fonts["title"].render("BIG TOWER", True, (250, 250, 240))

        self.mainbox = pygame.Rect(0, 0, 380, 300)
        self.mainbox.bottomright = (self.game.canvas.get_width() - 60,
                                    self.game.canvas.get_height() - 60)
        self.last_user = self._known_last_user()
        start_text = ("Continue as {}".format(self.last_user)
                      if self.last_user else "Start Game")
        self.buttons = self._make_menu_buttons([
            {"name": "start", "text": start_text, "function": self.action_start},
            {"name": "settings", "text": "Settings", "function": self.action_settings},
            {"name": "quit", "text": "Quit Game", "function": self.game.on_quit},
        ], self.mainbox)

    def _known_last_user(self):
        """Return the remembered profile only if it still exists on disk."""
        from core import savestate
        name = self.game.settings.get("last_user") or ""
        if name and savestate.user_exists(name):
            return name
        return ""

    def action_start(self):
        from core import savestate
        from menus.career_menu import Scene as Career
        # Resume the remembered profile, or jump straight in if one is active.
        if self.game.user or self.last_user:
            self.game.set_user(self.game.user or self.last_user)
            self.replace_with(Career(self.game))
            return
        from menus.user_selection import Scene as UserSelect
        users = savestate.list_users()
        self.push_overlay(UserSelect(self.game, users))

    def action_settings(self):
        from menus.settings_overlay import Scene as Settings
        self.push_overlay(Settings(self.game))

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
        self.game.canvas.blit(self.title,
                              self.title.get_rect(
                                  topright=(self.mainbox.right - 20,
                                            self.mainbox.top - 70)))

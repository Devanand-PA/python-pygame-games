import pygame
import subprocess
import sys
import os

from utils.gui_elements import Button, ListBox


class Scene:
    def __init__(self, game):
        self.game = game
        self.background = pygame.image.load(
            "assets/menus/welcom_screen_background_2.jpg"
        )
        self.subscene_index = len(game.subscenes)

        from campaigns import CAMPAIGNS
        self.campaigns = CAMPAIGNS
        self.campaign_names = list(self.campaigns.keys()) or ["(none)"]

        self.mainbox_width = self.game.screen_size[0] // 2
        self.mainbox_height = self.game.screen_size[1] // 2
        self.mainbox = pygame.Rect(
            self.game.screen_size[0] // 4,
            self.game.screen_size[1] // 4,
            self.mainbox_width,
            self.mainbox_height,
        )

        self.background = pygame.transform.scale(
            self.background, (self.mainbox.width, self.mainbox.height)
        )

        self.title = self.game.title_font.render("Select Campaign", True, (0, 0, 0))

        self.campaign_list = ListBox(
            self.game,
            [self.mainbox.x + 20, self.mainbox.y + 60],
            [self.mainbox_width - 40, self.mainbox_height - 140],
            self.campaign_names,
            sel=True,
        )

        button_w = (self.mainbox_width - 60) // 2
        button_h = 40
        button_y = self.mainbox.bottom - button_h - 20

        self.launch_button = Button(
            self.game,
            [self.mainbox.x + 20, button_y],
            [button_w, button_h],
            text="Launch",
            bgcolor=[(100, 100, 0), (200, 200, 0)],
            fgcolor=[(0, 0, 0), (0, 0, 0)],
            sel=True,
        )

        self.back_button = Button(
            self.game,
            [self.mainbox.x + 40 + button_w, button_y],
            [button_w, button_h],
            text="Back",
            bgcolor=[(100, 100, 0), (200, 200, 0)],
            fgcolor=[(0, 0, 0), (0, 0, 0)],
        )

    def kill(self):
        self.game.subscenes.pop(self.subscene_index)

    def launch_selected(self):
        campaign_name = self.campaign_list.sel_text
        campaign = self.campaigns.get(campaign_name)
        if not campaign:
            return

        scenarios = campaign.get("scenarios", [])
        if not scenarios:
            print(f"Campaign '{campaign_name}' has no scenarios.")
            return

        scenario = scenarios[0]
        game_file = scenario.get("game_file")
        if not game_file or not os.path.exists(game_file):
            print(f"Game file '{game_file}' not found.")
            return

        game_dir = os.path.dirname(os.path.abspath(game_file))
        game_name = os.path.basename(game_file)

        self.game.child_process = subprocess.Popen(
            [sys.executable, game_name],
            cwd=game_dir,
        )

        # Optional: minimize the menu window so the OS gives the
        # game window focus and the compositor stops blitting us.
        try:
            pygame.display.iconify()
        except pygame.error:
            pass

    def on_draw(self):
        self.game.screen.blit(self.background, (self.mainbox.x, self.mainbox.y))

        pygame.draw.rect(self.game.screen, (10, 10, 10), self.mainbox, 5)

        self.game.screen.blit(
            self.title,
            (self.mainbox.x + 20, self.mainbox.y + 10),
        )

        self.campaign_list.on_draw()
        self.launch_button.on_draw()
        self.back_button.on_draw()

    def default_handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.kill()
                return
            if event.key == pygame.K_RETURN:
                self.launch_selected()
                return

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.launch_button.rect.collidepoint(event.pos):
                self.launch_selected()
                return
            if self.back_button.rect.collidepoint(event.pos):
                self.kill()
                return

        self.campaign_list.handle_event(event)

    def handle_event(self, event):
        self.default_handle_event(event)

    def handle_keypress(self):
        pass

    def on_update(self, delta_time):
        pass

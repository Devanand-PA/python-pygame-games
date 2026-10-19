"""Pause overlay for the game scene: Resume / Restart / Quit to Career."""
import pygame

from core.scene import Scene
from gui.widgets import Button


class Scene(Scene):
    scene_type = "menu"

    def __init__(self, game, game_scene):
        super().__init__(game)
        self.game_scene = game_scene
        self.box = pygame.Rect(0, 0, 380, 300)
        self.box.center = (game.canvas.get_width() // 2,
                           game.canvas.get_height() // 2)
        self.title = game.fonts["big"].render("Paused", True, (250, 250, 240))
        self.buttons = [
            Button(game, (self.box.x + 40, self.box.y + 80),
                   (self.box.width - 80, 48), text="Resume",
                   function=self.close_overlay),
            Button(game, (self.box.x + 40, self.box.y + 140),
                   (self.box.width - 80, 48), text="Restart Level",
                   function=self.restart),
            Button(game, (self.box.x + 40, self.box.y + 200),
                   (self.box.width - 80, 48), text="Quit to Career",
                   function=self.quit_to_career),
        ]
        self.buttons[0].sel = True

    def restart(self):
        from engine.game_scene import GameScene
        self.game.subscenes.clear()
        self.game.scene = GameScene(self.game, self.game_scene.level_id)

    def quit_to_career(self):
        self.game.subscenes.clear()
        self.game_scene.finishbattle(record=True)
        from menus.career_menu import Scene as Career
        self.game.scene = Career(self.game)

    def _move(self, step):
        for i, b in enumerate(self.buttons):
            if b.sel:
                b.sel = False
                self.buttons[(i + step) % len(self.buttons)].sel = True
                return

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.close_overlay()
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                for b in self.buttons:
                    if b.sel:
                        self.game.play("click", 0.4)
                        b.function()
                        return
            elif event.key == pygame.K_UP:
                self._move(-1)
            elif event.key == pygame.K_DOWN:
                self._move(1)
        elif event.type == pygame.MOUSEMOTION:
            for b in self.buttons:
                b.sel = b.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            for b in self.buttons:
                if b.rect.collidepoint(event.pos):
                    self.game.play("click", 0.4)
                    b.function()
                    return

    def on_draw(self):
        veil = pygame.Surface(self.game.canvas.get_size(), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 150))
        self.game.canvas.blit(veil, (0, 0))
        pygame.draw.rect(self.game.canvas, (18, 18, 26), self.box, border_radius=10)
        pygame.draw.rect(self.game.canvas, (90, 86, 120), self.box, 3, border_radius=10)
        self.game.canvas.blit(self.title,
                              self.title.get_rect(midtop=(self.box.centerx,
                                                          self.box.y + 16)))
        for b in self.buttons:
            b.on_draw()

"""Settings overlay: fullscreen + sound toggles."""
import pygame

from core.scene import Scene
from gui.widgets import Button


class Scene(Scene):
    scene_type = "menu"

    def __init__(self, game):
        super().__init__(game)
        self.box = pygame.Rect(0, 0, 420, 260)
        self.box.center = (game.canvas.get_width() // 2,
                           game.canvas.get_height() // 2)
        self.title = game.fonts["big"].render("Settings", True, (250, 250, 240))
        self.fullscreen_btn = Button(
            game, (self.box.x + 30, self.box.y + 80), (self.box.width - 60, 48),
            text=self._fullscreen_text(), function=self.toggle_fullscreen)
        self.sfx_btn = Button(
            game, (self.box.x + 30, self.box.y + 140), (self.box.width - 60, 48),
            text=self._sfx_text(), function=self.toggle_sfx)
        self.back_btn = Button(
            game, (self.box.x + 30, self.box.y + 200), (self.box.width - 60, 44),
            text="Back", function=self.close_overlay)
        self.buttons = [self.fullscreen_btn, self.sfx_btn, self.back_btn]
        self.fullscreen_btn.sel = True

    def _fullscreen_text(self):
        return "Fullscreen: {}".format(
            "ON" if self.game.settings["fullscreen"] else "OFF")

    def _sfx_text(self):
        return "Sound: {}".format(
            "ON" if self.game.settings["sfx"] else "OFF")

    def toggle_fullscreen(self):
        self.game.toggle_fullscreen()
        self.fullscreen_btn.set_text(self._fullscreen_text())

    def toggle_sfx(self):
        self.game.set_sfx(not self.game.settings["sfx"])
        self.sfx_btn.set_text(self._sfx_text())

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.close_overlay()
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                for b in self.buttons:
                    if b.sel and b.function:
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
                    if b.function:
                        b.function()
                    return

    def _move(self, step):
        for i, b in enumerate(self.buttons):
            if b.sel:
                b.sel = False
                self.buttons[(i + step) % len(self.buttons)].sel = True
                return
        self.buttons[0].sel = True

    def on_draw(self):
        veil = pygame.Surface(self.game.canvas.get_size(), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 160))
        self.game.canvas.blit(veil, (0, 0))
        pygame.draw.rect(self.game.canvas, (18, 18, 26), self.box, border_radius=10)
        pygame.draw.rect(self.game.canvas, (90, 86, 120), self.box, 3, border_radius=10)
        self.game.canvas.blit(self.title,
                              self.title.get_rect(midtop=(self.box.centerx,
                                                          self.box.y + 16)))
        for b in self.buttons:
            b.on_draw()

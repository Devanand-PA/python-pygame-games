"""Level select overlay: a race's levels, with locked ones greyed out."""
import pygame

from core import savestate
from core.content import get_content
from core.scene import Scene
from gui.widgets import Button


class Scene(Scene):
    scene_type = "menu"

    def __init__(self, game, race):
        super().__init__(game)
        self.content = get_content()
        self.race = race or {}
        self.levels = self.content.race_levels(self.race)
        self.box = pygame.Rect(0, 0, 560, 150 + 64 * max(1, len(self.levels)) + 70)
        self.box.center = (game.canvas.get_width() // 2,
                           game.canvas.get_height() // 2)
        self.title = game.fonts["big"].render(
            "{} - Select Level".format(self.race.get("name", "Campaign")),
            True, tuple(self.race.get("color") or (250, 250, 240)))

        completed = savestate.levels_completed(game.user or "Player")
        self.buttons = []
        y = self.box.y + 86
        for idx, level in enumerate(self.levels):
            unlocked = (idx == 0) or (self.levels[idx - 1]["id"] in completed)
            if level["id"] in completed:
                suffix = "  (cleared)"
            elif unlocked:
                suffix = ""
            else:
                suffix = "  (locked)"
            btn = Button(game, (self.box.x + 40, y), (self.box.width - 80, 52),
                         text="{} - {}{}".format(idx + 1, level.get("name", level["id"]),
                                                 suffix),
                         disabled=not unlocked)
            btn.level_id = level["id"]
            if unlocked:
                btn.function = self._make_launcher(btn)
                if not any(b.sel for b in self.buttons):
                    btn.sel = True
            self.buttons.append(btn)
            y += 64
        self.back_btn = Button(game, (self.box.x + 40, y + 6),
                               (self.box.width - 80, 44),
                               text="Back", function=self.close_overlay)
        self.buttons.append(self.back_btn)

    def _make_launcher(self, btn):
        def launch():
            self._launch(btn.level_id)
        return launch

    def _launch(self, level_id):
        from engine.game_scene import GameScene
        if self in self.game.subscenes:
            self.game.subscenes.remove(self)
        self.game.scene = GameScene(self.game, level_id)

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
            elif event.key in (pygame.K_UP, pygame.K_DOWN):
                playable = [b for b in self.buttons if b.function]
                step = -1 if event.key == pygame.K_UP else 1
                for i, b in enumerate(playable):
                    if b.sel:
                        b.sel = False
                        playable[(i + step) % len(playable)].sel = True
                        break
                else:
                    if playable:
                        playable[0].sel = True
        elif event.type == pygame.MOUSEMOTION:
            for b in self.buttons:
                if b.function:
                    b.sel = b.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            for b in self.buttons:
                if b.function and b.rect.collidepoint(event.pos):
                    self.game.play("click", 0.4)
                    b.function()
                    return

    def on_draw(self):
        veil = pygame.Surface(self.game.canvas.get_size(), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 160))
        self.game.canvas.blit(veil, (0, 0))
        pygame.draw.rect(self.game.canvas, (18, 18, 26), self.box, border_radius=10)
        pygame.draw.rect(self.game.canvas, (90, 86, 120), self.box, 3, border_radius=10)
        self.game.canvas.blit(self.title,
                              self.title.get_rect(midtop=(self.box.centerx,
                                                          self.box.y + 18)))
        for b in self.buttons:
            b.on_draw()

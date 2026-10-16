"""User selection overlay: pick an existing user or type a new name.

Fixes vs the old scene:
  - no crash when the user list is empty (fresh install)
  - no crash when the save location is read-only (falls back inside savestate)
"""
import pygame

from core import savestate
from core.scene import Scene
from gui.widgets import InputBox, ListBox


class Scene(Scene):
    scene_type = "menu"

    def __init__(self, game, users, next_scene="menus.career_menu"):
        super().__init__(game)
        self.next_scene = next_scene
        self.box = pygame.Rect(0, 0, 560, 420)
        self.box.center = (self.game.canvas.get_width() // 2,
                           self.game.canvas.get_height() // 2)

        self.title = game.fonts["big"].render("Enter User Name", True,
                                              (250, 250, 240))
        self.input = InputBox(game, (self.box.x + 30, self.box.y + 70),
                              (self.box.width - 60,), font_size=40, sel=True)
        self.userlist = ListBox(game, (self.box.x + 30, self.input.rect.bottom + 16),
                                (self.box.width - 60,
                                 self.box.height - 150),
                                users or [], sel=False)
        self.hint = game.fonts["small"].render(
            "Type a name (Enter to confirm) - or pick one from the list - Esc to cancel",
            True, (200, 200, 200))

    # ---------------------------------------------------------------- actions
    def confirm(self):
        name = self.input.text.strip()
        if not name:
            self.game.play("error", 0.5)
            return
        try:
            savestate.create_user(name)
        except ValueError:
            self.game.play("error", 0.5)
            return
        self.game.set_user(name)
        self.game.play("place", 0.5)
        self.close_and_continue()

    def close_and_continue(self):
        # remove this overlay from the stack first
        if self in self.game.subscenes:
            self.game.subscenes.remove(self)
        if self.next_scene:
            import importlib
            module = importlib.import_module(self.next_scene)
            self.game.scene = module.Scene(self.game)

    # ---------------------------------------------------------------- events
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.close_overlay()
                return
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.confirm()
                return
            self.input.handle_event(event)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.input.rect.collidepoint(event.pos):
                self.input.sel = True
                self.userlist.sel = False
            elif self.userlist.rect.collidepoint(event.pos):
                self.userlist.handle_event(event)
                if self.userlist.sel_text:
                    self.input.set_text(self.userlist.sel_text)
        elif event.type == pygame.MOUSEMOTION:
            if self.userlist.rect.collidepoint(event.pos):
                self.userlist.handle_event(event)
        elif event.type == pygame.MOUSEWHEEL:
            if self.userlist.rect.collidepoint(event.pos):
                self.userlist.handle_event(event)

    def on_draw(self):
        # dim whatever is underneath
        veil = pygame.Surface(self.game.canvas.get_size(), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 160))
        self.game.canvas.blit(veil, (0, 0))

        pygame.draw.rect(self.game.canvas, (18, 18, 26), self.box, border_radius=10)
        pygame.draw.rect(self.game.canvas, (90, 86, 120), self.box, 3, border_radius=10)
        self.game.canvas.blit(self.title,
                              self.title.get_rect(midtop=(self.box.centerx,
                                                          self.box.y + 18)))
        self.input.on_draw()
        if self.userlist.items:
            self.userlist.on_draw()
        self.game.canvas.blit(self.hint,
                              self.hint.get_rect(midbottom=(self.box.centerx,
                                                            self.box.bottom - 12)))

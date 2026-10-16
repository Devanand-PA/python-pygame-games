"""User selection overlay: pick a saved user or type a new name.

The typed name is the single source of truth for "confirm", so the old trap
where a saved user looked selected while the box stayed empty (Enter then did
nothing) can't happen.  Layout is derived from the text/widget sizes so nothing
is clipped or overlapped, and the screen works with zero users and on read-only
save roots.
"""
import pygame

from core import savestate
from core.scene import Scene
from gui.widgets import Button, InputBox, ListBox

PANEL_W = 580
PAD = 28
MAX_ROWS = 5
DOUBLE_CLICK_MS = 400


class Scene(Scene):
    scene_type = "menu"

    def __init__(self, game, users, next_scene="menus.career_menu"):
        super().__init__(game)
        self.next_scene = next_scene
        self.users = list(users or [])
        fonts = game.fonts
        small = fonts["small"]

        self.title = fonts["big"].render("Choose a User", True, (250, 250, 240))
        self.subtitle = small.render(
            "Pick a saved user or type a new name.", True, (188, 188, 204))
        self.label_name = small.render("User name", True, (206, 206, 216))
        self.label_saved = small.render("Saved users", True, (206, 206, 216))

        input_h = pygame.font.Font(None, 36).get_height() + 12
        list_h = max(1, min(len(self.users) or 1, MAX_ROWS)) * (
            fonts["default"].get_height() + 8) + 8
        btn_h = 46

        title_h = self.title.get_height()
        sub_h = self.subtitle.get_height()
        lab_h = self.label_name.get_height()

        height = (PAD + title_h + 6 + sub_h + 22 + lab_h + 6 + input_h
                  + 18 + lab_h + 6 + list_h + 22 + btn_h + 14 + sub_h + PAD)
        self.box = pygame.Rect(0, 0, PANEL_W, height)
        self.box.center = (game.canvas.get_width() // 2,
                           game.canvas.get_height() // 2)

        x = self.box.x + PAD
        cw = PANEL_W - 2 * PAD
        y = self.box.y + PAD

        self.title_pos = (self.box.centerx, y)
        y += title_h + 6
        self.subtitle_pos = (self.box.centerx, y)
        y += sub_h + 22

        self.name_label_pos = (x, y)
        y += lab_h + 6
        self.input = InputBox(game, (x, y), (cw,), font_size=36, sel=True,
                              placeholder="type a new name")
        y = self.input.rect.bottom + 18

        self.saved_label_pos = (x, y)
        y += lab_h + 6
        self.userlist = ListBox(game, (x, y), (cw, list_h), self.users, sel=False)
        y = self.userlist.rect.bottom + 22

        gap = 14
        bw = (cw - gap) // 2
        self.play_btn = Button(game, (x, y), (bw, btn_h), text="Play",
                               function=self.confirm)
        self.cancel_btn = Button(game, (x + bw + gap, y), (bw, btn_h),
                                 text="Cancel", function=self.close_overlay)
        self.buttons = [self.play_btn, self.cancel_btn]
        self.play_btn.sel = True
        y += btn_h + 14

        self.status = ""
        self.status_pos = (self.box.centerx, y + sub_h // 2)
        self._last_click_ms = 0
        self._last_click_row = None

    # ---------------------------------------------------------------- actions
    def confirm(self):
        name = self.input.text.strip()
        if not name:
            self.status = "Type a name, or click a saved user below."
            self.game.play("error", 0.5)
            return
        try:
            savestate.create_user(name)
        except ValueError:
            self.status = "That name can't be used."
            self.game.play("error", 0.5)
            return
        self.game.set_user(name)
        self.game.play("place", 0.5)
        self.close_and_continue()

    def close_and_continue(self):
        if self in self.game.subscenes:
            self.game.subscenes.remove(self)
        if self.next_scene:
            import importlib
            module = importlib.import_module(self.next_scene)
            self.game.scene = module.Scene(self.game)

    def _pick(self, name):
        self.input.set_text(name)
        self.input.sel = True
        self.status = ""

    def _activate_row(self):
        name = self.userlist.sel_text
        if name:
            self._pick(name)
            self.confirm()

    # ---------------------------------------------------------------- events
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.close_overlay()
                return
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.confirm()
                return
            if event.key in (pygame.K_UP, pygame.K_DOWN):
                if self.userlist.items:
                    self.userlist.handle_event(event)
                    if self.userlist.sel_text:
                        self._pick(self.userlist.sel_text)
                return
            self.input.handle_event(event)
            self.status = ""
        elif event.type == pygame.MOUSEMOTION:
            self.userlist.handle_event(event)
            for b in self.buttons:
                b.sel = b.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.userlist.rect.collidepoint(event.pos):
                self.userlist.handle_event(event)
                if self.userlist.sel_text:
                    self._pick(self.userlist.sel_text)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.input.rect.collidepoint(event.pos):
                self.input.sel = True
                return
            if self.userlist.rect.collidepoint(event.pos):
                now = pygame.time.get_ticks()
                row = self.userlist.row_at(event.pos)
                if (row is not None and row == self._last_click_row
                        and now - self._last_click_ms <= DOUBLE_CLICK_MS):
                    self._last_click_ms = 0
                    self._last_click_row = None
                    self._activate_row()
                else:
                    self._last_click_ms = now
                    self._last_click_row = row
                return
            for b in self.buttons:
                if b.rect.collidepoint(event.pos) and b.function:
                    self.game.play("click", 0.4)
                    b.function()
                    return
        elif event.type == pygame.MOUSEWHEEL:
            if self.userlist.rect.collidepoint(event.pos):
                self.userlist.handle_event(event)

    # ---------------------------------------------------------------- drawing
    def _draw_empty_state(self):
        r = self.userlist.rect
        pygame.draw.rect(self.game.canvas, (14, 14, 18), r, border_radius=3)
        pygame.draw.rect(self.game.canvas, (120, 120, 120), r, 2, border_radius=3)
        msg = self.game.fonts["small"].render(
            "No saved users yet - type a name and press Play.",
            True, (150, 150, 160))
        self.game.canvas.blit(msg, msg.get_rect(center=r.center))

    def on_draw(self):
        veil = pygame.Surface(self.game.canvas.get_size(), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 170))
        self.game.canvas.blit(veil, (0, 0))

        pygame.draw.rect(self.game.canvas, (18, 18, 26), self.box, border_radius=10)
        pygame.draw.rect(self.game.canvas, (90, 86, 120), self.box, 3,
                         border_radius=10)

        self.game.canvas.blit(self.title, self.title.get_rect(midtop=self.title_pos))
        self.game.canvas.blit(self.subtitle,
                              self.subtitle.get_rect(midtop=self.subtitle_pos))
        self.game.canvas.blit(self.label_name, self.name_label_pos)

        name = self.input.text.strip()
        self.play_btn.set_text("Play as {}".format(name) if name else "Play")
        self.input.on_draw()

        self.game.canvas.blit(self.label_saved, self.saved_label_pos)
        if self.userlist.items:
            self.userlist.on_draw()
        else:
            self._draw_empty_state()

        for b in self.buttons:
            b.on_draw()
        if self.status:
            surf = self.game.fonts["small"].render(self.status, True, (240, 120, 120))
            self.game.canvas.blit(surf, surf.get_rect(center=self.status_pos))

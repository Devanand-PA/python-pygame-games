"""Shared menu plumbing: keyboard navigation + hover + click for button lists."""
import pygame

from gui.widgets import Button


class MenuPage:
    """Mixin for scenes built around a vertical list of selectable buttons."""

    def _make_menu_buttons(self, defs, box, pad=10, height=52):
        """defs: list of dicts {name, text, function?, disabled?}"""
        buttons = []
        y = box.y + pad
        for d in defs:
            btn = Button(self.game,
                         (box.x + pad, y),
                         (box.width - 2 * pad, height),
                         text=d.get("text", d["name"]),
                         disabled=d.get("disabled", False))
            btn.name = d["name"]
            btn.function = d.get("function")
            buttons.append(btn)
            y += height + pad
        box.height = (y - box.y) + pad - 10
        if buttons:
            buttons[0].sel = True
        return buttons

    def menu_hover(self, buttons, pos):
        changed = False
        for b in buttons:
            if b.disabled or not b.visible:
                continue
            if b.rect.collidepoint(pos) and not b.sel:
                for other in buttons:
                    other.sel = False
                b.sel = True
                changed = True
        return changed

    def menu_click(self, buttons, pos):
        for b in buttons:
            if b.disabled or not b.visible:
                continue
            if b.rect.collidepoint(pos):
                self.game.play("click", 0.4)
                if b.function:
                    b.function()
                return b
        return None

    def menu_key(self, buttons, event):
        """Return the activated button on Enter, else None."""
        selectable = [b for b in buttons if not b.disabled and b.visible]
        if not selectable:
            return None
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            for b in selectable:
                if b.sel:
                    self.game.play("click", 0.4)
                    if b.function:
                        b.function()
                    return b
            selectable[0].sel = True
            return None
        step = 0
        if event.key == pygame.K_UP:
            step = -1
        elif event.key == pygame.K_DOWN:
            step = 1
        if step:
            for i, b in enumerate(selectable):
                if b.sel:
                    b.sel = False
                    selectable[(i + step) % len(selectable)].sel = True
                    break
            else:
                selectable[0].sel = True
        return None

    def draw_menu_box(self, box, color=(12, 12, 16)):
        pygame.draw.rect(self.game.canvas, color, box, border_radius=8)
        pygame.draw.rect(self.game.canvas, (70, 66, 90), box, 3, border_radius=8)

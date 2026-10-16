"""Reusable GUI widgets: Button, InputBox, ListBox.

All widgets draw onto game.canvas and take the Game instance for fonts.
Fixes vs the old utils/gui_elements.py:
  - ListBox no longer crashes on an empty list (IndexError on sel_text)
  - Button keeps a stable hit rect; selection colors use bool indexing
  - InputBox trimmed to sane cursor logic
"""
import pygame


class Button:
    def __init__(self, game, coords, size, text="", font=None,
                 fg=(20, 20, 20), bg=(104, 104, 20), bg_sel=(200, 200, 40),
                 disabled=False, text_scale=1.0, function=None):
        self.game = game
        self.coords = list(coords)
        self.size = list(size)
        self.text = text
        self.font = font or game.fonts["default"]
        self.fg = fg
        self.bg = bg
        self.bg_sel = bg_sel
        self.sel = False
        self.disabled = disabled
        self.visible = True
        self.text_scale = text_scale
        self.function = function
        self.rect = pygame.Rect(self.coords[0], self.coords[1],
                                self.size[0], self.size[1])

    def set_text(self, text):
        self.text = text

    def on_resize(self):
        self.rect = pygame.Rect(self.coords[0], self.coords[1],
                                self.size[0], self.size[1])

    def on_draw(self):
        if not self.visible:
            return
        color = self.bg_sel if self.sel else self.bg
        if self.disabled:
            dim = tuple(c // 2 for c in color)
            pygame.draw.rect(self.game.canvas, dim, self.rect, border_radius=4)
            fg = (110, 110, 110)
        else:
            pygame.draw.rect(self.game.canvas, color, self.rect, border_radius=4)
            if self.sel:
                pygame.draw.rect(self.game.canvas, (250, 250, 210), self.rect,
                                 2, border_radius=4)
            fg = self.fg
        if self.text:
            size = self.font.size(self.text)
            scale = min(1.0, (self.size[0] - 16) / size[0]) * self.text_scale
            if scale < 1.0:
                rendered = self.font.render(self.text, True, fg)
                w = max(1, int(size[0] * scale))
                h = max(1, int(size[1] * scale))
                rendered = pygame.transform.smoothscale(rendered, (w, h))
            else:
                rendered = self.font.render(self.text, True, fg)
            self.game.canvas.blit(
                rendered,
                rendered.get_rect(center=self.rect.center))


class InputBox:
    """Single-line text field with a scrolling window around the cursor."""

    def __init__(self, game, coords, size, font=None, font_size=0,
                 sel=False, fg=(240, 240, 240)):
        self.game = game
        self.coords = list(coords)
        if font or font_size:
            self.font = font or pygame.font.Font(None, font_size or 32)
        else:
            self.font = game.fonts["default"]
        self.size = [size[0], self.font.get_height() + 10]
        self.sel = sel
        self.text = ""
        self.curpos = 0                    # cursor index inside text
        self.d_i = [0, 0]                  # visible slice [start, end]
        self.pad_x = self.font.size(">>")[0]
        self.fg = fg
        self.rect = pygame.Rect(self.coords[0], self.coords[1],
                                self.size[0], self.size[1])

    def on_resize(self):
        self.rect = pygame.Rect(self.coords[0], self.coords[1],
                                self.size[0], self.size[1])

    def set_text(self, text):
        self.text = text
        self.curpos = len(text)
        self.d_i = [0, len(text)]

    def _adjust_slice(self):
        width = self.rect.width - 2 * self.pad_x
        # grow the visible slice to fill the box
        while (self.d_i[1] < len(self.text)
               and self.font.size(self.text[self.d_i[0]:self.d_i[1] + 1])[0] <= width):
            self.d_i[1] += 1
        # shrink it if too wide
        while (self.d_i[1] > self.d_i[0]
               and self.font.size(self.text[self.d_i[0]:self.d_i[1]])[0] > width):
            self.d_i[1] -= 1
        # keep the cursor inside the slice
        while self.curpos < self.d_i[0]:
            self.d_i[0] -= 1
            while (self.d_i[1] > self.d_i[0]
                   and self.font.size(self.text[self.d_i[0]:self.d_i[1]])[0] > width):
                self.d_i[1] -= 1
        while self.curpos > self.d_i[1]:
            self.d_i[1] += 1
            while (self.d_i[1] - self.d_i[0] > 1
                   and self.font.size(self.text[self.d_i[0]:self.d_i[1]])[0] > width):
                self.d_i[0] += 1

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        if event.unicode and event.unicode.isprintable():
            self.text = self.text[:self.curpos] + event.unicode + self.text[self.curpos:]
            self.curpos += 1
        elif event.key == pygame.K_LEFT:
            self.curpos = max(0, self.curpos - 1)
        elif event.key == pygame.K_RIGHT:
            self.curpos = min(len(self.text), self.curpos + 1)
        elif event.key == pygame.K_BACKSPACE:
            if self.curpos > 0:
                self.text = self.text[:self.curpos - 1] + self.text[self.curpos:]
                self.curpos -= 1
        elif event.key == pygame.K_HOME:
            self.curpos = 0
        elif event.key == pygame.K_END:
            self.curpos = len(self.text)
        self._adjust_slice()

    def on_draw(self):
        pygame.draw.rect(self.game.canvas, (14, 14, 18), self.rect, border_radius=3)
        pygame.draw.rect(self.game.canvas,
                         (235, 235, 210) if self.sel else (120, 120, 120),
                         self.rect, 2, border_radius=3)
        visible = self.text[self.d_i[0]:self.d_i[1]]
        rendered = self.font.render(visible, True, self.fg)
        self.game.canvas.blit(rendered, (self.rect.x + self.pad_x,
                                         self.rect.centery - rendered.get_height() // 2))
        if self.sel and (pygame.time.get_ticks() % 1000) < 600:
            cursor_x = self.rect.x + self.pad_x + self.font.size(
                self.text[self.d_i[0]:self.curpos])[0]
            pygame.draw.line(self.game.canvas, self.fg,
                             (cursor_x, self.rect.y + 3),
                             (cursor_x, self.rect.bottom - 3), 2)


class ListBox:
    """Scrollable single-selection list. Empty lists are fine (sel_text=None)."""

    def __init__(self, game, coords, size, items, sel=False,
                 fg=(20, 20, 20), bg=(60, 60, 60), bg_sel=(200, 200, 40)):
        self.game = game
        self.coords = list(coords)
        self.size = list(size)
        self.items = list(items)
        self.font = game.fonts["default"]
        self.row_h = self.font.get_height() + 8
        self.max_rows = max(1, (self.size[1] - 8) // self.row_h)
        self.scroll = 0            # first visible row
        self.curr_sel = 0          # absolute selection index
        self.sel = sel
        self.fg = fg
        self.bg = bg
        self.bg_sel = bg_sel
        self.rect = pygame.Rect(self.coords[0], self.coords[1],
                                self.size[0], self.size[1])
        self.sel_text = self.items[self.curr_sel] if self.items else None

    def on_resize(self):
        self.rect = pygame.Rect(self.coords[0], self.coords[1],
                                self.size[0], self.size[1])

    def set_items(self, items):
        self.items = list(items)
        self.curr_sel = 0
        self.scroll = 0
        self.sel_text = self.items[0] if self.items else None

    def _clamp(self):
        if not self.items:
            self.curr_sel = 0
            self.scroll = 0
            self.sel_text = None
            return
        self.curr_sel = max(0, min(self.curr_sel, len(self.items) - 1))
        if self.curr_sel < self.scroll:
            self.scroll = self.curr_sel
        if self.curr_sel >= self.scroll + self.max_rows:
            self.scroll = self.curr_sel - self.max_rows + 1
        self.scroll = max(0, min(self.scroll, max(0, len(self.items) - self.max_rows)))
        self.sel_text = self.items[self.curr_sel]

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(event.pos):
            self.scroll = max(0, self.scroll - event.y)
            self._clamp()
        elif event.type == pygame.MOUSEMOTION:
            for row in range(self.max_rows):
                idx = self.scroll + row
                if idx >= len(self.items):
                    break
                row_rect = pygame.Rect(self.rect.x + 4,
                                       self.rect.y + 4 + row * self.row_h,
                                       self.rect.width - 8, self.row_h)
                if row_rect.collidepoint(event.pos):
                    self.curr_sel = idx
                    self._clamp()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_DOWN:
                self.curr_sel += 1
                self._clamp()
            elif event.key == pygame.K_UP:
                self.curr_sel -= 1
                self._clamp()

    def on_draw(self):
        pygame.draw.rect(self.game.canvas, (14, 14, 18), self.rect, border_radius=3)
        pygame.draw.rect(self.game.canvas, (120, 120, 120), self.rect, 2,
                         border_radius=3)
        for row in range(self.max_rows):
            idx = self.scroll + row
            if idx >= len(self.items):
                break
            row_rect = pygame.Rect(self.rect.x + 4,
                                   self.rect.y + 4 + row * self.row_h,
                                   self.rect.width - 8, self.row_h)
            color = self.bg_sel if idx == self.curr_sel else self.bg
            pygame.draw.rect(self.game.canvas, color, row_rect, border_radius=3)
            text = self.font.render(str(self.items[idx]), True, self.fg)
            self.game.canvas.blit(text, (row_rect.x + 8,
                                         row_rect.centery - text.get_height() // 2))

"""Editor widget toolkit for the standalone level designer.

Small, focused widgets drawn onto a plain pygame surface.  The designer is not
the game, so there is no scene stack here -- just a form of fields and lists
that read and write Python values.
"""
import pygame

from core import paths
from core.content import ANIMATION_STATES
from engine import art

# --- palette ---------------------------------------------------------------
BG = (22, 22, 30)
PANEL = (34, 34, 46)
PANEL2 = (42, 42, 56)
EDGE = (78, 76, 104)
TEXT = (232, 232, 236)
DIM = (156, 156, 172)
ACCENT = (96, 150, 220)
OK = (110, 190, 120)
BAD = (220, 110, 110)
FIELD_BG = (16, 16, 22)
FIELD_EDGE = (110, 110, 130)
FIELD_FOCUS = (235, 235, 210)


class Ctx:
    """Minimal game-like context passed to widgets (canvas + fonts)."""

    def __init__(self, canvas, fonts):
        self.canvas = canvas
        self.fonts = fonts
        self.modal = None
        self.status = ""
        # The one field allowed to show a caret.  Text fields claim it on
        # focus; the app clears it when a click lands anywhere else, so two
        # boxes can never look focused at once.
        self.focus_owner = None

    def play(self, *args, **kwargs):    # widgets call this; designer is silent
        pass

    def open_modal(self, modal):
        self.modal = modal

    def close_modal(self):
        self.modal = None


# ---------------------------------------------------------------------------
# field base
# ---------------------------------------------------------------------------
class Field:
    height = 30
    label_w = 150

    def __init__(self, ctx, rect, label="", label_w=None):
        self.ctx = ctx
        self.rect = pygame.Rect(rect)
        self.label = label
        self.label_w = label_w if label_w is not None else self.label_w
        self.focused = False

    # -- focus bookkeeping ---------------------------------------------------
    def _claim_focus(self):
        """Become the app's one focused field, defocusing the previous one."""
        prev = getattr(self.ctx, "focus_owner", None)
        if prev is not None and prev is not self \
                and getattr(prev, "focused", False):
            prev.focused = False
        self.ctx.focus_owner = self

    @staticmethod
    def defocus_owner(ctx):
        """Drop the current focus owner (used when a click lands elsewhere)."""
        owner = getattr(ctx, "focus_owner", None)
        if owner is not None:
            owner.focused = False
            ctx.focus_owner = None

    @property
    def box_rect(self):
        return pygame.Rect(self.rect.x + self.label_w, self.rect.y + 2,
                           self.rect.width - self.label_w, self.rect.height - 4)

    def set_rect(self, rect):
        self.rect = pygame.Rect(rect)

    def handle_event(self, event):
        return False

    def draw(self, canvas):
        raise NotImplementedError

    def _draw_label(self, canvas):
        if self.label:
            surf = self.ctx.fonts["small"].render(self.label, True, DIM)
            canvas.blit(surf, (self.rect.x, self.rect.centery - surf.get_height() // 2))


def _draw_box(canvas, rect, focused):
    pygame.draw.rect(canvas, FIELD_BG, rect, border_radius=3)
    pygame.draw.rect(canvas, FIELD_FOCUS if focused else FIELD_EDGE, rect, 2,
                     border_radius=3)


# ---------------------------------------------------------------------------
# text / number fields
# ---------------------------------------------------------------------------
# Clipboard: prefer the system clipboard via pygame.scrap, fall back to an
# in-process string so copy/paste always works (headless, odd platforms,
# uninitialised scrap -- none of that may ever raise).
_CLIPBOARD = ""          # internal fallback clipboard
_SCRAP_TRIED = False


def _scrap_put(text):
    """Copy *text* to the system clipboard; True on success."""
    global _SCRAP_TRIED, _CLIPBOARD
    _CLIPBOARD = text
    try:
        import pygame.scrap
        if not pygame.scrap.get_init():
            pygame.scrap.init()
        pygame.scrap.put_text(text)
        return True
    except Exception:                                  # noqa: BLE001
        return False
    finally:
        _SCRAP_TRIED = True


def _scrap_get():
    """Read the system clipboard, falling back to the internal one."""
    global _CLIPBOARD
    try:
        import pygame.scrap
        if pygame.scrap.get_init():
            text = pygame.scrap.get_text()
            if text:
                return text
    except Exception:                                  # noqa: BLE001
        pass
    return _CLIPBOARD


def wrap_text(text, font, max_width):
    """Word-wrap ``text`` to ``font``; returns a list of lines (never empty).

    Honours explicit ``\\n`` paragraph breaks.  Used by the multiline field and
    by anywhere else that needs to draw flowing text.
    """
    lines = []
    for paragraph in str(text).split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            trial = f"{current} {word}"
            if font.size(trial)[0] <= max_width:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines or [""]


class TextField(Field):
    """A single- or multi-line text box with copy/paste.

    Keyboard (while focused): arrows move the caret (holding repeats, thanks
    to the app-wide ``pygame.key.set_repeat``), Home/End jump, Backspace and
    Delete edit, ``Ctrl+C`` / ``Ctrl+X`` / ``Ctrl+V`` copy, cut and paste.
    Multiline fields also accept Enter (newline) and Up/Down to move between
    *visual* (wrapped) lines.
    """

    REPEAT_NOTE = "key repeat comes from pygame.key.set_repeat in app.py"

    def __init__(self, ctx, rect, label="", value="", label_w=None,
                 allow="all", multiline=False):
        super().__init__(ctx, rect, label, label_w)
        self.allow = allow               # all | int | float
        self.multiline = bool(multiline)
        self.text = "" if value is None else str(value)
        self.cursor = len(self.text)
        self.scroll_line = 0             # first visible visual line (multiline)

    # -- value --------------------------------------------------------------
    def set_value(self, value):
        self.text = "" if value is None else str(value)
        self.cursor = len(self.text)     # fresh text -> caret at its end
        self.scroll_line = 0

    @property
    def value(self):
        return self.text.strip()

    def _accepts(self, ch):
        if self.allow == "int":
            return ch.isdigit() or (ch == "-" and self.cursor == 0)
        if self.allow == "float":
            return ch.isdigit() or ch in ".-"
        return True

    def _insert(self, chunk):
        """Insert *chunk* at the caret, honouring the field's char filter."""
        kept = ""
        for ch in chunk:
            if ch == "\n":
                if self.multiline:
                    kept += ch
            elif self._accepts(ch):
                kept += ch
        if not kept:
            return
        self.text = self.text[:self.cursor] + kept + self.text[self.cursor:]
        self.cursor += len(kept)

    # -- clipboard ----------------------------------------------------------
    def _copy(self):
        return _scrap_put(self.text)

    def _cut(self):
        self._copy()
        self.text = ""
        self.cursor = 0

    def _paste(self):
        self._insert(_scrap_get())

    # -- visual-line mapping (multiline) ------------------------------------
    def _visual_lines(self):
        """[(line_text, start_index_in_text), ...] for the wrapped display."""
        font = self.ctx.fonts["small"]
        width = max(10, self.box_rect.width - 10)
        out = []
        start = 0
        for paragraph in self.text.split("\n"):
            words = paragraph.split()
            if not words:
                out.append(("", start))            # empty (blank) line
                start += 1                          # the "\n"
                continue
            pos = start
            current = ""
            for word in words:
                trial = word if not current else f"{current} {word}"
                if current and font.size(trial)[0] > width:
                    out.append((current, pos))
                    pos += len(current) + 1        # + the joining space
                    current = word
                else:
                    current = trial
            out.append((current, pos))
            start = pos + len(current) + 1         # + the "\n"
        return out or [(" ", 0)]

    def _line_of_cursor(self, lines):
        for index in range(len(lines)):
            line_text, line_start = lines[index]
            end = line_start + len(line_text)
            # a caret sitting on the wrap boundary belongs to the earlier line
            if index + 1 < len(lines) and self.cursor == end + 1 \
                    and lines[index + 1][1] == end + 1:
                continue
            if line_start <= self.cursor <= end:
                return index
        return len(lines) - 1

    def _move_line(self, step):
        lines = self._visual_lines()
        index = self._line_of_cursor(lines)
        target = max(0, min(len(lines) - 1, index + step))
        if target == index:
            return
        line_text, line_start = lines[target]
        col = self.cursor - lines[index][1]
        self.cursor = min(line_start + len(line_text), line_start + max(0, col))

    # -- events -------------------------------------------------------------
    def _caret_from_click(self, pos):
        """Put the caret at the character the user clicked on."""
        box = self.box_rect
        font = self.ctx.fonts["small"]
        char_w = max(1, font.size("M")[0])
        if not self.multiline:
            dx = pos[0] - (box.x + 5)
            # mirror the draw scissor: it keeps the *caret's* prefix inside
            # the box, so exactly the characters on screen are hit-testable
            start = 0
            while (start < self.cursor
                   and font.size(self.text[start:self.cursor])[0]
                   > box.width - 10):
                start += 1
            best, best_d = start, None
            for i in range(start, len(self.text) + 1):
                d = abs(font.size(self.text[start:i])[0] - dx)
                if best_d is None or d < best_d:
                    best, best_d = i, d
                if font.size(self.text[start:i])[0] - dx > char_w:
                    break
            self.cursor = best
            return
        lines = self._visual_lines()
        line_h = font.get_height() + 3
        max_lines = max(1, (box.height - 8) // line_h)
        row = self.scroll_line + int((pos[1] - (box.y + 4)) // line_h)
        row = max(0, min(len(lines) - 1, row))
        line_text, line_start = lines[row]
        dx = max(0, pos[0] - (box.x + 5))
        best, best_d = 0, None
        for i in range(len(line_text) + 1):
            d = abs(font.size(line_text[:i])[0] - dx)
            if best_d is None or d < best_d:
                best, best_d = i, d
            if font.size(line_text[:i])[0] - dx > char_w:
                break
        self.cursor = line_start + best
        # keep the clicked line on screen (same clamp the draw path applies)
        if row < self.scroll_line:
            self.scroll_line = row
        elif row >= self.scroll_line + max_lines:
            self.scroll_line = row - max_lines + 1

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.focused = self.box_rect.collidepoint(event.pos)
            if self.focused:
                self._claim_focus()
                self._caret_from_click(event.pos)
            return self.focused
        if event.type != pygame.KEYDOWN or not self.focused:
            return False
        ctrl = bool(event.mod & pygame.KMOD_CTRL)

        if ctrl and event.key in (pygame.K_c, pygame.K_x, pygame.K_v):
            if event.key == pygame.K_c:
                self._copy()
            elif event.key == pygame.K_x:
                self._cut()
            else:
                self._paste()
            return True
        if event.key == pygame.K_BACKSPACE:
            if self.cursor > 0:
                self.text = self.text[:self.cursor - 1] + self.text[self.cursor:]
                self.cursor -= 1
        elif event.key == pygame.K_DELETE:
            self.text = self.text[:self.cursor] + self.text[self.cursor + 1:]
        elif event.key == pygame.K_LEFT:
            self.cursor = max(0, self.cursor - 1)
        elif event.key == pygame.K_RIGHT:
            self.cursor = min(len(self.text), self.cursor + 1)
        elif event.key == pygame.K_UP and self.multiline:
            self._move_line(-1)
        elif event.key == pygame.K_DOWN and self.multiline:
            self._move_line(1)
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.multiline:
            self._insert("\n")
        elif event.key == pygame.K_HOME:
            if self.multiline:
                lines = self._visual_lines()
                self.cursor = lines[self._line_of_cursor(lines)][1]
            else:
                self.cursor = 0
        elif event.key == pygame.K_END:
            if self.multiline:
                lines = self._visual_lines()
                index = self._line_of_cursor(lines)
                self.cursor = lines[index][1] + len(lines[index][0])
            else:
                self.cursor = len(self.text)
        elif event.unicode and event.unicode.isprintable() and self._accepts(event.unicode):
            self._insert(event.unicode)
        else:
            return True
        return True

    # -- drawing ------------------------------------------------------------
    def _draw_single_line(self, canvas, box, font):
        text = self.text
        # keep the caret visible: drop characters from the left while the
        # prefix up to the caret would overflow, then scissor the right side
        start = 0
        while start < self.cursor and \
                font.size(text[start:self.cursor])[0] > box.width - 10:
            start += 1
        shown = text[start:]
        while shown and font.size(shown)[0] > box.width - 10:
            shown = shown[:-1]
        surf = font.render(shown, True, TEXT)
        canvas.blit(surf, (box.x + 5, box.centery - surf.get_height() // 2))
        if self.focused and (pygame.time.get_ticks() % 1000) < 550:
            cx = min(box.right - 5,
                     box.x + 5 + font.size(text[start:self.cursor])[0])
            pygame.draw.line(canvas, FIELD_FOCUS, (cx, box.y + 3),
                             (cx, box.bottom - 3), 2)

    def _draw_multiline(self, canvas, box, font):
        lines = self._visual_lines()
        line_h = font.get_height() + 3
        max_lines = max(1, (box.height - 8) // line_h)
        # vertical scroll: keep the caret's line on screen
        index = self._line_of_cursor(lines)
        if index < self.scroll_line:
            self.scroll_line = index
        elif index >= self.scroll_line + max_lines:
            self.scroll_line = index - max_lines + 1
        self.scroll_line = max(0, min(self.scroll_line, max(0, len(lines) - max_lines)))
        y = box.y + 4
        for line_text, _start in lines[self.scroll_line:self.scroll_line + max_lines]:
            if line_text:
                surf = font.render(line_text, True, TEXT)
                canvas.blit(surf, (box.x + 5, y))
            y += line_h
        if self.focused and (pygame.time.get_ticks() % 1000) < 550:
            line_text, line_start = lines[index]
            col = max(0, min(len(line_text), self.cursor - line_start))
            cx = min(box.right - 5,
                     box.x + 5 + font.size(line_text[:col])[0])
            cy = box.y + 4 + (index - self.scroll_line) * line_h
            pygame.draw.line(canvas, FIELD_FOCUS, (cx, cy),
                             (cx, min(box.bottom - 3, cy + font.get_height())), 2)

    def draw(self, canvas):
        self._draw_label(canvas)
        box = self.box_rect
        _draw_box(canvas, box, self.focused)
        font = self.ctx.fonts["small"]
        if self.multiline:
            self._draw_multiline(canvas, box, font)
        else:
            self._draw_single_line(canvas, box, font)


class MultilineField(TextField):
    """A TextField that wraps, grows tall and accepts Enter for newlines."""

    def __init__(self, ctx, rect, label="", value="", label_w=None):
        super().__init__(ctx, rect, label, value, label_w, multiline=True)

    @property
    def value(self):
        # keep leading newlines/indent (they are content here); trim only the
        # trailing whitespace the caret tends to leave behind
        return self.text.rstrip()


class IntField(TextField):
    def __init__(self, ctx, rect, label="", value=0, label_w=None, allow_negative=False):
        super().__init__(ctx, rect, label, value, label_w,
                         allow="int" if allow_negative else "int")
        self.allow_negative = allow_negative

    @property
    def value(self):
        try:
            return int(self.text.strip() or 0)
        except ValueError:
            return 0

    def set_value(self, value):
        super().set_value(int(value) if value is not None else 0)


class FloatField(TextField):
    def __init__(self, ctx, rect, label="", value=0.0, label_w=None):
        super().__init__(ctx, rect, label, value, label_w, allow="float")

    @property
    def value(self):
        try:
            return float(self.text.strip() or 0)
        except ValueError:
            return 0.0

    def set_value(self, value):
        super().set_value(round(float(value), 4) if value is not None else 0.0)


# ---------------------------------------------------------------------------
# checkbox / choice / color
# ---------------------------------------------------------------------------
class CheckField(Field):
    def __init__(self, ctx, rect, label="", value=False, label_w=None):
        super().__init__(ctx, rect, label, label_w)
        self.checked = bool(value)

    def set_value(self, value):
        self.checked = bool(value)

    @property
    def value(self):
        return self.checked

    def handle_event(self, event):
        if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.box_rect.collidepoint(event.pos)):
            self.checked = not self.checked
            return True
        return False

    def draw(self, canvas):
        self._draw_label(canvas)
        box = self.box_rect
        box.width = box.height
        pygame.draw.rect(canvas, FIELD_BG, box, border_radius=3)
        pygame.draw.rect(canvas, OK if self.checked else FIELD_EDGE, box, 2,
                         border_radius=3)
        if self.checked:
            pygame.draw.line(canvas, OK, (box.x + 5, box.centery),
                             (box.centerx, box.bottom - 7), 3)
            pygame.draw.line(canvas, OK, (box.centerx, box.bottom - 7),
                             (box.right - 5, box.y + 6), 3)


class ChoiceField(Field):
    def __init__(self, ctx, rect, label="", options=(), index=0, label_w=None):
        super().__init__(ctx, rect, label, label_w)
        self.options = list(options)
        self.index = max(0, min(index, max(0, len(self.options) - 1)))

    def set_value(self, value):
        if value in self.options:
            self.index = self.options.index(value)
        elif self.options:
            self.index = 0

    @property
    def value(self):
        return self.options[self.index] if self.options else None

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and self.box_rect.collidepoint(event.pos):
            if not self.options:
                return True
            self.index = (self.index - 1) % len(self.options) if event.button == 3 \
                else (self.index + 1) % len(self.options)
            return True
        if event.type == pygame.MOUSEWHEEL and self.box_rect.collidepoint(event.pos):
            if self.options:
                self.index = (self.index - event.y) % len(self.options)
            return True
        return False

    def draw(self, canvas):
        self._draw_label(canvas)
        box = self.box_rect
        _draw_box(canvas, box, False)
        text = str(self.value) if self.options else "-"
        surf = self.ctx.fonts["small"].render("{}   < >".format(text), True, TEXT)
        canvas.blit(surf, (box.x + 6, box.centery - surf.get_height() // 2))


class ColorField(Field):
    def __init__(self, ctx, rect, label="", value=None, label_w=None):
        super().__init__(ctx, rect, label, label_w)
        self.fields = []
        sw = 26
        gap = 6
        for i, channel in enumerate("RGB"):
            f = IntField(ctx, (0, 0, 0, 0), "", 0, label_w=0)
            self.fields.append(f)
        self.rect = pygame.Rect(rect)
        self._layout()

    def _layout(self):
        box = self.box_rect
        n = len(self.fields)
        cw = (box.width - 3 * 6 - 30) // n
        for i, f in enumerate(self.fields):
            r = pygame.Rect(box.x + i * (cw + 6), box.y, cw, box.height)
            f.set_rect(r)
            f.label_w = 0

    def set_rect(self, rect):
        super().set_rect(rect)
        self._layout()

    def set_value(self, value):
        value = value or [0, 0, 0]
        for f, v in zip(self.fields, value):
            f.set_value(v)

    @property
    def value(self):
        return [f.value for f in self.fields]

    def handle_event(self, event):
        for f in self.fields:
            if f.handle_event(event):
                return True
        return False

    def draw(self, canvas):
        self._draw_label(canvas)
        for f in self.fields:
            f.draw(canvas)
        box = self.box_rect
        sw = pygame.Rect(box.right - 26, box.y, 26, box.height)
        try:
            col = tuple(self.value)
        except Exception:      # noqa: BLE001
            col = (0, 0, 0)
        pygame.draw.rect(canvas, col, sw, border_radius=3)
        pygame.draw.rect(canvas, FIELD_EDGE, sw, 1, border_radius=3)


class TileField(Field):
    """A Kenney tile number: type it, preview it, or click to pick from a grid."""

    def __init__(self, ctx, rect, label="", value=226, label_w=None, optional=False):
        super().__init__(ctx, rect, label, label_w)
        self.optional = optional
        self.number = IntField(ctx, (0, 0, 0, 0), "", value, label_w=0)
        self._layout()

    def _layout(self):
        box = self.box_rect
        self.number.set_rect(pygame.Rect(box.x, box.y, box.width - 62, box.height))

    def set_rect(self, rect):
        super().set_rect(rect)
        self._layout()

    def set_value(self, value):
        self.number.set_value(-1 if value in (None, "none", "") else value)

    @property
    def value(self):
        n = self.number.value
        return None if (self.optional and n < 0) else n

    def handle_event(self, event):
        box = self.box_rect
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pick = pygame.Rect(box.right - 34, box.y, 34, box.height)
            clear = pygame.Rect(box.right - 60, box.y, 24, box.height)
            if pick.collidepoint(event.pos):
                self.ctx.open_modal(TilePicker(self.ctx, self._picked))
                return True
            if self.optional and clear.collidepoint(event.pos):
                self.number.set_value(-1)
                return True
        return self.number.handle_event(event)

    def _picked(self, tile):
        self.number.set_value(tile)

    def draw(self, canvas):
        self._draw_label(canvas)
        self.number.draw(canvas)
        box = self.box_rect
        pick = pygame.Rect(box.right - 34, box.y, 34, box.height)
        pygame.draw.rect(canvas, PANEL2, pick, border_radius=3)
        pygame.draw.rect(canvas, EDGE, pick, 1, border_radius=3)
        # preview
        n = self.number.value
        prev = pygame.Rect(box.right - 61, box.y, 26, box.height)
        if n is not None and n >= 0:
            try:
                img = art.scaled(art.tile(int(n)),
                                 (prev.height - 4, prev.height - 4), ("tile", int(n)))
                canvas.blit(img, img.get_rect(center=prev.center))
            except Exception:      # noqa: BLE001
                pass
        if self.optional:
            clear = pygame.Rect(box.right - 88, box.y, 24, box.height)
            pygame.draw.rect(canvas, PANEL2, clear, border_radius=3)
            pygame.draw.rect(canvas, EDGE, clear, 1, border_radius=3)
            surf = self.ctx.fonts["small"].render("x", True, BAD)
            canvas.blit(surf, surf.get_rect(center=clear.center))
        label = self.ctx.fonts["small"].render("pick", True, TEXT)
        canvas.blit(label, label.get_rect(center=pick.center))


# ---------------------------------------------------------------------------
# image path field (type a path or pick a PNG under assets/)
# ---------------------------------------------------------------------------
class ImageField(Field):
    """A PNG path relative to ``assets/``: type it, or pick one from disk."""

    def __init__(self, ctx, rect, label="", value="", label_w=None):
        super().__init__(ctx, rect, label, label_w)
        self.text = TextField(ctx, (0, 0, 0, 0), "", value, label_w=0)
        self._layout()

    def _layout(self):
        box = self.box_rect
        self.text.set_rect(pygame.Rect(box.x, box.y, max(20, box.width - 52),
                                       box.height))

    def set_rect(self, rect):
        super().set_rect(rect)
        self._layout()

    def set_value(self, value):
        self.text.set_value(value or "")

    @property
    def value(self):
        return self.text.value

    def handle_event(self, event):
        box = self.box_rect
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pick = pygame.Rect(box.right - 34, box.y, 34, box.height)
            if pick.collidepoint(event.pos):
                self.ctx.open_modal(ImagePicker(self.ctx, self.text.set_value))
                return True
        return self.text.handle_event(event)

    def draw(self, canvas):
        self._draw_label(canvas)
        self.text.draw(canvas)
        box = self.box_rect
        pick = pygame.Rect(box.right - 34, box.y, 34, box.height)
        pygame.draw.rect(canvas, PANEL2, pick, border_radius=3)
        pygame.draw.rect(canvas, EDGE, pick, 1, border_radius=3)
        label = self.ctx.fonts["small"].render("png", True, TEXT)
        canvas.blit(label, label.get_rect(center=pick.center))
        # thumbnail
        thumb = pygame.Rect(box.right - 84, box.y, box.height, box.height)
        pygame.draw.rect(canvas, FIELD_BG, thumb, border_radius=3)
        pygame.draw.rect(canvas, FIELD_EDGE, thumb, 1, border_radius=3)
        if self.value:
            try:
                img = art.scaled(art.image(self.value),
                                 (thumb.height - 4, thumb.height - 4),
                                 ("image", self.value))
                canvas.blit(img, img.get_rect(center=thumb.center))
            except Exception:      # noqa: BLE001
                pass


# ---------------------------------------------------------------------------
# lists
# ---------------------------------------------------------------------------
class ScrollList:
    def __init__(self, ctx, rect, items=(), on_select=None, on_activate=None):
        self.ctx = ctx
        self.rect = pygame.Rect(rect)
        self.items = list(items)
        self.on_select = on_select
        self.on_activate = on_activate
        self.index = -1
        self.scroll = 0
        self.row_h = ctx.fonts["small"].get_height() + 10
        self._last_click = 0
        self._last_row = -1

    def set_items(self, items, keep=True):
        current = self.selected
        self.items = list(items)
        if keep and current in self.items:
            self.index = self.items.index(current)
        else:
            self.index = 0 if self.items else -1
        self._clamp()

    @property
    def selected(self):
        if 0 <= self.index < len(self.items):
            return self.items[self.index]
        return None

    def _max_rows(self):
        return max(1, (self.rect.height - 8) // self.row_h)

    def _clamp(self):
        if not self.items:
            self.index = -1
            self.scroll = 0
            return
        self.index = max(0, min(self.index, len(self.items) - 1))
        if self.index < self.scroll:
            self.scroll = self.index
        if self.index >= self.scroll + self._max_rows():
            self.scroll = self.index - self._max_rows() + 1
        self.scroll = max(0, min(self.scroll, max(0, len(self.items) - self._max_rows())))

    def _row_at(self, pos):
        if not self.rect.collidepoint(pos):
            return None
        row = (pos[1] - self.rect.y - 4) // self.row_h
        idx = self.scroll + row
        return idx if 0 <= idx < len(self.items) else None

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(
                getattr(event, "pos", (0, 0))):
            self.scroll = max(0, self.scroll - event.y)
            self._clamp()
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            idx = self._row_at(event.pos)
            if idx is None:
                return False
            now = pygame.time.get_ticks()
            double = (idx == self._last_row and now - self._last_click < 400)
            self._last_click, self._last_row = now, idx
            self.index = idx
            self._clamp()
            if self.on_select:
                self.on_select(self.selected)
            if double and self.on_activate:
                self.on_activate(self.selected)
            return True
        return False

    def draw(self, canvas):
        pygame.draw.rect(canvas, FIELD_BG, self.rect, border_radius=4)
        pygame.draw.rect(canvas, FIELD_EDGE, self.rect, 2, border_radius=4)
        for row in range(self._max_rows()):
            idx = self.scroll + row
            if idx >= len(self.items):
                break
            r = pygame.Rect(self.rect.x + 4, self.rect.y + 4 + row * self.row_h,
                            self.rect.width - 8, self.row_h)
            if idx == self.index:
                pygame.draw.rect(canvas, ACCENT, r, border_radius=3)
            surf = self.ctx.fonts["small"].render(str(self.items[idx]), True,
                                                  TEXT if idx == self.index else DIM)
            canvas.blit(surf, (r.x + 8, r.centery - surf.get_height() // 2))
        if len(self.items) > self._max_rows():
            inner = self.rect.height - 8
            bar_h = max(24, int(inner * self._max_rows() / len(self.items)))
            denom = max(1, len(self.items) - self._max_rows())
            y = self.rect.y + 4 + int((inner - bar_h) * (self.scroll / denom))
            pygame.draw.rect(canvas, EDGE, (self.rect.right - 9, y, 4, bar_h),
                             border_radius=2)


class MultiSelect:
    """Scrollable checkbox list; ``value`` is the set of checked item ids."""

    def __init__(self, ctx, rect, options=(), selected=()):
        self.ctx = ctx
        self.rect = pygame.Rect(rect)
        self.options = list(options)          # [(id, label)]
        self.checked = set(selected)
        self.scroll = 0
        self.row_h = ctx.fonts["small"].get_height() + 8

    def set_options(self, options, selected=None):
        self.options = list(options)
        if selected is not None:
            self.checked = set(selected)

    @property
    def value(self):
        return [oid for oid, _ in self.options if oid in self.checked]

    def _max_rows(self):
        return max(1, (self.rect.height - 8) // self.row_h)

    def _clamp(self):
        self.scroll = max(0, min(self.scroll, max(0, len(self.options) - self._max_rows())))

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(getattr(event, "pos", (0, 0))):
            self.scroll = max(0, self.scroll - event.y)
            self._clamp()
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            row = (event.pos[1] - self.rect.y - 4) // self.row_h
            idx = self.scroll + row
            if 0 <= idx < len(self.options):
                oid = self.options[idx][0]
                self.checked.symmetric_difference_update({oid})
            return True
        return False

    def draw(self, canvas):
        pygame.draw.rect(canvas, FIELD_BG, self.rect, border_radius=4)
        pygame.draw.rect(canvas, FIELD_EDGE, self.rect, 2, border_radius=4)
        for row in range(self._max_rows()):
            idx = self.scroll + row
            if idx >= len(self.options):
                break
            oid, label = self.options[idx]
            r = pygame.Rect(self.rect.x + 4, self.rect.y + 4 + row * self.row_h,
                            self.rect.width - 8, self.row_h)
            box = pygame.Rect(r.x + 4, r.centery - 7, 14, 14)
            on = oid in self.checked
            pygame.draw.rect(canvas, FIELD_BG, box)
            pygame.draw.rect(canvas, OK if on else FIELD_EDGE, box, 2)
            if on:
                pygame.draw.line(canvas, OK, (box.x + 3, box.centery),
                                 (box.centerx, box.bottom - 3), 2)
                pygame.draw.line(canvas, OK, (box.centerx, box.bottom - 3),
                                 (box.right - 3, box.y + 3), 2)
            surf = self.ctx.fonts["small"].render(label, True, TEXT)
            canvas.blit(surf, (box.right + 8, r.centery - surf.get_height() // 2))
        if len(self.options) > self._max_rows():
            inner = self.rect.height - 8
            bar_h = max(20, int(inner * self._max_rows() / len(self.options)))
            denom = max(1, len(self.options) - self._max_rows())
            y = self.rect.y + 4 + int((inner - bar_h) * (self.scroll / denom))
            pygame.draw.rect(canvas, EDGE, (self.rect.right - 9, y, 4, bar_h), border_radius=2)


# ---------------------------------------------------------------------------
# upgrade branch editor
# ---------------------------------------------------------------------------
UPGRADE_GAIN_KEYS = ("damage", "range", "rate", "hp")
UPGRADE_GAIN_LABELS = {"damage": "dmg", "range": "range", "rate": "rate",
                       "hp": "hp"}


def default_upgrade_paths():
    """The five default branches (imported lazily to avoid a cycle)."""
    from core.content import DEFAULT_UPGRADE_PATHS
    return [{"id": p["id"], "name": p["name"], "gains": dict(p["gains"])}
            for p in DEFAULT_UPGRADE_PATHS]


def clean_upgrade_path(path, fallback_id="path"):
    """One branch with every gain key spelled out, so it round-trips exactly.

    ``normalise_upgrade_paths`` drops branches with a blank id or no gains at
    all, so the editor never emits one: gains always carry all four multipliers
    (1.0 == no change) and the id/name fall back to something printable.
    """
    pid = str(path.get("id") or "").strip() or fallback_id
    name = str(path.get("name") or "").strip() or pid.replace("_", " ").title()
    raw = path.get("gains") or {}
    gains = {}
    for key in UPGRADE_GAIN_KEYS:
        try:
            value = float(raw.get(key, 1.0))
        except (TypeError, ValueError):
            value = 1.0
        gains[key] = round(max(0.01, value), 4)
    try:
        shots = int(raw.get("projectiles") or 0)
    except (TypeError, ValueError):
        shots = 0
    gains["projectiles"] = shots
    return {"id": pid, "name": name, "gains": gains}


class UpgradePathEditor:
    """Compact editor for a unit's upgrade branches.

    Left: the branch list plus add / del / reset-to-default.  Right: the
    selected branch's id, name, four gain multipliers and an additive projectile
    count.  ``paths`` is always a list of ``{"id", "name", "gains"}`` dicts in
    exactly the shape ``core.content`` reads back, so save + reload is lossless.
    """

    def __init__(self, ctx, rect, on_change=None):
        self.ctx = ctx
        self.rect = pygame.Rect(rect)
        self.on_change = on_change
        self.paths = []
        self.index = -1

        list_w = 168
        self.list = ScrollList(ctx, pygame.Rect(self.rect.x + 6, self.rect.y + 26,
                                               list_w, self.rect.height - 56),
                               [], on_select=self._on_select)
        bw, bh = (list_w - 8) // 3, 24
        by = self.list.rect.bottom + 4
        self.add_btn = Btn(ctx, (self.list.rect.x, by, bw, bh), "add", self.add)
        self.del_btn = Btn(ctx, (self.list.rect.x + bw + 4, by, bw, bh), "del",
                           self.remove, color=(90, 54, 54))
        self.def_btn = Btn(ctx, (self.list.rect.x + 2 * (bw + 4), by, bw, bh),
                           "default", self.restore_defaults)

        fx = self.list.rect.right + 10
        fw = self.rect.right - 6 - fx
        self.fields = {
            "id": TextField(ctx, pygame.Rect(fx, self.rect.y + 26, fw // 2 - 4, 24),
                            "id", label_w=40),
            "name": TextField(ctx, pygame.Rect(fx + fw // 2 + 4, self.rect.y + 26,
                                               fw // 2 - 4, 24), "name", label_w=56),
        }
        gain_w = (fw - 3 * 6) // 4
        for i, key in enumerate(UPGRADE_GAIN_KEYS):
            self.fields[key] = FloatField(
                ctx, pygame.Rect(fx + i * (gain_w + 6), self.rect.y + 58,
                                 gain_w, 24),
                UPGRADE_GAIN_LABELS[key], 1.0, label_w=44)
        self.fields["projectiles"] = IntField(
            ctx, pygame.Rect(fx, self.rect.y + 90, gain_w, 24), "+shots", 0, label_w=50)
        self.summary = pygame.Rect(fx, self.rect.y + 124, fw, 22)
        self.hint = pygame.Rect(fx, self.rect.y + 150, fw, self.rect.height - 156)
        self.set_paths([])

    # -- data ----------------------------------------------------------------
    def set_paths(self, paths):
        """Load branches; an empty/None value means "the shipped defaults"."""
        paths = [clean_upgrade_path(p) for p in (paths or [])] or default_upgrade_paths()
        self.paths = paths
        self.index = 0 if paths else -1
        self.list.set_items([self._label(p) for p in paths], keep=False)
        self._load_active()

    @property
    def value(self):
        return [clean_upgrade_path(p, "path{}".format(i + 1))
                for i, p in enumerate(self.paths)]

    def _label(self, path):
        text = "{}  {}".format(path["id"], path["name"])
        return text[:22] + "..." if len(text) > 25 else text

    def _active(self):
        return self.paths[self.index] if 0 <= self.index < len(self.paths) else None

    def _on_select(self, _label):
        if 0 <= self.list.index < len(self.paths):
            self.index = self.list.index
        self._load_active()

    def _load_active(self):
        path = self._active()
        for key, field in self.fields.items():
            if path is None:
                field.set_value(1.0 if key in UPGRADE_GAIN_KEYS else
                                ("" if key in ("id", "name") else 0))
            elif key in ("id", "name"):
                field.set_value(path[key])
            elif key == "projectiles":
                field.set_value(path["gains"].get("projectiles", 0))
            else:
                field.set_value(path["gains"].get(key, 1.0))
        self._sync_buttons()

    def _store_active(self):
        """Copy the on-screen field values back into the selected branch."""
        path = self._active()
        if path is None:
            return False
        before = (path["id"], path["name"], dict(path["gains"]))
        f = self.fields
        path["id"] = f["id"].value
        path["name"] = f["name"].value
        gains = path["gains"]
        for key in UPGRADE_GAIN_KEYS:
            gains[key] = f[key].value
        gains["projectiles"] = max(0, f["projectiles"].value)
        return before != (path["id"], path["name"], dict(gains))

    def _sync_buttons(self):
        self.del_btn.enabled = self._active() is not None
        self.def_btn.enabled = True

    # -- editing -------------------------------------------------------------
    def add(self):
        taken = {p["id"] for p in self.paths}
        base, n = "path", 2
        while base in taken:
            base, n = "path{}".format(n), n + 1
        self.paths.append({"id": base, "name": base.title(),
                           "gains": dict({k: 1.0 for k in UPGRADE_GAIN_KEYS},
                                         projectiles=0)})
        self.index = len(self.paths) - 1
        self._rebuild()
        self._notify()

    def remove(self):
        if not (0 <= self.index < len(self.paths)):
            return
        self.paths.pop(self.index)
        self.index = min(self.index, len(self.paths) - 1)
        self._rebuild()
        self._notify()

    def restore_defaults(self):
        self.set_paths(default_upgrade_paths())
        self._notify()

    def _rebuild(self):
        self.list.set_items([self._label(p) for p in self.paths], keep=False)
        self.list.index = self.index if self.paths else -1
        self.list._clamp()
        self._load_active()

    def _refresh_labels(self):
        """Update only the list captions (typing must not steal the cursor)."""
        selected = self.list.selected
        self.list.items = [self._label(p) for p in self.paths]
        if selected in self.list.items:
            self.list.index = self.list.items.index(selected)
        self.list._clamp()

    def _notify(self):
        if self.on_change is not None:
            self.on_change(self)

    # -- events --------------------------------------------------------------
    def handle_event(self, event):
        if self.list.handle_event(event):
            return True
        for btn in (self.add_btn, self.del_btn, self.def_btn):
            if btn.handle_event(event):
                return True
        before = self._signature()
        for field in self.fields.values():
            if field.handle_event(event):
                self._store_active()
                if self._signature() != before:
                    self._refresh_labels()
                    self._notify()
                return True
        return False

    def _signature(self):
        return repr(self.paths)

    # -- drawing -------------------------------------------------------------
    def draw(self, canvas):
        pygame.draw.rect(canvas, PANEL, self.rect, border_radius=6)
        pygame.draw.rect(canvas, EDGE, self.rect, 1, border_radius=6)
        font = self.ctx.fonts["small"]
        title = font.render("Upgrade paths (multipliers; 1.0 = unchanged)",
                            True, TEXT)
        canvas.blit(title, (self.rect.x + 8, self.rect.y + 6))
        self.list.draw(canvas)
        for btn in (self.add_btn, self.del_btn, self.def_btn):
            btn.draw(canvas)
        path = self._active()
        for field in self.fields.values():
            field.draw(canvas)
        if path is None:
            note = font.render("no branches", True, DIM)
            canvas.blit(note, note.get_rect(center=self.summary.center))
            return
        g = self.fields  # the values on screen are the ones that get saved
        text = ("gains  x{:.2f} dmg   x{:.2f} range   x{:.2f} rate   "
                "x{:.2f} hp   +{} shot{}".format(
                    g["damage"].value, g["range"].value, g["rate"].value,
                    g["hp"].value, max(0, g["projectiles"].value),
                    "" if max(0, g["projectiles"].value) == 1 else "s"))
        canvas.blit(font.render(text, True, OK), (self.summary.x, self.summary.y))
        y = self.hint.y
        for line in ("Left click a branch to edit it, the wheel scrolls the list.",
                     "Every gain is always written out, so save + reload keeps",
                     "exactly what you typed.  'default' restores the five",
                     "shipped branches (damage / range / rapid / multi / vitality)."):
            canvas.blit(font.render(line, True, DIM), (self.hint.x, y))
            y += 18

    def value_signature(self):     # kept for the parent tab's change detection
        return repr(self.paths)


# ---------------------------------------------------------------------------
# buttons
# ---------------------------------------------------------------------------
class Btn:
    def __init__(self, ctx, rect, text, fn=None, color=PANEL2, fg=TEXT, enabled=True):
        self.ctx = ctx
        self.rect = pygame.Rect(rect)
        self.text = text
        self.fn = fn
        self.color = color
        self.fg = fg
        self.enabled = enabled
        self.hover = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
        elif (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
              and self.rect.collidepoint(event.pos)):
            if self.enabled and self.fn:
                self.fn()
            return True
        return False

    def draw(self, canvas):
        color = self.color
        if not self.enabled:
            color = (48, 48, 58)
        elif self.hover:
            color = tuple(min(255, c + 24) for c in color[:3])
        pygame.draw.rect(canvas, color, self.rect, border_radius=4)
        pygame.draw.rect(canvas, EDGE, self.rect, 1, border_radius=4)
        surf = self.ctx.fonts["small"].render(self.text, True,
                                              self.fg if self.enabled else DIM)
        canvas.blit(surf, surf.get_rect(center=self.rect.center))


# ---------------------------------------------------------------------------
# tile picker modal
# ---------------------------------------------------------------------------
class TilePicker:
    COLS = 12
    ROWS = 9
    CELL = 56

    def __init__(self, ctx, on_pick):
        self.ctx = ctx
        self.on_pick = on_pick
        w = self.COLS * self.CELL + 40
        h = self.ROWS * self.CELL + 70
        self.rect = pygame.Rect(0, 0, w, h)
        cw, ch = ctx.canvas.get_size()
        self.rect.center = (cw // 2, ch // 2)
        self.scroll = 0

    def _max_scroll(self):
        total = (300 + self.COLS - 1) // self.COLS
        return max(0, total - self.ROWS)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.ctx.close_modal()
            return True
        if event.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, min(self._max_scroll(), self.scroll - event.y))
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.rect.collidepoint(event.pos):
                self.ctx.close_modal()
                return True
            grid = self.grid_rect
            if grid.collidepoint(event.pos):
                col = (event.pos[0] - grid.x) // self.CELL
                row = (event.pos[1] - grid.y) // self.CELL
                idx = (self.scroll + row) * self.COLS + col
                if 0 <= idx < 300:
                    self.on_pick(idx)
                    self.ctx.close_modal()
            return True
        return True

    @property
    def grid_rect(self):
        return pygame.Rect(self.rect.x + 20, self.rect.y + 50,
                           self.COLS * self.CELL, self.ROWS * self.CELL)

    def draw(self, canvas):
        veil = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 170))
        canvas.blit(veil, (0, 0))
        pygame.draw.rect(canvas, PANEL, self.rect, border_radius=8)
        pygame.draw.rect(canvas, EDGE, self.rect, 2, border_radius=8)
        title = self.ctx.fonts["default"].render(
            "Pick a tile (mouse wheel scrolls, ESC closes)", True, TEXT)
        canvas.blit(title, title.get_rect(midtop=(self.rect.centerx, self.rect.y + 16)))
        grid = self.grid_rect
        pygame.draw.rect(canvas, FIELD_BG, grid, border_radius=4)
        for i in range(300):
            col = i % self.COLS
            row = i // self.COLS
            if row < self.scroll or row >= self.scroll + self.ROWS:
                continue
            x = grid.x + col * self.CELL
            y = grid.y + (row - self.scroll) * self.CELL
            cell = pygame.Rect(x, y, self.CELL, self.CELL)
            try:
                img = art.scaled(art.tile(i), (self.CELL - 8, self.CELL - 8),
                                 ("tile", i))
                canvas.blit(img, img.get_rect(center=cell.center))
            except Exception:      # noqa: BLE001
                pass
            pygame.draw.rect(canvas, (60, 60, 72), cell, 1)
            num = self.ctx.fonts["small"].render(str(i), True, (255, 255, 255))
            canvas.blit(num, (cell.x + 2, cell.y + 1))


# ---------------------------------------------------------------------------
# file browser modal (navigate folders under assets/ and pick a PNG)
# ---------------------------------------------------------------------------
class FileBrowser:
    """Browse ``assets/`` folders and pick a PNG image or spritesheet."""

    def __init__(self, ctx, on_pick, start=""):
        self.ctx = ctx
        self.on_pick = on_pick
        self.root = paths.ASSETS_DIR
        self.rel = (start or "").strip("/")
        if self.rel and not (self.root / self.rel).is_dir():
            self.rel = ""
        cw, ch = ctx.canvas.get_size()
        w, h = min(980, cw - 60), min(700, ch - 60)
        self.rect = pygame.Rect(0, 0, w, h)
        self.rect.center = (cw // 2, ch // 2)
        self.row_h = ctx.fonts["small"].get_height() + 8
        self.scroll = 0
        self._reload()

    def _reload(self):
        self.entries = []
        if self.rel:
            self.entries.append(("up", ".."))
        try:
            children = sorted((self.root / self.rel).iterdir(),
                              key=lambda p: (p.is_file(), p.name.lower()))
        except OSError:
            children = []
        for p in children:
            if p.is_dir():
                self.entries.append(("dir", p.name))
            elif p.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp", ".gif"):
                self.entries.append(("img", p.name))
        self.scroll = 0

    def _rel_of(self, name):
        return (self.rel + "/" + name).lstrip("/") if self.rel else name

    def _rows(self):
        return max(1, (self.list_rect.height - 8) // self.row_h)

    def _clamp(self):
        self.scroll = max(0, min(self.scroll, max(0, len(self.entries) - self._rows())))

    @property
    def list_rect(self):
        return pygame.Rect(self.rect.x + 12, self.rect.y + 56,
                           self.rect.width - 24, self.rect.height - 68)

    def _enter(self, rel):
        self.rel = rel
        self._reload()

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.ctx.close_modal()
            return True
        if event.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, self.scroll - event.y)
            self._clamp()
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.rect.collidepoint(event.pos):
                self.ctx.close_modal()
                return True
            if self.list_rect.collidepoint(event.pos):
                row = (event.pos[1] - self.list_rect.y) // self.row_h
                idx = self.scroll + row
                if 0 <= idx < len(self.entries):
                    kind, name = self.entries[idx]
                    if kind == "up":
                        self._enter("/".join(self.rel.split("/")[:-1]))
                    elif kind == "dir":
                        self._enter(self._rel_of(name))
                    else:
                        self.on_pick(self._rel_of(name))
                        # on_pick may open another modal (e.g. the animation
                        # editor); only close if we are still the active modal
                        if self.ctx.modal is self:
                            self.ctx.close_modal()
            return True
        return True

    def draw(self, canvas):
        veil = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 175))
        canvas.blit(veil, (0, 0))
        pygame.draw.rect(canvas, PANEL, self.rect, border_radius=8)
        pygame.draw.rect(canvas, EDGE, self.rect, 2, border_radius=8)
        title = self.ctx.fonts["default"].render(
            "Pick an image - assets/{}  (ESC closes)".format(
                "/" + self.rel if self.rel else ""), True, TEXT)
        canvas.blit(title, (self.rect.x + 16, self.rect.y + 16))

        lst = self.list_rect
        pygame.draw.rect(canvas, FIELD_BG, lst, border_radius=4)
        pygame.draw.rect(canvas, FIELD_EDGE, lst, 1, border_radius=4)
        for row in range(self._rows()):
            idx = self.scroll + row
            if idx >= len(self.entries):
                break
            kind, name = self.entries[idx]
            r = pygame.Rect(lst.x + 4, lst.y + 4 + row * self.row_h,
                            lst.width - 8, self.row_h - 2)
            pygame.draw.rect(canvas, PANEL2, r, border_radius=3)
            icon = pygame.Rect(r.x + 4, r.y + 3, self.row_h - 8, self.row_h - 8)
            if kind == "dir":
                pygame.draw.rect(canvas, (150, 170, 90), icon, border_radius=3)
                label, color = "[" + name + "]", TEXT
            elif kind == "up":
                pygame.draw.rect(canvas, (110, 120, 150), icon, border_radius=3)
                label, color = ".. (up one folder)", DIM
            else:
                try:
                    img = art.scaled(art.image(self._rel_of(name)),
                                     (icon.height, icon.height),
                                     ("image", self._rel_of(name)))
                    canvas.blit(img, img.get_rect(center=icon.center))
                except Exception:      # noqa: BLE001
                    pass
                label, color = name, TEXT
            pygame.draw.rect(canvas, EDGE, icon, 1, border_radius=3)
            surf = self.ctx.fonts["small"].render(label, True, color)
            canvas.blit(surf, (icon.right + 8, r.centery - surf.get_height() // 2))
        if len(self.entries) > self._rows():
            inner = lst.height - 8
            bar_h = max(24, int(inner * self._rows() / len(self.entries)))
            denom = max(1, len(self.entries) - self._rows())
            y = lst.y + 4 + int((inner - bar_h) * (self.scroll / denom))
            pygame.draw.rect(canvas, EDGE, (lst.right - 6, y, 4, bar_h),
                             border_radius=2)
        if not self.entries:
            msg = self.ctx.fonts["default"].render(
                "No images here - go up a folder, or add PNGs under assets/.",
                True, DIM)
            canvas.blit(msg, msg.get_rect(center=lst.center))


# backwards-compatible alias used elsewhere
ImagePicker = FileBrowser


# ---------------------------------------------------------------------------
# "static or animation?" chooser
# ---------------------------------------------------------------------------
class SpriteKindDialog:
    """Ask whether the sprite is a single image, an animation, or a sheet tile."""

    def __init__(self, ctx, on_choice):
        self.ctx = ctx
        self.on_choice = on_choice
        cw, ch = ctx.canvas.get_size()
        self.rect = pygame.Rect(0, 0, 620, 250)
        self.rect.center = (cw // 2, ch // 2)
        bw, bh = 170, 84
        y = self.rect.y + 112
        xs = (self.rect.x + 40, self.rect.x + 40 + bw + 15,
              self.rect.x + 40 + 2 * (bw + 15))
        self.buttons = [
            (pygame.Rect(xs[0], y, bw, bh), "Static image", "static"),
            (pygame.Rect(xs[1], y, bw, bh), "Animation", "anim"),
            (pygame.Rect(xs[2], y, bw, bh), "Sheet tile", "sheet"),
        ]
        self.cancel = pygame.Rect(self.rect.centerx - 60, y + bh + 16, 120, 28)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.ctx.close_modal()
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.rect.collidepoint(event.pos):
                self.ctx.close_modal()
                return True
            for rect, _label, value in self.buttons:
                if rect.collidepoint(event.pos):
                    self.ctx.close_modal()
                    self.on_choice(value)
                    return True
            if self.cancel.collidepoint(event.pos):
                self.ctx.close_modal()
            return True
        return True

    def draw(self, canvas):
        veil = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 175))
        canvas.blit(veil, (0, 0))
        pygame.draw.rect(canvas, PANEL, self.rect, border_radius=8)
        pygame.draw.rect(canvas, EDGE, self.rect, 2, border_radius=8)
        title = self.ctx.fonts["default"].render(
            "What kind of sprite is this?", True, TEXT)
        canvas.blit(title, title.get_rect(midtop=(self.rect.centerx, self.rect.y + 22)))
        sub = self.ctx.fonts["small"].render(
            "Static: one PNG.   Animation: a spritesheet you split into states."
            "   Sheet tile: one frame from an imported sheet.", True, DIM)
        canvas.blit(sub, sub.get_rect(midtop=(self.rect.centerx, self.rect.y + 58)))
        hints = {"Static image": "image", "Animation": "spritesheet",
                 "Sheet tile": "via the Sheets tab"}
        for rect, label, _value in self.buttons:
            pygame.draw.rect(canvas, PANEL2, rect, border_radius=6)
            pygame.draw.rect(canvas, ACCENT, rect, 2, border_radius=6)
            surf = self.ctx.fonts["default"].render(label, True, TEXT)
            canvas.blit(surf, surf.get_rect(center=(rect.centerx, rect.centery - 8)))
            hint = self.ctx.fonts["small"].render(hints[label], True, DIM)
            canvas.blit(hint, hint.get_rect(center=(rect.centerx, rect.centery + 18)))
        pygame.draw.rect(canvas, PANEL2, self.cancel, border_radius=4)
        pygame.draw.rect(canvas, EDGE, self.cancel, 1, border_radius=4)
        c = self.ctx.fonts["small"].render("Cancel", True, TEXT)
        canvas.blit(c, c.get_rect(center=self.cancel.center))


# ---------------------------------------------------------------------------
# sheet tile picker (one frame from a registered spritesheet)
# ---------------------------------------------------------------------------
class SheetTilePicker:
    """Click one frame of an imported spritesheet.

    ``sheets`` is the registry from the Sheets tab (normalized dicts).  The
    chosen frame becomes a self-contained single-frame ``sheet`` spec -- it
    repeats the sheet's path and geometry, so the game needs no registry.
    The sheet PNG itself is loaded through :func:`engine.art.image`, whose
    path-keyed cache keeps one copy in memory however many sprites use it.
    """

    def __init__(self, ctx, sheets, on_result):
        self.ctx = ctx
        self.sheets = [s for s in (sheets or []) if isinstance(s, dict)
                       and s.get("path")]
        self.on_result = on_result
        self.index = 0
        self.hover = None                 # (col, row) under the cursor
        cw, ch = ctx.canvas.get_size()
        self.rect = pygame.Rect(0, 0, 900, 580)
        self.rect.center = (cw // 2, ch // 2)
        self.preview = pygame.Rect(self.rect.x + 16, self.rect.y + 76,
                                   self.rect.width - 32,
                                   self.rect.height - 132)
        self.prev_btn = pygame.Rect(self.rect.x + 16, self.rect.y + 34, 34, 30)
        self.next_btn = pygame.Rect(self.rect.x + self.rect.width - 50,
                                    self.rect.y + 34, 34, 30)
        self.cancel = pygame.Rect(self.rect.centerx - 55,
                                  self.rect.bottom - 42, 110, 28)

    # -- geometry -------------------------------------------------------------
    def _sheet(self):
        if 0 <= self.index < len(self.sheets):
            return self.sheets[self.index]
        return None

    def _grid(self, sheet, surf):
        """(fw, fh, spacing, margin, cols, rows, scale) for the shown sheet."""
        fw = max(1, int(sheet.get("frame_w", 32)))
        fh = max(1, int(sheet.get("frame_h", 32)))
        spacing = max(0, int(sheet.get("spacing", 0)))
        margin = max(0, int(sheet.get("margin", 0)))
        cols = max(1, (surf.get_width() - 2 * margin + spacing) // (fw + spacing))
        rows = max(1, (surf.get_height() - 2 * margin + spacing) // (fh + spacing))
        scale = min(self.preview.width / float(surf.get_width()),
                    self.preview.height / float(surf.get_height()))
        return fw, fh, spacing, margin, cols, rows, scale

    def _shown_origin(self, surf, scale):
        """Top-left corner of the scaled sheet as ``draw`` blits it.

        ``draw`` *centres* the scaled sheet in the preview panel, so the art
        only starts at ``preview.topleft`` when its aspect ratio happens to
        fill the panel.  The grid overlay and the hit-test have to measure
        from this origin too: with Kenney (1472x832, height-limited 868x448
        panel) the sheet sits 38px to the right of ``preview.x`` -- about one
        whole 64px tile on screen -- which made every click select the tile to
        the right of the one under the cursor.
        """
        shown_w = max(1, int(surf.get_width() * scale))
        shown_h = max(1, int(surf.get_height() * scale))
        return (self.preview.centerx - shown_w // 2,
                self.preview.centery - shown_h // 2)

    def _cell_rect(self, col, row):
        """Screen rect of grid cell (col, row) on the scaled preview."""
        sheet = self._sheet()
        if sheet is None:
            return None
        surf = art.image(sheet["path"])
        fw, fh, spacing, margin, _cols, _rows, scale = self._grid(sheet, surf)
        ox, oy = self._shown_origin(surf, scale)
        x = ox + (margin + col * (fw + spacing)) * scale
        y = oy + (margin + row * (fh + spacing)) * scale
        return pygame.Rect(int(x), int(y), max(2, int(fw * scale)),
                           max(2, int(fh * scale)))

    def _cell_at(self, pos):
        """(col, row, index) under a canvas point, or None outside the grid."""
        sheet = self._sheet()
        if sheet is None or not self.preview.collidepoint(pos):
            return None
        surf = art.image(sheet["path"])
        fw, fh, spacing, margin, cols, rows, scale = self._grid(sheet, surf)
        ox, oy = self._shown_origin(surf, scale)
        lx = (pos[0] - ox) / max(scale, 1e-6)
        ly = (pos[1] - oy) / max(scale, 1e-6)
        col = int((lx - margin) // (fw + spacing))
        row = int((ly - margin) // (fh + spacing))
        if not (0 <= col < cols and 0 <= row < rows):
            return None
        return col, row, row * cols + col

    # -- events ---------------------------------------------------------------
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.ctx.close_modal()
            return True
        if event.type == pygame.MOUSEMOTION:
            cell = self._cell_at(event.pos)
            self.hover = (cell[0], cell[1]) if cell else None
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.rect.collidepoint(event.pos):
                self.ctx.close_modal()
                return True
            if self.prev_btn.collidepoint(event.pos) and self.sheets:
                self.index = (self.index - 1) % len(self.sheets)
                self.hover = None
                return True
            if self.next_btn.collidepoint(event.pos) and self.sheets:
                self.index = (self.index + 1) % len(self.sheets)
                self.hover = None
                return True
            if self.cancel.collidepoint(event.pos):
                self.ctx.close_modal()
                return True
            cell = self._cell_at(event.pos)
            if cell is not None:
                sheet = self._sheet()
                self.ctx.close_modal()
                self.on_result({           # self-contained single-frame spec
                    "kind": "sheet", "path": sheet["path"],
                    "frame_w": int(sheet.get("frame_w", 32)),
                    "frame_h": int(sheet.get("frame_h", 32)),
                    "margin": int(sheet.get("margin", 0)),
                    "spacing": int(sheet.get("spacing", 0)),
                    "frames": [cell[2]], "fps": 8.0, "loop": False,
                })
            return True
        return True

    # -- drawing ----------------------------------------------------------------
    def draw(self, canvas):
        veil = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 185))
        canvas.blit(veil, (0, 0))
        pygame.draw.rect(canvas, PANEL, self.rect, border_radius=8)
        pygame.draw.rect(canvas, EDGE, self.rect, 2, border_radius=8)
        title = self.ctx.fonts["default"].render(
            "Pick a tile - click a frame to use it", True, TEXT)
        canvas.blit(title, title.get_rect(midtop=(self.rect.centerx,
                                                  self.rect.y + 14)))
        sheet = self._sheet()
        if sheet is None:
            msg = self.ctx.fonts["default"].render(
                "No spritesheets imported yet - add one in the Sheets tab",
                True, DIM)
            canvas.blit(msg, msg.get_rect(center=self.preview.center))
        else:
            surf = art.image(sheet["path"])
            fw, fh, spacing, margin, cols, rows, scale = self._grid(sheet, surf)
            shown = pygame.transform.smoothscale(
                surf, (max(1, int(surf.get_width() * scale)),
                       max(1, int(surf.get_height() * scale))))
            pygame.draw.rect(canvas, FIELD_BG, self.preview, border_radius=4)
            canvas.blit(shown, shown.get_rect(center=self.preview.center))
            # grid overlay at the sheet's own geometry
            for row in range(rows):
                for col in range(cols):
                    pygame.draw.rect(canvas, EDGE, self._cell_rect(col, row), 1)
            if self.hover:
                cell = self._cell_rect(*self.hover)
                pygame.draw.rect(canvas, ACCENT, cell, 3)
                index = self.hover[1] * cols + self.hover[0]
                tag = self.ctx.fonts["small"].render(
                    "frame {}".format(index), True, ACCENT)
                canvas.blit(tag, (self.prev_btn.right + 260,
                                  self.next_btn.centery - tag.get_height() // 2))
            # sheet switcher + frame count
            for btn, glyph in ((self.prev_btn, "<"), (self.next_btn, ">")):
                pygame.draw.rect(canvas, PANEL2, btn, border_radius=4)
                pygame.draw.rect(canvas, EDGE, btn, 1, border_radius=4)
                g = self.ctx.fonts["default"].render(glyph, True, TEXT)
                canvas.blit(g, g.get_rect(center=btn.center))
            label = self.ctx.fonts["small"].render(
                "{} ({}/{})   {}x{} frames of {}x{} px".format(
                    sheet.get("name", sheet.get("id", "?")),
                    self.index + 1, len(self.sheets),
                    cols, rows, fw, fh), True, DIM)
            canvas.blit(label, (self.prev_btn.right + 12, self.rect.y + 40))
        pygame.draw.rect(canvas, PANEL2, self.cancel, border_radius=4)
        pygame.draw.rect(canvas, EDGE, self.cancel, 1, border_radius=4)
        c = self.ctx.fonts["small"].render("Cancel", True, TEXT)
        canvas.blit(c, c.get_rect(center=self.cancel.center))


# ---------------------------------------------------------------------------
# animation editor (highlight frames of a spritesheet per state)
# ---------------------------------------------------------------------------
STATE_COLORS = {
    "idle": (120, 190, 255),
    "walk": (120, 220, 140),
    "attack": (240, 160, 90),
    "death": (220, 110, 110),
    "anim": (150, 180, 240),
}


class AnimationEditor:
    """Slice a spritesheet into named animation states by clicking frames.

    Left: the state list plus the active state's fps / loop.  Right: the whole
    spritesheet as a grid; click a frame to add/remove it from the active state
    (shift-click adds the range since the last click).  ``on_save`` receives
    ``(sheet, frame_w, frame_h, margin, spacing, {state: {...}})``.
    """

    def __init__(self, ctx, sheet, on_save, states=None,
                 frames_by_state=None, frame_w=32, frame_h=32,
                 margin=0, spacing=0, simple=False):
        self.ctx = ctx
        self.sheet = sheet
        self.on_save = on_save
        self.simple = simple
        self.states = list(states or ("idle", "walk", "attack", "death"))
        self.frames = {s: [] for s in self.states}
        self.fps_v = {s: 8.0 for s in self.states}
        self.loop_v = {s: True for s in self.states}
        for name, data in (frames_by_state or {}).items():
            if name in self.frames and isinstance(data, dict):
                self.frames[name] = [int(i) for i in (data.get("frames") or [])]
                self.fps_v[name] = float(data.get("fps", 8.0))
                self.loop_v[name] = bool(data.get("loop", True))
        self.active = self.states[0]
        self.frame_w, self.frame_h = int(frame_w), int(frame_h)
        self.margin, self.spacing = int(margin), int(spacing)
        self.scroll = 0
        self._last_click = None
        self._frame_cache = {}

        cw, ch = ctx.canvas.get_size()
        self.rect = pygame.Rect(0, 0, min(1200, cw - 40), min(760, ch - 40))
        self.rect.center = (cw // 2, ch // 2)

        self.left = pygame.Rect(self.rect.x + 14, self.rect.y + 50, 268,
                                self.rect.height - 118)
        self.grid = pygame.Rect(self.left.right + 14, self.rect.y + 50,
                                self.rect.right - 14 - (self.left.right + 14),
                                self.rect.height - 118)

        self.fps_field = FloatField(ctx, (0, 0, 0, 0), "", 8.0, label_w=0)
        self.loop_field = CheckField(ctx, (0, 0, 0, 0), "", True, label_w=0)
        self.fw_field = IntField(ctx, (0, 0, 0, 0), "frame w", self.frame_w, label_w=70)
        self.fh_field = IntField(ctx, (0, 0, 0, 0), "frame h", self.frame_h, label_w=70)
        self.margin_field = IntField(ctx, (0, 0, 0, 0), "margin", self.margin, label_w=70)
        self.spacing_field = IntField(ctx, (0, 0, 0, 0), "spacing", self.spacing, label_w=70)
        self._layout_fields()
        self.save_btn = pygame.Rect(0, 0, 120, 30)
        self.cancel_btn = pygame.Rect(0, 0, 100, 30)
        self.clear_btn = pygame.Rect(0, 0, 130, 28)
        self.sheet_btn = pygame.Rect(0, 0, 130, 26)
        self._place_buttons()
        self._load_active()

    # -- layout -------------------------------------------------------------
    def _layout_fields(self):
        y = self.rect.bottom - 40
        self.fw_field.set_rect(pygame.Rect(self.rect.x + 14, y, 150, 30))
        self.fh_field.set_rect(pygame.Rect(self.rect.x + 174, y, 150, 30))
        self.margin_field.set_rect(pygame.Rect(self.rect.x + 334, y, 150, 30))
        self.spacing_field.set_rect(pygame.Rect(self.rect.x + 494, y, 150, 30))

    def _place_buttons(self):
        self.save_btn.topleft = (self.rect.right - 274, self.rect.bottom - 42)
        self.cancel_btn.topleft = (self.rect.right - 144, self.rect.bottom - 42)
        self.clear_btn.topleft = (self.left.x, self.left.bottom - 34)
        self.sheet_btn.topleft = (self.rect.right - 150, self.rect.y + 16)

    def _state_rows(self):
        rows = []
        y = self.left.y
        for name in self.states:
            rows.append((pygame.Rect(self.left.x, y, self.left.width, 30), name))
            y += 34
        return rows

    def _detail_rects(self):
        y = self.left.y + len(self.states) * 34 + 8
        fps = pygame.Rect(self.left.x + 44, y, 90, 28)
        loop = pygame.Rect(self.left.x + 44, y + 36, 28, 28)
        preview = pygame.Rect(self.left.centerx - 44, y + 74, 88, 88)
        return fps, loop, preview

    # -- active state -------------------------------------------------------
    def _load_active(self):
        self.fps_field.set_value(self.fps_v[self.active])
        self.loop_field.set_value(self.loop_v[self.active])

    def _store_active(self):
        self.fps_v[self.active] = max(0.1, self.fps_field.value)
        self.loop_v[self.active] = bool(self.loop_field.value)

    # -- sheet geometry -----------------------------------------------------
    def _grid_size(self):
        try:
            img = art.image(self.sheet)
            w, h = img.get_size()
        except Exception:      # noqa: BLE001
            w = h = 0
        fw, fh = max(1, self.frame_w), max(1, self.frame_h)
        sp, mg = max(0, self.spacing), max(0, self.margin)
        cols = max(1, (w - 2 * mg + sp) // (fw + sp)) if w else 1
        rows = max(1, (h - 2 * mg + sp) // (fh + sp)) if h else 1
        return cols, rows

    def _frame_surfaces(self, cell):
        key = (self.sheet, self.frame_w, self.frame_h, self.margin,
               self.spacing, cell)
        if key not in self._frame_cache:
            cols, rows = self._grid_size()
            spec = {"kind": "sheet", "path": self.sheet,
                    "frame_w": self.frame_w, "frame_h": self.frame_h,
                    "margin": self.margin, "spacing": self.spacing,
                    "frames": cols * rows}
            try:
                self._frame_cache[key] = art.sprite_frames(spec, cell, None)
            except Exception:      # noqa: BLE001
                self._frame_cache[key] = []
        return self._frame_cache[key]

    def _grid_metrics(self):
        cols, rows = self._grid_size()
        inner = self.grid.width - 12
        cell = max(22, min(84, inner // max(1, cols)))
        visible = max(1, (self.grid.height - 12) // cell)
        max_scroll = max(0, rows - visible)
        self.scroll = max(0, min(self.scroll, max_scroll))
        return cols, rows, cell, visible

    def _frame_at(self, pos):
        if not self.grid.collidepoint(pos):
            return None
        cols, rows, cell, visible = self._grid_metrics()
        gx = self.grid.x + 6
        gy = self.grid.y + 6
        col = (pos[0] - gx) // cell
        row = (pos[1] - gy) // cell + self.scroll
        if col < 0 or col >= cols or row < 0 or row >= rows:
            return None
        idx = row * cols + col
        return idx if idx < cols * rows else None

    # -- events -------------------------------------------------------------
    def _all_fields(self):
        return (self.fps_field, self.loop_field, self.fw_field, self.fh_field,
                self.margin_field, self.spacing_field)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.ctx.close_modal()
                return True
            for f in self._all_fields():
                f.handle_event(event)
            return True
        if event.type == pygame.MOUSEWHEEL:
            self.scroll -= event.y
            self._grid_metrics()
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.rect.collidepoint(event.pos):
                self.ctx.close_modal()
                return True
            for f in self._all_fields():
                if f.box_rect.collidepoint(event.pos):
                    f.handle_event(event)
                    self._store_active()
                    return True
            if self.sheet_btn.collidepoint(event.pos):
                self._change_sheet()
                return True
            if self.clear_btn.collidepoint(event.pos):
                self.frames[self.active] = []
                return True
            if self.save_btn.collidepoint(event.pos):
                self._save()
                return True
            if self.cancel_btn.collidepoint(event.pos):
                self.ctx.close_modal()
                return True
            for rect, name in self._state_rows():
                if rect.collidepoint(event.pos):
                    self._store_active()
                    self.active = name
                    self._last_click = None
                    self._load_active()
                    return True
            idx = self._frame_at(event.pos)
            if idx is not None:
                self._toggle_frame(idx)
                return True
            return True
        return True

    def _change_sheet(self):
        def picked(path):
            self.sheet = path
            self._frame_cache.clear()
            self.scroll = 0
            self.ctx.open_modal(self)
        self.ctx.open_modal(FileBrowser(self.ctx, picked, start=self.sheet.rsplit("/", 1)[0]
                                        if "/" in self.sheet else ""))

    def _toggle_frame(self, idx):
        frames = self.frames[self.active]
        if (pygame.key.get_mods() & pygame.KMOD_SHIFT) and self._last_click is not None:
            a, b = sorted((self._last_click, idx))
            for i in range(a, b + 1):
                if i not in frames:
                    frames.append(i)
        elif idx in frames:
            frames.remove(idx)
        else:
            frames.append(idx)
        self._last_click = idx

    def _save(self):
        self._store_active()
        self.frame_w = max(1, self.fw_field.value)
        self.frame_h = max(1, self.fh_field.value)
        self.margin = max(0, self.margin_field.value)
        self.spacing = max(0, self.spacing_field.value)
        chosen = {name: {"frames": list(self.frames[name]),
                         "fps": self.fps_v[name], "loop": self.loop_v[name]}
                  for name in self.states if self.frames[name]}
        self.ctx.close_modal()
        if chosen:
            self.on_save(self.sheet, self.frame_w, self.frame_h, self.margin,
                         self.spacing, chosen)

    # -- drawing ------------------------------------------------------------
    def draw(self, canvas):
        veil = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 185))
        canvas.blit(veil, (0, 0))
        pygame.draw.rect(canvas, PANEL, self.rect, border_radius=8)
        pygame.draw.rect(canvas, EDGE, self.rect, 2, border_radius=8)
        title = self.ctx.fonts["default"].render(
            "Animation editor - click frames to assign them to the selected state",
            True, TEXT)
        canvas.blit(title, (self.rect.x + 16, self.rect.y + 16))

        # sheet path + change button
        path = self.ctx.fonts["small"].render(self.sheet, True, DIM)
        canvas.blit(path, (self.rect.x + 16, self.rect.y + 44))
        pygame.draw.rect(canvas, PANEL2, self.sheet_btn, border_radius=4)
        pygame.draw.rect(canvas, EDGE, self.sheet_btn, 1, border_radius=4)
        sb = self.ctx.fonts["small"].render("Change sheet", True, TEXT)
        canvas.blit(sb, sb.get_rect(center=self.sheet_btn.center))

        self._draw_states(canvas)
        self._draw_grid(canvas)

        for f in (self.fw_field, self.fh_field, self.margin_field,
                  self.spacing_field):
            f.draw(canvas)
        for rect, label, color in ((self.save_btn, "Save", (64, 92, 70)),
                                   (self.cancel_btn, "Cancel", PANEL2)):
            pygame.draw.rect(canvas, color, rect, border_radius=4)
            pygame.draw.rect(canvas, EDGE, rect, 1, border_radius=4)
            surf = self.ctx.fonts["small"].render(label, True, TEXT)
            canvas.blit(surf, surf.get_rect(center=rect.center))

    def _draw_states(self, canvas):
        done = self.ctx.fonts["small"].render("done", True, OK)
        for rect, name in self._state_rows():
            selected = name == self.active
            pygame.draw.rect(canvas, PANEL2 if selected else FIELD_BG, rect,
                             border_radius=4)
            pygame.draw.rect(canvas, ACCENT if selected else EDGE, rect,
                             2 if selected else 1, border_radius=4)
            color = STATE_COLORS.get(name, ACCENT)
            pygame.draw.rect(canvas, color, (rect.x + 6, rect.centery - 7, 14, 14),
                             border_radius=3)
            label = self.ctx.fonts["small"].render(
                "{}  ({} frames)".format(name, len(self.frames[name])), True,
                TEXT if selected else DIM)
            canvas.blit(label, (rect.x + 28, rect.centery - label.get_height() // 2))
            if name != self.active and self.frames[name]:
                canvas.blit(done, (rect.right - done.get_width() - 8,
                                   rect.centery - done.get_height() // 2))

        fps_rect, loop_rect, preview = self._detail_rects()
        lbl = self.ctx.fonts["small"].render("fps", True, DIM)
        canvas.blit(lbl, (self.left.x, fps_rect.centery - lbl.get_height() // 2))
        self.fps_field.draw(canvas)
        lbl2 = self.ctx.fonts["small"].render("loop", True, DIM)
        canvas.blit(lbl2, (self.left.x, loop_rect.centery - lbl2.get_height() // 2))
        self.loop_field.draw(canvas)
        pygame.draw.rect(canvas, PANEL2, self.clear_btn, border_radius=4)
        pygame.draw.rect(canvas, EDGE, self.clear_btn, 1, border_radius=4)
        cl = self.ctx.fonts["small"].render("Clear state frames", True, BAD)
        canvas.blit(cl, cl.get_rect(center=self.clear_btn.center))
        # preview of the active animation
        pygame.draw.rect(canvas, FIELD_BG, preview, border_radius=4)
        pygame.draw.rect(canvas, FIELD_EDGE, preview, 1, border_radius=4)
        self._draw_preview(canvas, preview)

    def _draw_preview(self, canvas, preview):
        frames = self.frames[self.active]
        if not frames:
            hint = self.ctx.fonts["small"].render("no frames", True, DIM)
            canvas.blit(hint, hint.get_rect(center=preview.center))
            return
        spec = {"kind": "sheet", "path": self.sheet, "frame_w": self.frame_w,
                "frame_h": self.frame_h, "margin": self.margin,
                "spacing": self.spacing, "frames": list(frames),
                "fps": self.fps_v[self.active], "loop": self.loop_v[self.active]}
        try:
            surfs = art.sprite_frames(spec, preview.width - 8)
            t = pygame.time.get_ticks() / 1000.0
            img = surfs[art.frame_index(spec, t) % len(surfs)]
            canvas.blit(img, img.get_rect(center=preview.center))
        except Exception:      # noqa: BLE001
            pass

    def _draw_grid(self, canvas):
        pygame.draw.rect(canvas, FIELD_BG, self.grid, border_radius=4)
        pygame.draw.rect(canvas, FIELD_EDGE, self.grid, 1, border_radius=4)
        cols, rows, cell, visible = self._grid_metrics()
        frames = self._frame_surfaces(cell)
        gx, gy = self.grid.x + 6, self.grid.y + 6
        active_frames = set(self.frames[self.active])
        for row in range(visible):
            for col in range(cols):
                idx = (self.scroll + row) * cols + col
                if idx >= cols * rows or idx >= len(frames):
                    continue
                x = gx + col * cell
                y = gy + row * cell
                r = pygame.Rect(x, y, cell, cell)
                if not self.grid.colliderect(r):
                    continue
                canvas.blit(frames[idx], frames[idx].get_rect(center=r.center))
                pygame.draw.rect(canvas, (60, 60, 72), r, 1)
                num = self.ctx.fonts["small"].render(str(idx), True, (230, 230, 230))
                canvas.blit(num, (r.x + 2, r.y + 1))
                if idx in active_frames:
                    pygame.draw.rect(canvas, STATE_COLORS.get(self.active, ACCENT),
                                     r, 3)
                # dots for membership in the other states
                dx = r.right - 8
                for name in self.states:
                    if name == self.active:
                        continue
                    if idx in self.frames[name]:
                        pygame.draw.circle(canvas, STATE_COLORS.get(name, ACCENT),
                                           (dx, r.y + 8), 4)
                        dx -= 10
        total = cols * rows
        info = self.ctx.fonts["small"].render(
            "{} frames in sheet - {} assigned to {}".format(
                total, len(self.frames[self.active]), self.active), True, DIM)
        canvas.blit(info, (self.grid.x, self.grid.bottom + 4))
        if rows > visible:
            inner = self.grid.height - 8
            bar_h = max(24, int(inner * visible / rows))
            denom = max(1, rows - visible)
            y = self.grid.y + 4 + int((inner - bar_h) * (self.scroll / denom))
            pygame.draw.rect(canvas, EDGE, (self.grid.right - 6, y, 4, bar_h),
                             border_radius=2)


# ---------------------------------------------------------------------------
# sprite flows (icon click -> static/animation -> pick -> edit)
# ---------------------------------------------------------------------------
def _static_image_of(spec):
    if isinstance(spec, dict):
        if spec.get("kind") == "image":
            return spec
        if spec.get("kind") == "sprites" and spec.get("image"):
            return spec["image"]
    return None


def _animations_of(spec):
    if isinstance(spec, dict) and spec.get("kind") == "sprites":
        return {k: dict(v) for k, v in (spec.get("animations") or {}).items()}
    return {}


def _start_dir(path):
    return path.rsplit("/", 1)[0] if isinstance(path, str) and "/" in path else ""


def open_unit_sprite_flow(ctx, current_spec, on_result, sheets=()):
    """Ask static/animation/sheet-tile, pick a file, maybe edit states."""
    image = _static_image_of(current_spec)
    animations = _animations_of(current_spec)

    def finalise(image_spec, anims):
        if anims:
            on_result({"kind": "sprites", "image": image_spec, "animations": anims})
        else:
            on_result(image_spec or {"kind": "pack", "tile": 226})

    def pick_static():
        ctx.open_modal(FileBrowser(ctx, lambda path: finalise(
            {"kind": "image", "path": path}, animations),
            start=_start_dir(image.get("path") if image else "")))

    def pick_sheet():
        def picked(path):
            def saved(sheet, fw, fh, margin, spacing, chosen):
                anims = {
                    name: {"kind": "sheet", "path": sheet, "frame_w": fw,
                           "frame_h": fh, "margin": margin, "spacing": spacing,
                           "frames": a["frames"], "fps": a["fps"],
                           "loop": a["loop"]}
                    for name, a in chosen.items()
                }
                on_result({"kind": "sprites", "image": image, "animations": anims})
            ctx.open_modal(AnimationEditor(ctx, path, saved,
                                           states=ANIMATION_STATES,
                                           frames_by_state=animations))
        ctx.open_modal(FileBrowser(ctx, picked))

    def choose(kind):
        if kind == "static":
            pick_static()
        elif kind == "sheet":
            # one frame from an imported sheet becomes the unit's static
            # image; any existing state animations are kept
            ctx.open_modal(SheetTilePicker(ctx, sheets,
                                           lambda spec: finalise(spec, animations)))
        else:
            pick_sheet()

    ctx.open_modal(SpriteKindDialog(ctx, choose))


def open_terrain_sprite_flow(ctx, current_spec, on_result, sheets=()):
    """Terrain variant: a single looping animation (no named states)."""

    def save_static(path):
        on_result({"kind": "image", "path": path})

    def pick_sheet():
        def picked(path):
            prefill = {}
            if (isinstance(current_spec, dict) and current_spec.get("kind") == "sheet"
                    and current_spec.get("path") == path):
                raw = current_spec.get("frames")
                frames = raw if isinstance(raw, list) else list(range(int(raw or 1)))
                prefill["anim"] = {"frames": frames,
                                   "fps": current_spec.get("fps", 8.0),
                                   "loop": current_spec.get("loop", True)}

            def saved(sheet, fw, fh, margin, spacing, chosen):
                a = chosen.get("anim") or next(iter(chosen.values()), None)
                if not a:
                    return
                on_result({"kind": "sheet", "path": sheet, "frame_w": fw,
                           "frame_h": fh, "margin": margin, "spacing": spacing,
                           "frames": a["frames"], "fps": a["fps"],
                           "loop": a["loop"]})
            ctx.open_modal(AnimationEditor(ctx, path, saved, states=["anim"],
                                           frames_by_state=prefill, simple=True))
        ctx.open_modal(FileBrowser(ctx, picked))

    def choose(kind):
        if kind == "static":
            ctx.open_modal(FileBrowser(ctx, save_static, start=_start_dir(
                current_spec.get("path") if isinstance(current_spec, dict) else "")))
        elif kind == "sheet":
            # one frame from an imported sheet, used directly as the art
            ctx.open_modal(SheetTilePicker(ctx, sheets, on_result))
        else:
            pick_sheet()

    ctx.open_modal(SpriteKindDialog(ctx, choose))

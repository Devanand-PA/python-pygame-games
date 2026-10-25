"""Story dialogue runtime: portrait dialogue box + full-screen cutscenes.

Two overlay scenes, both pushed onto ``game.subscenes`` (which automatically
pauses the GameScene underneath, because :meth:`Game.on_update` only ticks the
top-most subscene):

``Cutscene``
    A full-screen slideshow used for a level's intro and its victory/defeat
    outro.  Each slide shows an optional image (letterboxed to the canvas,
    aspect preserved), an optional caption above it, and a speaker name +
    word-wrapped text block near the bottom.

``DialogueBox``
    The classic in-game portrait box pinned to the bottom of the canvas: a
    square speaker portrait on the left (or right, per the line's ``side``),
    the speaker's name, and wrapped text.  Used for scripted checkpoints.

Input (both scenes): click / Space / Enter / Right-arrow advances, Left-arrow
steps back one entry, Esc skips the whole sequence.  ``on_finish`` /
``on_done`` fires exactly once, after the overlay has removed itself from the
subscene stack.

Every image is loaded through :func:`engine.art.image`, which degrades to a
placeholder if the file is missing -- a broken portrait can never crash the
game.
"""
import pygame

from core.scene import Scene
from core import settings as S
from engine import art

# ---------------------------------------------------------------- palette ---
BACKDROP = (12, 12, 18)
PANEL = (24, 24, 34)
PANEL_EDGE = (96, 92, 124)
TEXT = (238, 238, 240)
DIM = (168, 168, 182)
ACCENT = (120, 176, 240)
PORTRAIT_BG = (34, 34, 46)


# ------------------------------------------------------------- text utils ---
def wrap_text(text, font, max_width):
    """Word-wrap ``text`` to ``font``; returns a list of lines (never empty)."""
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


def fit_surface(surf, box_w, box_h):
    """Scale ``surf`` to fit inside (box_w, box_h), preserving aspect."""
    if surf is None or box_w <= 0 or box_h <= 0:
        return None
    w, h = surf.get_size()
    scale = min(box_w / w, box_h / h)
    size = (max(1, int(w * scale)), max(1, int(h * scale)))
    if size == (w, h):
        return surf
    return pygame.transform.smoothscale(surf, size)


def load_image(path):
    """Load an assets-relative image; None for empty paths, placeholder for
    broken ones (delegates the placeholder to :func:`engine.art.image`)."""
    if not path:
        return None
    try:
        return art.image(str(path))
    except Exception:                                  # noqa: BLE001
        return None


class _StoryOverlay(Scene):
    """Shared plumbing: an ordered list of entries, advance/skip, on-finish."""

    def __init__(self, game, entries, on_done=None):
        super().__init__(game)
        self.entries = [e for e in (entries or []) if e]
        self.index = 0
        self.on_done = on_done
        self._done = False

    # -- lifecycle ----------------------------------------------------------
    @property
    def current(self):
        if 0 <= self.index < len(self.entries):
            return self.entries[self.index]
        return None

    def _advance(self):
        if self.index + 1 < len(self.entries):
            self.index += 1
        else:
            self.finish()

    def _step_back(self):
        if self.index > 0:
            self.index -= 1

    def finish(self):
        """Remove this overlay and fire the callback exactly once."""
        if self._done:
            return
        self._done = True
        if self in self.game.subscenes:
            self.game.subscenes.remove(self)
        callback, self.on_done = self.on_done, None
        if callback is not None:
            callback()

    # -- input --------------------------------------------------------------
    _ADVANCE_KEYS = (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER,
                     pygame.K_RIGHT)

    def handle_event(self, event):
        if self._done or not self.entries:
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.game.play("click", 0.3)
                self.finish()
            elif event.key in self._ADVANCE_KEYS:
                self.game.play("click", 0.3)
                self._advance()
            elif event.key == pygame.K_LEFT:
                self._step_back()
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.game.play("click", 0.3)
            self._advance()

    # -- shared drawing -----------------------------------------------------
    def _draw_veil(self, alpha=150):
        veil = pygame.Surface(self.game.canvas.get_size(), pygame.SRCALPHA)
        veil.fill((0, 0, 0, alpha))
        self.game.canvas.blit(veil, (0, 0))

    def _draw_hint(self, bottom_y, skip_label="Esc: skip"):
        canvas = self.game.canvas
        small = self.game.fonts["small"]
        progress = f"{self.index + 1}/{len(self.entries)}"
        hint = small.render(f"click / Space: next    {skip_label}", True, DIM)
        canvas.blit(hint, hint.get_rect(midbottom=(canvas.get_width() - 24,
                                                   bottom_y)))
        count = small.render(progress, True, DIM)
        canvas.blit(count, count.get_rect(midtop=(canvas.get_width() - 24, 16)))


class DialogueBox(_StoryOverlay):
    """Bottom portrait box for checkpoint dialogues.

    ``lines`` is one checkpoint's line list (already normalized by
    :func:`core.content.normalize_script`): dicts with ``speaker``, ``text``,
    ``image`` and ``side``.
    """

    BOX_H = 196
    PORTRAIT = 140
    MARGIN = 40

    def __init__(self, game, lines, on_finish=None):
        super().__init__(game, list(lines) if lines else [], on_finish)
        w, h = game.canvas.get_size()
        self.box = pygame.Rect(self.MARGIN, h - self.BOX_H - 26,
                               w - 2 * self.MARGIN, self.BOX_H)
        self.portrait_rect = pygame.Rect(0, 0, self.PORTRAIT, self.PORTRAIT)
        self.portrait_rect.midleft = (self.box.x + 22, self.box.centery)
        self.text_rect = pygame.Rect(
            self.portrait_rect.right + 26, self.box.y + 14,
            self.box.right - 26 - (self.portrait_rect.right + 26),
            self.box.height - 52)

    # -- drawing ------------------------------------------------------------
    def on_draw(self):
        line = self.current
        if line is None:
            return
        canvas = self.game.canvas
        self._draw_veil(120)
        # keep the line's image on the requested side by mirroring the layout
        box = pygame.Rect(self.box)
        portrait = pygame.Rect(self.portrait_rect)
        text = pygame.Rect(self.text_rect)
        if line.get("side") == "right":
            portrait.midright = (box.right - 22, box.centery)
            text = pygame.Rect(box.x + 26, box.y + 14,
                               portrait.left - 26 - box.x - 26,
                               box.height - 52)

        pygame.draw.rect(canvas, PANEL, box, border_radius=12)
        pygame.draw.rect(canvas, PANEL_EDGE, box, 3, border_radius=12)

        self._draw_portrait(line.get("image"), portrait)
        self._draw_text(line, text)
        self._draw_hint(box.bottom - 12)
        # advance arrow at the bottom-right corner of the box
        arrow = self.game.fonts["small"].render("▼", True, ACCENT)
        canvas.blit(arrow, arrow.get_rect(midbottom=(box.right - 34,
                                                     box.bottom - 16)))

    def _draw_portrait(self, image_path, rect):
        canvas = self.game.canvas
        pygame.draw.rect(canvas, PORTRAIT_BG, rect, border_radius=8)
        pygame.draw.rect(canvas, PANEL_EDGE, rect, 2, border_radius=8)
        surf = load_image(image_path)
        if surf is not None:
            fitted = fit_surface(surf, rect.width - 12, rect.height - 12)
            if fitted is not None:
                canvas.blit(fitted, fitted.get_rect(center=rect.center))

    def _draw_text(self, line, rect):
        canvas = self.game.canvas
        default = self.game.fonts["default"]
        small = self.game.fonts["small"]
        y = rect.y
        speaker = (line.get("speaker") or "").strip()
        if speaker:
            surf = default.render(speaker, True, ACCENT)
            canvas.blit(surf, (rect.x, y))
            y += surf.get_height() + 6
        body = (line.get("text") or "").strip() or "…"
        # try the comfortable font first; fall back to the small one when the
        # text would not fit the box
        for font in (default, small):
            wrapped = wrap_text(body, font, rect.width)
            line_h = font.get_height() + 4
            if y + line_h * len(wrapped) <= rect.bottom:
                break
        for text_line in wrapped:
            if y > rect.bottom:
                break
            surf = font.render(text_line, True, TEXT)
            canvas.blit(surf, (rect.x, y))
            y += line_h


class Cutscene(_StoryOverlay):
    """Full-screen slideshow for a level's intro / victory / defeat story."""

    def __init__(self, game, slides, on_done=None):
        super().__init__(game, slides, on_done)
        w, h = game.canvas.get_size()
        self.canvas_size = (w, h)
        self.stage = pygame.Rect(60, 70, w - 120, h - 220)

    # -- drawing ------------------------------------------------------------
    def on_draw(self):
        slide = self.current
        if slide is None:
            return
        canvas = self.game.canvas
        w, h = self.canvas_size
        canvas.fill(BACKDROP)

        caption = (slide.get("caption") or "").strip()
        speaker = (slide.get("speaker") or "").strip()
        body = (slide.get("text") or "").strip()
        surf = load_image(slide.get("image"))

        # the image takes the stage; without one, the text panel still fills
        # the lower area so the slide never looks broken
        stage = pygame.Rect(self.stage)
        if surf is not None:
            fitted = fit_surface(surf, stage.width, stage.height)
            if fitted is not None:
                canvas.blit(fitted, fitted.get_rect(center=stage.center))
        elif not caption and not speaker and not body:
            # completely empty slide: show its number so it is not a black void
            big = self.game.fonts["title"].render(
                f"{self.index + 1}", True, (52, 52, 66))
            canvas.blit(big, big.get_rect(center=stage.center))

        y_text = stage.bottom + 18
        if caption:
            csurf = self.game.fonts["small"].render(caption, True, DIM)
            canvas.blit(csurf, csurf.get_rect(midtop=(w // 2, 24)))
        if speaker or body:
            panel = pygame.Rect(0, 0, w - 240, h - y_text - 56)
            panel.midtop = (w // 2, y_text)
            pygame.draw.rect(canvas, PANEL, panel, border_radius=12)
            pygame.draw.rect(canvas, PANEL_EDGE, panel, 2, border_radius=12)
            ty = panel.y + 14
            if speaker:
                ssurf = self.game.fonts["default"].render(speaker, True, ACCENT)
                canvas.blit(ssurf, (panel.x + 22, ty))
                ty += ssurf.get_height() + 6
            if body:
                for font in (self.game.fonts["default"],
                             self.game.fonts["small"]):
                    wrapped = wrap_text(body, font, panel.width - 44)
                    line_h = font.get_height() + 5
                    if ty + line_h * len(wrapped) <= panel.bottom - 10:
                        break
                for text_line in wrapped:
                    if ty > panel.bottom - 10:
                        break
                    canvas.blit(font.render(text_line, True, TEXT),
                                (panel.x + 22, ty))
                    ty += line_h
        self._draw_hint(h - 24)

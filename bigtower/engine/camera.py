"""Camera: a scrolling window onto the level.

The game draws the world in *map space* (pixel 0,0 is the top-left tile) onto a
rectangular region of the canvas called the *viewport* -- everything below it
belongs to the HUD.  A camera maps map space into that viewport via a single
offset, so the renderer just draws everything a little to the left/up and the
world appears to slide.

Two properties make it forgiving:

* If the map is smaller than the viewport the camera *centres* it instead of
  clamping to 0, so a small level is never pinned to a top-left corner.
* Movement is eased: panning sets a target and :meth:`update` chases it, which
  keeps dragging and edge-scrolling from feeling twitchy.
"""
import pygame

from core import settings as S


class Camera:
    def __init__(self, viewport, map_size, speed=S.CAMERA_SPEED,
                 ease=S.CAMERA_EASE):
        self.viewport = pygame.Rect(viewport)
        self.map_size = (0, 0)
        self.x = 0.0
        self.y = 0.0
        self._tx = 0.0
        self._ty = 0.0
        self.speed = float(speed)
        self.ease = float(ease)
        self.set_map_size(map_size)

    # ------------------------------------------------------------------ size
    @property
    def view_size(self):
        return (self.viewport.width, self.viewport.height)

    def set_map_size(self, size):
        self.map_size = (max(0, int(size[0])), max(0, int(size[1])))
        self.center()

    # ---------------------------------------------------------------- bounds
    def _limits(self):
        """Return ``(min_x, max_x, min_y, max_y)`` for the current offset.

        When the map is smaller than the viewport on an axis the min equals the
        max, which centres that axis instead of pinning it.
        """
        vw, vh = self.view_size
        mw, mh = self.map_size
        if mw <= vw:
            centre_x = (vw - mw) / 2.0
            min_x = max_x = centre_x
        else:
            min_x, max_x = 0.0, float(mw - vw)
        if mh <= vh:
            centre_y = (vh - mh) / 2.0
            min_y = max_y = centre_y
        else:
            min_y, max_y = 0.0, float(mh - vh)
        return min_x, max_x, min_y, max_y

    @property
    def scrollable(self):
        """True when the map is larger than the viewport on either axis."""
        vw, vh = self.view_size
        mw, mh = self.map_size
        return mw > vw or mh > vh

    def clamp(self):
        min_x, max_x, min_y, max_y = self._limits()
        self.x = min(max(self.x, min_x), max_x)
        self.y = min(max(self.y, min_y), max_y)

    def clamp_target(self):
        min_x, max_x, min_y, max_y = self._limits()
        self._tx = min(max(self._tx, min_x), max_x)
        self._ty = min(max(self._ty, min_y), max_y)

    # -------------------------------------------------------------- movement
    @property
    def target(self):
        return (self._tx, self._ty)

    def scroll_to(self, x, y):
        """Jump the camera (and its target) to an absolute offset."""
        self._tx, self._ty = float(x), float(y)
        self.x, self.y = self._tx, self._ty
        self.clamp()
        self._tx, self._ty = self.x, self.y

    def pan_by(self, dx, dy):
        """Move the *target* by a delta, in pixels."""
        self._tx += dx
        self._ty += dy
        self.clamp_target()

    def pan_screen(self, dx, dy, dt):
        """Pan by a per-frame delta derived from ``dx``/``dy`` direction keys."""
        self.pan_by(dx * self.speed * dt, dy * self.speed * dt)

    def center(self):
        """Return to the home view: the top-left of the map, or the middle of
        it when it is smaller than the viewport (see :meth:`_limits`)."""
        min_x, _max_x, min_y, _max_y = self._limits()
        self.scroll_to(min_x, min_y)

    def center_on(self, world_pos):
        """Centre the viewport on a map-space point."""
        vw, vh = self.view_size
        self.pan_by(world_pos[0] - (self.x + vw / 2.0),
                    world_pos[1] - (self.y + vh / 2.0))
        self.snap()

    def snap(self):
        """Jump the visible offset straight to the target (drag / jump-to feel)."""
        self.clamp_target()
        self.x, self.y = self._tx, self._ty

    def drag_to(self, world_pos, grab_offset):
        """Keep ``grab_offset`` (a map point) under the cursor at ``world_pos``."""
        self.pan_by(grab_offset[0] - world_pos[0], grab_offset[1] - world_pos[1])
        self.snap()

    def update(self, dt):
        """Ease the visible offset toward the target."""
        if dt <= 0.0:
            return
        k = min(1.0, self.ease * dt)
        self.x += (self._tx - self.x) * k
        self.y += (self._ty - self.y) * k
        if abs(self._tx - self.x) < 0.05:
            self.x = self._tx
        if abs(self._ty - self.y) < 0.05:
            self.y = self._ty

    # ----------------------------------------------------------- conversions
    @property
    def offset(self):
        """Integer ``(dx, dy)`` camera scroll, in pixels.

        This is the amount to **subtract** from a map coordinate to reach the
        viewport (see :meth:`world_to_screen`).  Pass it straight to the world
        ``draw(..., offset=...)`` calls, which all follow the same rule.
        """
        return (int(round(self.x)), int(round(self.y)))

    def screen_to_world(self, pos):
        ox, oy = self.offset
        return (int(pos[0] - self.viewport.x + ox),
                int(pos[1] - self.viewport.y + oy))

    def world_to_screen(self, pos):
        ox, oy = self.offset
        return (int(pos[0] - ox + self.viewport.x),
                int(pos[1] - oy + self.viewport.y))

    # ---------------------------------------------------------------- culling
    def is_visible(self, pos, margin=0):
        """True when a map-space point (optionally padded) falls in the viewport."""
        ox, oy = self.offset
        vw, vh = self.view_size
        return (self.viewport.x - margin <= pos[0] - ox <= self.viewport.right + margin
                and self.viewport.y - margin <= pos[1] - oy <= self.viewport.bottom + margin)

    def is_rect_visible(self, rect, margin=0):
        ox, oy = self.offset
        left = self.viewport.x - ox - margin
        top = self.viewport.y - oy - margin
        return (rect.right >= left and rect.left <= self.viewport.x - ox
                + self.viewport.width + margin
                and rect.bottom >= top
                and rect.top <= self.viewport.y - oy + self.viewport.height + margin)

    # ------------------------------------------------------------- minimap box
    def minimap_view_rect(self, box):
        """The viewport's outline expressed inside a minimap ``box``."""
        mw, mh = self.map_size
        if mw <= 0 or mh <= 0:
            return pygame.Rect(box)
        sx = box.width / mw
        sy = box.height / mh
        vw, vh = self.view_size
        return pygame.Rect(
            int(box.x + self.x * sx), int(box.y + self.y * sy),
            max(6, min(box.width, int(vw * sx))),
            max(6, min(box.height, int(vh * sy))))

    def minimap_click(self, box, pos):
        """Map a click inside a minimap ``box`` to the map point to centre on."""
        mw, mh = self.map_size
        if mw <= 0 or mh <= 0:
            return None
        sx = mw / box.width
        sy = mh / box.height
        return (int((pos[0] - box.x) * sx), int((pos[1] - box.y) * sy))
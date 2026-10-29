"""Sprite loading, tinting and rotation caching.

Kenney tiles come from assets/packs/kenney_tower-defense-top-down; custom art
lives under assets/units.  Sprites face UP by default in the pack, so rot()
returns pre-rotated copies and per-frame rotation never happens twice for the
same angle bucket.

Units describe their art with a small *sprite spec* (see core.content):

    {"kind": "pack",  "tile": 226}
    {"kind": "image", "path": "units/towers/forest-towers/scorpion-tower/scorpion-001.png"}
    {"kind": "shape", "shape": "circle", "color": [200, 120, 120]}

:func:`sprite` turns any spec into a scaled, optionally tinted surface.
"""
import math
import pathlib

import pygame

from core import paths

_cache = {}
_rot_cache = {}
_alpha_cache = {}


def _surface_key(surf: pygame.Surface, name=None) -> tuple:
    """A stable identity for a surface's pixels (a replacement for ``id``).

    ``id()`` is unsafe as a cache key for the temporary frame surfaces that
    :func:`_sheet_frames` creates: they die immediately, the next allocation
    reuses the address, and the stale entry is then served for a different
    frame -- the sprite would silently keep showing the wrong tile.  When the
    caller knows what the surface *is* (a sheet crop, a pack tile, a loaded
    image) it passes that name in, which is both stable and free.  Anything
    unnamed falls back to a hash of its pixels.
    """
    if name is not None:
        return ("named", str(name))
    return ("raw", surf.get_size(), surf.get_bitsize(),
            hash(pygame.image.tobytes(surf, "RGBA")))


def tile(num: int) -> pygame.Surface:
    """Load a Kenney tile by its number (towerDefense_tile0NN.png)."""
    key = ("tile", num)
    if key not in _cache:
        path = paths.PACK_DIR / f"towerDefense_tile{num:03d}.png"
        surf = pygame.image.load(str(path)).convert_alpha()
        _cache[key] = surf
    return _cache[key]


def image(rel_path: str) -> pygame.Surface:
    """Load an arbitrary PNG from assets/ (or an absolute path)."""
    key = ("image", rel_path)
    if key not in _cache:
        p = pathlib.Path(rel_path)
        if not p.is_absolute():
            p = paths.asset(*str(rel_path).replace("\\", "/").split("/"))
        try:
            surf = pygame.image.load(str(p)).convert_alpha()
        except (pygame.error, FileNotFoundError):
            surf = pygame.Surface((48, 48), pygame.SRCALPHA)
            pygame.draw.circle(surf, (210, 90, 90), (24, 24), 20, 3)
        _cache[key] = surf
    return _cache[key]


def custom(name: str, size: int) -> pygame.Surface:
    """Backwards-compatible helper for the two original forest towers."""
    return sprite({"kind": "image",
                   "path": f"units/towers/forest-towers/{name}-tower/{name}-001.png"},
                  size)


def shape_surface(shape: str, color) -> pygame.Surface:
    """Draw a simple placeholder sprite (circle / square / diamond / triangle)."""
    key = ("shape", shape, tuple(color))
    if key not in _cache:
        surf = pygame.Surface((64, 64), pygame.SRCALPHA)
        col = tuple(color[:3])
        edge = tuple(max(0, c - 70) for c in col)
        if shape == "square":
            pygame.draw.rect(surf, col, (10, 10, 44, 44), border_radius=6)
            pygame.draw.rect(surf, edge, (10, 10, 44, 44), 3, border_radius=6)
        elif shape == "diamond":
            pts = [(32, 6), (58, 32), (32, 58), (6, 32)]
            pygame.draw.polygon(surf, col, pts)
            pygame.draw.polygon(surf, edge, pts, 3)
        elif shape == "triangle":
            pts = [(32, 6), (58, 56), (6, 56)]
            pygame.draw.polygon(surf, col, pts)
            pygame.draw.polygon(surf, edge, pts, 3)
        else:
            pygame.draw.circle(surf, col, (32, 32), 24)
            pygame.draw.circle(surf, edge, (32, 32), 24, 3)
        _cache[key] = surf
    return _cache[key]


def scaled(surf: pygame.Surface, size, name=None) -> pygame.Surface:
    # Key by content, not id(): _sheet_frames hands us a freshly allocated
    # temporary Surface each call, and once it is garbage collected Python
    # reuses the address -- so id(surf) collisions made later frames return
    # an earlier frame's cached (wrong) pixels.
    key = ("scaled", _surface_key(surf, name), size)
    if key not in _cache:
        _cache[key] = pygame.transform.smoothscale(surf, size)
    return _cache[key]


def tinted(surf: pygame.Surface, color, name=None) -> pygame.Surface:
    """Multiply a surface's colours by ``color`` (keeps alpha)."""
    key = ("tint", _surface_key(surf, name), tuple(color[:3]))
    if key not in _cache:
        out = surf.copy()
        out.fill(tuple(color[:3]) + (255,), special_flags=pygame.BLEND_RGBA_MULT)
        _cache[key] = out
    return _cache[key]


def _is_sheet_like(spec):
    """True for a ``sheet`` spec, or a kind-less animation/sheet dict."""
    if not isinstance(spec, dict):
        return False
    if spec.get("kind") == "sheet":
        return True
    return spec.get("kind") is None and "path" in spec and "frames" in spec


def _resolve_animation(spec, name):
    """Pick which named animation a ``sprites`` spec should show."""
    anims = spec.get("animations") or {}
    if name and name in anims:
        return name
    if "idle" in anims:
        return "idle"
    return next(iter(anims), None)


def animation_names(spec):
    """The animation state names a spec defines (empty for static art)."""
    if isinstance(spec, dict) and spec.get("kind") == "sprites":
        return list((spec.get("animations") or {}).keys())
    return []


def sprite(spec, size: int, tint=None, frame: int = 0, name=None) -> pygame.Surface:
    """Resolve a sprite spec into one scaled (and optionally tinted) surface."""
    frames = sprite_frames(spec, size, tint, name=name)
    return frames[frame % len(frames)]


def sprite_frames(spec, size: int, tint=None, name=None):
    """Every frame of a sprite spec as a list of scaled surfaces.

    Static specs return a one-element list; ``anim`` and ``sheet`` specs return
    their frames in order.  A ``sprites`` spec resolves the requested ``name``
    (falling back to ``idle``, the first animation, then its static image).
    Custom PNGs are loaded relative to ``assets/``.
    """
    if spec is None or isinstance(spec, int):
        spec = {"kind": "pack", "tile": 226 if spec is None else spec}
    if not isinstance(spec, dict):
        spec = {"kind": "pack", "tile": 226}
    kind = spec.get("kind", "pack")
    if kind == "sprites":
        anim_name = _resolve_animation(spec, name)
        if anim_name is not None:
            return _sheet_frames(spec["animations"][anim_name], size, tint)
        image = spec.get("image")
        if image:
            return sprite_frames(image, size, tint)
        return [_finish(shape_surface("circle", [200, 200, 200]), size,
                      tint, ("circle", 200, 200, 200))]
    if kind == "anim":
        frames = [sprite_frames(f, size, tint)[0]
                  for f in (spec.get("frames") or [])]
        return frames or [_finish(shape_surface("circle", [200, 200, 200]),
                                   size, tint, ("circle", 200, 200, 200))]
    if _is_sheet_like(spec):
        return _sheet_frames(spec, size, tint)
    return [_finish(_base_surface(spec), size, tint, _base_name(spec))]


def _base_name(spec):
    """Stable name for a static spec's base surface (pack tile / image / shape)."""
    kind = spec.get("kind", "pack") if isinstance(spec, dict) else "pack"
    if kind == "image":
        return ("image", spec.get("path", ""))
    if kind == "shape":
        return ("shape", spec.get("shape", "circle"),
                tuple(spec.get("color") or [200, 200, 200]))
    return ("tile", int(spec.get("tile", 226) or 226))


def _base_surface(spec) -> pygame.Surface:
    kind = spec.get("kind", "pack")
    if kind == "image":
        return image(spec.get("path", ""))
    if kind == "shape":
        return shape_surface(spec.get("shape", "circle"),
                             spec.get("color") or [200, 200, 200])
    return tile(int(spec.get("tile", 226)))


def _finish(surf: pygame.Surface, size, tint, name=None) -> pygame.Surface:
    out = scaled(surf, (size, size), name)
    return tinted(out, tint, name) if tint else out


def _frame_indices(spec, cols, rows):
    """The frame indices a sheet/animation spec selects, in order."""
    raw = spec.get("frames", cols * rows)
    if isinstance(raw, (list, tuple)):
        return [max(0, int(i)) for i in raw]
    return list(range(max(1, int(raw))))


def _sheet_grid(spec):
    """``(cols, rows)`` for a sheet spec based on the image and frame size."""
    sheet = image(spec.get("path", ""))
    fw = max(1, int(spec.get("frame_w", 32)))
    fh = max(1, int(spec.get("frame_h", 32)))
    spacing = max(0, int(spec.get("spacing", 0)))
    margin = max(0, int(spec.get("margin", 0)))
    cols = int(spec.get("cols", 0)) or max(
        1, (sheet.get_width() - 2 * margin + spacing) // (fw + spacing))
    rows = int(spec.get("rows", 0)) or max(
        1, (sheet.get_height() - 2 * margin + spacing) // (fh + spacing))
    return cols, rows


def _sheet_frames(spec, size, tint):
    """Slice a spritesheet (row-major) into its selected frames."""
    sheet = image(spec.get("path", ""))
    fw = max(1, int(spec.get("frame_w", 32)))
    fh = max(1, int(spec.get("frame_h", 32)))
    spacing = max(0, int(spec.get("spacing", 0)))
    margin = max(0, int(spec.get("margin", 0)))
    cols, rows = _sheet_grid(spec)
    frames = []
    for i in _frame_indices(spec, cols, rows):
        c, r = i % cols, i // cols
        rect = pygame.Rect(margin + c * (fw + spacing),
                           margin + r * (fh + spacing), fw, fh)
        frame = pygame.Surface((fw, fh), pygame.SRCALPHA)
        frame.blit(sheet, (0, 0), rect)
        # the crop is named, so the scaled/tinted caches key on (sheet, frame
        # geometry, index) instead of the id() of this throw-away Surface
        key = (spec.get("path"), fw, fh, margin, spacing, cols, i)
        frames.append(_finish(frame, size, tint, key))
    if not frames:
        return [_finish(sheet, size, tint, ("whole", spec.get("path"), size))]
    return frames


def frame_count(spec, name=None) -> int:
    """Number of frames a spec has (1 for static art)."""
    if not isinstance(spec, dict):
        return 1
    kind = spec.get("kind")
    if kind == "sprites":
        anim_name = _resolve_animation(spec, name)
        if anim_name is not None:
            return frame_count(spec["animations"][anim_name])
        return frame_count(spec["image"]) if spec.get("image") else 1
    if kind == "anim":
        return max(1, len(spec.get("frames") or []))
    if _is_sheet_like(spec):
        raw = spec.get("frames", 1)
        return max(1, len(raw)) if isinstance(raw, (list, tuple)) else max(1, int(raw))
    return 1


def fps(spec, default=8.0, name=None) -> float:
    """Frames per second a spec animates at."""
    if isinstance(spec, dict):
        kind = spec.get("kind")
        if kind == "sprites":
            anim_name = _resolve_animation(spec, name)
            if anim_name is not None:
                return fps(spec["animations"][anim_name], default)
            return fps(spec["image"], default) if spec.get("image") else default
        if kind == "anim" or _is_sheet_like(spec):
            try:
                return max(0.1, float(spec.get("fps", default)))
            except (TypeError, ValueError):
                return default
    return default


def loops(spec, name=None) -> bool:
    if not isinstance(spec, dict):
        return True
    if spec.get("kind") == "sprites":
        anim_name = _resolve_animation(spec, name)
        if anim_name is not None:
            return loops(spec["animations"][anim_name])
        return loops(spec["image"]) if spec.get("image") else True
    return bool(spec.get("loop", True))


def frame_index(spec, t: float, name=None) -> int:
    """Which frame a spec shows at time ``t`` seconds."""
    n = frame_count(spec, name)
    if n <= 1:
        return 0
    i = int(t * fps(spec, name=name))
    return i % n if loops(spec, name) else min(n - 1, i)


def sprite_alpha(surf: pygame.Surface, alpha: int) -> pygame.Surface:
    """Return a cached copy of ``surf`` with its alpha multiplied."""
    alpha = max(0, min(255, int(alpha)))
    key = ("alpha", id(surf), alpha)
    if key not in _alpha_cache:
        out = surf.copy()
        out.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
        _alpha_cache[key] = out
    return _alpha_cache[key]


def rot(surf: pygame.Surface, angle_deg: float, bucket: int = 6) -> pygame.Surface:
    """Rotate with caching; angles snap to `bucket` degrees."""
    snapped = int(round(angle_deg / bucket) * bucket) % 360
    key = (id(surf), snapped)
    if key not in _rot_cache:
        _rot_cache[key] = pygame.transform.rotate(surf, snapped)
    return _rot_cache[key]


def angle_between(frm, to) -> float:
    """Angle in degrees pointing from frm to to (0 = up, clockwise positive),
    matching pygame.transform.rotate on up-facing sprites."""
    dx, dy = to[0] - frm[0], to[1] - frm[1]
    if dx == 0 and dy == 0:
        return 0.0
    return math.degrees(math.atan2(dx, -dy))


def clear_caches():
    """Drop every cached surface (used after the designer edits content)."""
    _cache.clear()
    _rot_cache.clear()
    _alpha_cache.clear()

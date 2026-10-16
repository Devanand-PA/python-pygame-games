"""Sprite loading and rotation caching.

All Kenney tiles come from assets/packs/kenney_tower-defense-top-down.
Sprites face UP by default in the pack; rot() returns pre-rotated copies so
per-frame rotation never happens twice for the same angle bucket.
"""
import math

import pygame

from core import paths

_cache = {}
_rot_cache = {}


def tile(num: int) -> pygame.Surface:
    """Load a Kenney tile by its number (towerDefense_tile0NN.png)."""
    key = ("tile", num)
    if key not in _cache:
        path = paths.PACK_DIR / f"towerDefense_tile{num:03d}.png"
        surf = pygame.image.load(str(path)).convert_alpha()
        _cache[key] = surf
    return _cache[key]


def custom(name: str, size: int) -> pygame.Surface:
    """Load (and scale) a piece of custom art from assets/units."""
    key = ("custom", name, size)
    if key not in _cache:
        spots = [
            paths.asset("units", "towers", "forest-towers",
                        f"{name}-tower", f"{name}-001.png"),
        ]
        surf = None
        for path in spots:
            if path.exists():
                surf = pygame.image.load(str(path)).convert_alpha()
                break
        if surf is None:
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
        if surf.get_size() != (size, size):
            surf = pygame.transform.smoothscale(surf, (size, size))
        _cache[key] = surf
    return _cache[key]


def scaled(surf: pygame.Surface, size: (int, int)) -> pygame.Surface:
    key = ("scaled", id(surf), size)
    if key not in _cache:
        _cache[key] = pygame.transform.smoothscale(surf, size)
    return _cache[key]


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
    # up-facing sprite: 0 deg when pointing up (0,-1); clockwise positive
    return math.degrees(math.atan2(dx, -dy))

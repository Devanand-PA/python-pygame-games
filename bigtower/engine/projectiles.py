"""Projectiles: homing bullets and splash rockets, plus little hit/boom effects.

A projectile is fired by *any* unit (defender or attacker) and homes on its
target.  Splash projectiles damage every opposing unit within their radius, so
both sides can shell each other.
"""
import math

import pygame

from engine import art


class Projectile:
    def __init__(self, unit, target):
        self.side = unit.side
        self.pos = [unit.pos[0], unit.pos[1]]
        self.target = target
        self.last_target_pos = [target.pos[0], target.pos[1]]
        self.damage = unit.damage
        self.splash = unit.type.splash
        self.dead = False

        spec = unit.type.projectile_sprite
        if spec:
            self.speed = 300.0 if unit.type.projectile == "rocket" else 460.0
            self.sprite = art.sprite(spec, 14, unit.tint)
        elif unit.type.projectile == "rocket":
            self.speed = 300.0
            self.sprite = art.scaled(art.tile(252), (18, 18))
        else:
            self.speed = 460.0
            self.sprite = art.scaled(art.tile(272), (10, 10))

    def update(self, dt, targets, effects):
        """Home toward the target; on arrival damage it (or splash ``targets``)."""
        if self.dead:
            return
        if self.target is not None and self.target.alive:
            self.last_target_pos = [self.target.pos[0], self.target.pos[1]]
        tx, ty = self.last_target_pos
        dx, dy = tx - self.pos[0], ty - self.pos[1]
        dist = math.hypot(dx, dy)
        step = self.speed * dt
        if dist <= max(step, 6):
            self._hit(targets, effects)
            return
        self.pos[0] += dx / dist * step
        self.pos[1] += dy / dist * step

    def _hit(self, targets, effects):
        self.dead = True
        if self.splash:
            effects.append(("boom", list(self.pos)))
            for unit in targets:
                if not unit.alive:
                    continue
                d = math.hypot(unit.pos[0] - self.pos[0],
                               unit.pos[1] - self.pos[1])
                if d <= self.splash:
                    unit.take_hit(self.damage)
        else:
            if self.target is not None and self.target.alive:
                self.target.take_hit(self.damage)
                effects.append(("hit", list(self.pos)))

    def draw(self, canvas):
        if self.dead:
            return
        angle = art.angle_between(self.pos, self.last_target_pos)
        img = art.rot(self.sprite, angle)
        canvas.blit(img, img.get_rect(center=self.pos))


class Effects:
    """Expanding-ring / fading-puff effects (``boom`` and ``hit``)."""

    LIFE = {"boom": 0.35, "hit": 0.16}

    def __init__(self):
        self.items = []

    def append(self, effect):
        kind, pos = effect
        self.items.append({"kind": kind, "pos": list(pos), "t": 0.0})

    def update(self, dt):
        for item in self.items:
            item["t"] += dt
        self.items = [i for i in self.items
                      if i["t"] < self.LIFE.get(i["kind"], 0.35)]

    def draw(self, canvas):
        for item in self.items:
            life = self.LIFE.get(item["kind"], 0.35)
            frac = item["t"] / life
            if item["kind"] == "hit":
                radius = int(4 + 14 * frac)
                alpha = max(0, int(200 * (1 - frac)))
                pygame.draw.circle(canvas, (255, 240, 190, alpha), item["pos"],
                                   radius, 2)
                continue
            radius = int(8 + 40 * frac)
            alpha = max(0, int(180 * (1 - frac)))
            ring = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(ring, (255, 160, 60, alpha),
                               (radius, radius), radius, 3)
            pygame.draw.circle(ring, (255, 220, 120, alpha // 2),
                               (radius, radius), max(2, radius // 2))
            canvas.blit(ring, (item["pos"][0] - radius, item["pos"][1] - radius))

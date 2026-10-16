"""Projectiles: homing bullets and splash rockets with little boom effects."""
import math

import pygame

from engine import art


class Projectile:
    def __init__(self, tower, target):
        self.tower = tower
        self.pos = [tower.pos[0], tower.pos[1]]
        self.target = target
        self.last_target_pos = [target.pos[0], target.pos[1]]
        self.damage = tower.damage
        self.splash = tower.type.splash
        self.dead = False
        if tower.type.projectile == "rocket":
            self.speed = 300.0
            self.sprite = art.scaled(art.tile(252), (18, 18))
        else:
            self.speed = 460.0
            self.sprite = art.scaled(art.tile(272), (10, 10))
            if tower.type.key == "snakewatch":
                self.sprite = art.scaled(art.tile(273), (12, 12))
            elif tower.type.key == "scorpion":
                self.sprite = art.scaled(art.tile(272), (8, 8))

    def update(self, dt, enemies, effects):
        if self.dead:
            return
        # home in while the target lives, else fly to its last known spot
        if self.target is not None and self.target.alive:
            self.last_target_pos = [self.target.pos[0], self.target.pos[1]]
        tx, ty = self.last_target_pos
        dx, dy = tx - self.pos[0], ty - self.pos[1]
        dist = math.hypot(dx, dy)
        step = self.speed * dt
        if dist <= max(step, 6):
            self._hit(enemies, effects)
            return
        self.pos[0] += dx / dist * step
        self.pos[1] += dy / dist * step

    def _hit(self, enemies, effects):
        self.dead = True
        if self.splash:
            effects.append(("boom", list(self.pos)))
            for enemy in enemies:
                if not enemy.alive:
                    continue
                d = math.hypot(enemy.pos[0] - self.pos[0],
                               enemy.pos[1] - self.pos[1])
                if d <= self.splash:
                    enemy.take_hit(self.damage)
        else:
            if self.target is not None and self.target.alive:
                self.target.take_hit(self.damage)

    def draw(self, canvas):
        if self.dead:
            return
        angle = art.angle_between(self.pos, self.last_target_pos)
        img = art.rot(self.sprite, angle)
        canvas.blit(img, img.get_rect(center=self.pos))


class Effects:
    """Simple expanding-ring / fading-puff effects."""

    def __init__(self):
        self.items = []

    def append(self, effect):
        kind, pos = effect
        self.items.append({"kind": kind, "pos": pos, "t": 0.0})

    def update(self, dt):
        for item in self.items:
            item["t"] += dt
        self.items = [i for i in self.items if i["t"] < 0.35]

    def draw(self, canvas):
        for item in self.items:
            frac = item["t"] / 0.35
            radius = int(8 + 40 * frac)
            alpha = max(0, int(180 * (1 - frac)))
            ring = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(ring, (255, 160, 60, alpha),
                               (radius, radius), radius, 3)
            pygame.draw.circle(ring, (255, 220, 120, alpha // 2),
                               (radius, radius), max(2, radius // 2))
            canvas.blit(ring, (item["pos"][0] - radius, item["pos"][1] - radius))

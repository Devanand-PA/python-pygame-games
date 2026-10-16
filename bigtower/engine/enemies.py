"""Enemy units: ground units follow the path, flyers go straight to the base."""
import pygame

from core import settings as S
from engine import art


class EnemyType:
    def __init__(self, key, sprite, hp, speed, bounty, damage,
                 radius=16, flying=False, sprite_scale=1.0):
        self.key = key
        self.sprite = sprite
        self.hp = hp
        self.speed = speed
        self.bounty = bounty
        self.damage = damage
        self.radius = radius
        self.flying = flying
        self.sprite_scale = sprite_scale


ENEMY_TYPES = {
    "grunt":   EnemyType("grunt", 247, hp=42, speed=55, bounty=6, damage=1,
                         sprite_scale=1.6),
    "runner":  EnemyType("runner", 248, hp=30, speed=100, bounty=8, damage=1,
                         radius=14, sprite_scale=1.45),
    "armored": EnemyType("armored", 249, hp=130, speed=40, bounty=15, damage=2,
                         radius=18, sprite_scale=1.25),
    "jet":     EnemyType("jet", 270, hp=65, speed=130, bounty=13, damage=1,
                         radius=15, flying=True, sprite_scale=1.1),
    "tank":    EnemyType("tank", 250, hp=400, speed=28, bounty=45, damage=3,
                         radius=21, sprite_scale=1.4),
}


class Enemy:
    def __init__(self, etype: EnemyType, wave_number: int,
                 spawn_pos, base_pos, waypoints):
        self.type = etype
        self.max_hp = int(etype.hp * (1.0 + 0.10 * (wave_number - 1)))
        self.hp = self.max_hp
        self.speed = etype.speed
        self.pos = [spawn_pos[0], spawn_pos[1]]
        self.base_pos = base_pos
        self.flying = etype.flying
        self.radius = etype.radius
        self.alive = True
        self.reached_base = False

        if self.flying:
            self.route = [spawn_pos, base_pos]
        else:
            self.route = list(waypoints)
        self.route_index = 0
        self.heading = 0.0
        self._sprite = self._make_sprite()

    def _make_sprite(self):
        base = art.tile(self.type.sprite)
        size = int(S.TILE * self.type.sprite_scale)
        return art.scaled(base, (size, size))

    # ------------------------------------------------------------------ sim
    def update(self, dt):
        if not self.alive:
            return
        remaining = self.speed * dt
        while remaining > 0 and self.route_index < len(self.route):
            target = self.route[self.route_index]
            dx, dy = target[0] - self.pos[0], target[1] - self.pos[1]
            dist = (dx * dx + dy * dy) ** 0.5
            if dist <= remaining:
                self.pos[0], self.pos[1] = target
                remaining -= dist
                self.route_index += 1
            else:
                step = remaining / dist
                self.pos[0] += dx * step
                self.pos[1] += dy * step
                remaining = 0
            if dist > 0.001:
                self.heading = art.angle_between(self.pos, target)
        if self.route_index >= len(self.route):
            self.reached_base = True
            self.alive = False

    @property
    def progress(self):
        """How far along the route (for first-targeting)."""
        return self.route_index

    def take_hit(self, dmg):
        if not self.alive:
            return False
        self.hp -= dmg
        if self.hp <= 0:
            self.alive = False
            return True      # died
        return False

    # ------------------------------------------------------------------ draw
    def draw(self, canvas):
        if not self.alive:
            return
        img = art.rot(self._sprite, self.heading)
        canvas.blit(img, img.get_rect(center=self.pos))
        if self.hp < self.max_hp:
            w = max(20, self.radius * 2)
            frac = max(0.0, self.hp / self.max_hp)
            x = self.pos[0] - w // 2
            y = self.pos[1] - self.radius - 8
            pygame.draw.rect(canvas, (40, 40, 40), (x, y, w, 5))
            color = (120, 220, 120) if frac > 0.5 else (
                (240, 200, 60) if frac > 0.25 else (230, 80, 80))
            pygame.draw.rect(canvas, color, (x, y, int(w * frac), 5))

"""Towers: stats, upgrades, targeting, shooting."""
import pygame

from core import settings as S
from engine import art


class TowerType:
    def __init__(self, key, name, cost, sprite, sprite_scale=1.0,
                 custom_art=None, range=130, damage=9, cooldown=0.4,
                 projectile="dot", splash=0, sound="gun"):
        self.key = key
        self.name = name
        self.cost = cost
        self.sprite = sprite                # kenney tile number or None
        self.custom_art = custom_art        # name under assets/units/towers
        self.sprite_scale = sprite_scale
        self.range = range
        self.damage = damage
        self.cooldown = cooldown
        self.projectile = projectile        # dot | rocket
        self.splash = splash
        self.sound = sound


TOWER_TYPES = [
    TowerType("gun", "Gun Turret", cost=50, sprite=226,
              range=135, damage=9, cooldown=0.40, projectile="dot",
              sound="gun"),
    TowerType("scorpion", "Scorpion Den", cost=80, sprite=None,
              custom_art="scorpion", sprite_scale=0.92,
              range=105, damage=6, cooldown=0.20, projectile="dot",
              sound="sting"),
    TowerType("missile", "Missile Silo", cost=110, sprite=205,
              range=175, damage=30, cooldown=1.30, projectile="rocket",
              splash=56, sound="missile"),
    TowerType("snakewatch", "Snakewatch", cost=160, sprite=None,
              custom_art="snakewatch", sprite_scale=0.98,
              range=270, damage=70, cooldown=1.80, projectile="dot",
              sound="sniper"),
]
TOWER_BY_KEY = {t.key: t for t in TOWER_TYPES}


class Tower:
    def __init__(self, ttower: TowerType, cell, center):
        self.type = ttower
        self.cell = cell
        self.pos = center
        self.level = 1
        self.invested = ttower.cost
        self.cooldown_left = 0.0
        self.angle = 90.0      # facing down-toward path initially
        self.kills = 0
        self._sprite = self._make_sprite()

    # ---------------------------------------------------------------- stats
    def _make_sprite(self):
        size = int(S.TILE * self.type.sprite_scale)
        if self.type.custom_art:
            return art.custom(self.type.custom_art, size)
        return art.scaled(art.tile(self.type.sprite), (size, size))

    @property
    def damage(self):
        return self.type.damage * (1.6 ** (self.level - 1))

    @property
    def range(self):
        return self.type.range * (1.12 ** (self.level - 1))

    @property
    def cooldown(self):
        return self.type.cooldown * (0.82 ** (self.level - 1))

    def upgrade_cost(self):
        if self.level >= S.TOWER_MAX_LEVEL:
            return None
        return int(round(self.type.cost * 0.9 * self.level))

    def sell_value(self):
        return int(self.invested * S.SELL_RATIO)

    def upgrade(self):
        cost = self.upgrade_cost()
        if cost is None:
            return False
        self.level += 1
        self.invested += cost
        return True

    # ---------------------------------------------------------------- combat
    def update(self, dt, enemies, spawn_projectile):
        self.cooldown_left = max(0.0, self.cooldown_left - dt)
        target = self._pick_target(enemies)
        if target is not None:
            self.angle = art.angle_between(self.pos, target.pos)
            if self.cooldown_left <= 0:
                self.cooldown_left = self.cooldown
                spawn_projectile(self, target)
                return target
        return None

    def _pick_target(self, enemies):
        best = None
        best_score = -1
        rng2 = self.range * self.range
        for enemy in enemies:
            if not enemy.alive:
                continue
            dx = enemy.pos[0] - self.pos[0]
            dy = enemy.pos[1] - self.pos[1]
            if dx * dx + dy * dy > rng2:
                continue
            if enemy.progress > best_score:
                best_score = enemy.progress
                best = enemy
        return best

    # ------------------------------------------------------------------ draw
    def draw(self, canvas):
        img = art.rot(self._sprite, self.angle)
        canvas.blit(img, img.get_rect(center=self.pos))

    def draw_range(self, canvas):
        ring = pygame.Surface((self.range * 2 + 4, self.range * 2 + 4),
                              pygame.SRCALPHA)
        pygame.draw.circle(ring, (255, 255, 255, 40),
                           (ring.get_width() // 2, ring.get_height() // 2),
                           int(self.range))
        pygame.draw.circle(ring, (255, 255, 255, 120),
                           (ring.get_width() // 2, ring.get_height() // 2),
                           int(self.range), 2)
        canvas.blit(ring, (self.pos[0] - ring.get_width() // 2,
                           self.pos[1] - ring.get_height() // 2))

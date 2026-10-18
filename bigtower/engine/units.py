"""The unified unit: one class for towers *and* enemies.

A :class:`Unit` wraps a :class:`core.content.UnitType` and drives it with the
movement/attack rules taken from the type:

    movement  static  a fixed turret
              chase   a defender that walks after the nearest enemy
              route   an attacker that follows the map waypoints to the base
              direct  an attacker that flies straight at the base
              hunt    an attacker that leaves the path to chase a defender
    attack    none | melee | projectile   (projectiles are spawned by the scene)

Both sides can fight back, so enemies with an ``attack`` damage towers and
mobile defenders (the Scorpion) damage enemies.  ``update`` returns ``True`` on
the frames the unit fires so the scene can play its sound.
"""
import math

import pygame

from core import settings as S
from engine import art

FRAME_MOVE_EPS = 0.5


class Unit:
    def __init__(self, utype, pos, home=None, base_pos=None, waypoints=None,
                 wave_number=1, race_tint=None):
        self.type = utype
        self.side = utype.side
        self.attack = utype.attack
        self.speed = utype.speed
        self.pos = [float(pos[0]), float(pos[1])]
        self.home = home                        # a defender's build cell centre
        self.base_pos = base_pos                # an attacker's objective
        self.wave_number = int(wave_number or 1)
        self.tint = utype.tint or race_tint

        # movement bookkeeping
        self.waypoints = list(waypoints or [])
        self.wp_index = 1 if len(self.waypoints) > 1 else 0
        self.reached_base = False

        # combat / progression
        self.level = 1
        self.invested = int(utype.cost)
        self._wave_hp = 1.0 + 0.10 * (self.wave_number - 1) if self.side == "attacker" else 1.0
        self._wave_dmg = 1.0 + 0.08 * (self.wave_number - 1) if self.side == "attacker" else 1.0
        self._refresh_stats()
        self.hp = self.max_hp
        self.alive = True
        self._attack_timer = 0.0

        # animation
        self.size = max(12, int(S.TILE * utype.sprite_scale))
        self.radius = self.size / 2.0
        self._angle = 0.0
        self.anim_state = "idle"
        self._state_time = 0.0
        self._last_pos = (self.pos[0], self.pos[1])
        self._frames = art.sprite_frames(utype.sprite, self.size, self.tint)

    # -------------------------------------------------------------- stats
    def _refresh_stats(self):
        lv = self.level - 1
        self.damage = self.type.damage * (S.UNIT_DAMAGE_GAIN ** lv) * self._wave_dmg
        self.range = self.type.range * (S.UNIT_RANGE_GAIN ** lv)
        self.cooldown = max(0.05, self.type.cooldown * (S.UNIT_RATE_GAIN ** lv))
        self.max_hp = self.type.hp * (S.UNIT_HP_GAIN ** lv) * self._wave_hp

    def upgrade_cost(self):
        if self.level >= S.UNIT_MAX_LEVEL:
            return None
        return int(self.type.cost * (1.6 ** self.level))

    def upgrade(self):
        """Raise this tower one level; returns the gold spent (or 0)."""
        cost = self.upgrade_cost()
        if cost is None:
            return 0
        old_max = self.max_hp
        self.level += 1
        self.invested += cost
        self._refresh_stats()
        self.hp += (self.max_hp - old_max)
        return cost

    def sell_value(self):
        return int(self.invested * S.SELL_RATIO)

    # -------------------------------------------------------------- combat
    def take_hit(self, amount):
        if not self.alive:
            return
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.alive = False

    def _dist(self, other):
        return math.hypot(self.pos[0] - other[0], self.pos[1] - other[1])

    def _nearest(self, units):
        best, best_d = None, None
        for unit in units:
            if unit is self or not unit.alive or unit.side == self.side:
                continue
            d = self._dist(unit.pos)
            if best_d is None or d < best_d:
                best, best_d = unit, d
        return best

    def _pick_target(self, enemies):
        best, best_d = None, None
        reach = self.range
        for unit in enemies:
            if unit is self or not unit.alive or unit.side == self.side:
                continue
            d = self._dist(unit.pos)
            if d <= reach + unit.radius and (best_d is None or d < best_d):
                best, best_d = unit, d
        return best

    def _do_attack(self, target, fire, effects):
        if self.attack == "melee":
            target.take_hit(self.damage)
            effects.append(("hit", list(target.pos)))
        elif self.attack == "projectile":
            fire(self, target)

    # -------------------------------------------------------------- movement
    def _face(self, dx, dy):
        if dx or dy:
            self._angle = art.angle_between((0, 0), (dx, dy))

    def _move_to(self, dt, target_pos, stop=0.0):
        dx = target_pos[0] - self.pos[0]
        dy = target_pos[1] - self.pos[1]
        d = math.hypot(dx, dy)
        if d <= max(stop, 1e-6):
            return False
        step = min(self.speed * dt, d - stop if d > stop else 0.0)
        if step <= 0:
            return False
        self.pos[0] += dx / d * step
        self.pos[1] += dy / d * step
        self._face(dx, dy)
        return True

    def _follow_route(self, dt):
        if not self.waypoints:
            if self.base_pos is not None:
                self._move_to(dt, self.base_pos)
            return
        if self.wp_index >= len(self.waypoints):
            self._arrive()
            return
        wp = self.waypoints[self.wp_index]
        dx = wp[0] - self.pos[0]
        dy = wp[1] - self.pos[1]
        d = math.hypot(dx, dy)
        step = self.speed * dt
        if d <= step or d < 1e-6:
            self.pos[0], self.pos[1] = float(wp[0]), float(wp[1])
            self._face(dx, dy)
            self.wp_index += 1
            if self.wp_index >= len(self.waypoints):
                self._arrive()
        else:
            self.pos[0] += dx / d * step
            self.pos[1] += dy / d * step
            self._face(dx, dy)

    def _arrive(self):
        """An attacker that made it to the base leaks and is removed."""
        self.reached_base = True
        self.alive = False

    def _chase(self, dt, enemies):
        target = self._nearest(enemies)
        if target is not None:
            if self._dist(target.pos) > self.range * 0.8:
                self._move_to(dt, target.pos)
            return
        if self.home is not None:
            self._move_to(dt, self.home, stop=2.0)

    # -------------------------------------------------------------- update
    def update(self, dt, attackers, defenders, fire, effects):
        """Advance one tick. Returns True if the unit fired this frame."""
        if not self.alive:
            return False

        if self.side == "defender":
            enemies, allies = attackers, defenders
        else:
            enemies, allies = defenders, attackers

        fired = False
        move = self.type.movement

        if self.side == "defender":
            if move == "chase":
                self._chase(dt, enemies)
        else:
            if move == "route":
                self._follow_route(dt)
            elif move == "direct":
                if self.base_pos is not None:
                    self._move_to(dt, self.base_pos)
                    if self._dist(self.base_pos) <= max(self.radius, 6):
                        self._arrive()
            elif move == "hunt":
                quarry = self._nearest(allies)
                if quarry is not None and self._dist(quarry.pos) <= 260:
                    self._move_to(dt, quarry.pos)
                else:
                    self._follow_route(dt)

        if not self.alive:
            return False

        if self.attack != "none":
            target = self._pick_target(enemies)
            self._attack_timer -= dt
            if target is not None and self._attack_timer <= 0.0:
                self._do_attack(target, fire, effects)
                self._attack_timer = self.cooldown
                fired = True

        self._update_anim_state(dt, fired)
        return fired

    # -------------------------------------------------------------- animation
    def _frames_for(self, name):
        spec = self.type.sprite
        if isinstance(spec, dict) and spec.get("kind") == "sprites":
            anims = spec.get("animations") or {}
            if name in anims:
                return art.sprite_frames(spec, self.size, self.tint, name=name)
            if "idle" in anims:
                return art.sprite_frames(spec, self.size, self.tint, name="idle")
        return self._frames

    def _update_anim_state(self, dt, fired):
        moved = self._dist(self._last_pos) > FRAME_MOVE_EPS
        self._last_pos = (self.pos[0], self.pos[1])
        if not self.alive or self.hp <= 0:
            state = "death"
        elif fired:
            state = "attack"
        elif moved:
            state = "walk"
        else:
            state = "idle"
        if state != self.anim_state:
            self.anim_state = state
            self._state_time = 0.0
        else:
            self._state_time += dt

    def death_duration(self):
        spec = self.type.sprite
        if not (isinstance(spec, dict) and spec.get("kind") == "sprites"):
            return 0.0
        if "death" not in (spec.get("animations") or {}):
            return 0.0
        frames = art.frame_count(spec, "death")
        fps = art.fps(spec, name="death")
        if fps <= 0:
            return 0.0
        return frames / fps

    def tick_death(self, dt):
        self._state_time += dt

    def _current_frame(self, count):
        if count <= 1:
            return 0
        spec = self.type.sprite
        if isinstance(spec, dict) and spec.get("kind") in ("sprites", "anim", "sheet"):
            try:
                return art.frame_index(spec, self._state_time, name=self.anim_state) % count
            except Exception:
                return 0
        return 0

    # -------------------------------------------------------------- drawing
    def draw(self, canvas, show_hp=True, force=False):
        if not self.alive and not force:
            return
        frames = self._frames_for(self.anim_state)
        if not frames:
            return
        img = frames[self._current_frame(len(frames))]
        if self._angle:
            img = art.rot(img, self._angle)
        canvas.blit(img, img.get_rect(center=(int(self.pos[0]), int(self.pos[1]))))
        if show_hp and self.alive and self.max_hp > 0 and self.hp < self.max_hp:
            self._draw_hp(canvas)

    def _draw_hp(self, canvas):
        w = max(20, self.size)
        frac = max(0.0, min(1.0, self.hp / self.max_hp))
        x = int(self.pos[0] - w / 2)
        y = int(self.pos[1] - self.radius - 8)
        pygame.draw.rect(canvas, (30, 30, 34), (x, y, w, 5), border_radius=2)
        color = (120, 220, 120) if frac > 0.5 else (230, 200, 80) if frac > 0.25 else (230, 80, 80)
        pygame.draw.rect(canvas, color, (x, y, int(w * frac), 5), border_radius=2)

    def draw_range(self, canvas):
        r = int(self.range)
        if r <= 0:
            return
        surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (255, 255, 255, 40), (r, r), r)
        pygame.draw.circle(surf, (255, 255, 255, 120), (r, r), r, 2)
        canvas.blit(surf, (int(self.pos[0]) - r, int(self.pos[1]) - r))

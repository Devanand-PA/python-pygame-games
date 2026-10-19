"""The unified unit runtime.

A :class:`Unit` wraps a :class:`core.content.UnitType` and works for *both*
sides:

* **defenders** -- placed by the player.  ``movement="static"`` is a classic
  tower; ``movement="chase"`` is a melee/ranged unit that walks after the
  nearest enemy and returns home when the map is clear.
* **attackers** -- spawned by waves.  ``movement="route"`` follows the map path,
  ``"direct"`` flies straight at the base, ``"hunt"`` leaves the path to chase a
  defender.  Any unit with ``attack != "none"`` can damage defenders, so enemies
  now fight back against towers.

Everything (hp, speed, range, damage, rate, splash, targeting, flying, ...) is
read from the type, so a level designer can invent any unit without code.
"""
import math

import pygame

from core import settings as S
from engine import art


class Unit:
    def __init__(self, utype, pos, *, base_pos=None, waypoints=None,
                 wave_number=1, home=None, race_tint=None):
        self.type = utype
        self.side = utype.side
        self.pos = [float(pos[0]), float(pos[1])]
        self.base_pos = base_pos
        self.home = home                     # defenders: cell centre to return to
        self.tint = utype.tint or race_tint

        self.alive = True
        self.reached_base = False
        self.heading = 90.0
        self.radius = utype.radius
        self.is_flying = utype.is_flying

        # defenders get upgrade-driven scaling, attackers get wave scaling
        self.level = 1
        self.invested = utype.cost
        self.kills = 0
        self._wave_scale = 1.0 + 0.10 * max(0, wave_number - 1) if utype.is_attacker else 1.0

        self.cooldown_left = 0.0
        self.hunt_target = None

        if utype.is_flying or utype.movement in ("direct",):
            self.route = [tuple(pos), tuple(base_pos)] if base_pos else [tuple(pos)]
        elif waypoints:
            self.route = [tuple(w) for w in waypoints]
        else:
            self.route = [tuple(pos)] if not base_pos else [tuple(pos), tuple(base_pos)]
        self.route_index = 0

        self._size = max(8, int(S.TILE * self.type.sprite_scale))
        self._anim_cache = {}
        self._frames = art.sprite_frames(self.type.sprite, self._size, self.tint)
        self._sprite = self._frames[0]
        self._fps = art.fps(self.type.sprite)
        self._loop = art.loops(self.type.sprite)
        # desync identical units so a crowd doesn't animate in lockstep
        self._anim_offset = (self.pos[0] * 0.013 + self.pos[1] * 0.017) % 1.0
        # animation state machine (idle / walk / attack / death)
        self.anim_state = "idle"
        self._state_time = 0.0
        self._attack_flash = 0.0
        self._move_flash = 0.0
        self._last_pos = [self.pos[0], self.pos[1]]
        self.max_hp = self._base_max_hp()
        self.hp = self.max_hp

    # ------------------------------------------------------------- stats
    def _base_max_hp(self):
        hp = self.type.hp
        if self.type.is_defender:
            hp *= S.UNIT_HP_GAIN ** (self.level - 1)
        else:
            hp *= self._wave_scale
        return max(1, int(round(hp)))

    @property
    def damage(self):
        dmg = self.type.damage
        if self.type.is_defender:
            dmg *= S.UNIT_DAMAGE_GAIN ** (self.level - 1)
        return dmg

    @property
    def range(self):
        rng = self.type.range
        if self.type.is_defender:
            rng *= S.UNIT_RANGE_GAIN ** (self.level - 1)
        return rng

    @property
    def cooldown(self):
        cd = self.type.cooldown
        if self.type.is_defender:
            cd *= S.UNIT_RATE_GAIN ** (self.level - 1)
        return max(0.01, cd)

    @property
    def progress(self):
        return self.route_index

    def has_animation(self, name):
        return name in art.animation_names(self.type.sprite)

    def death_duration(self):
        """Seconds a death animation should linger (0 if there is none)."""
        if not self.has_animation("death"):
            return 0.0
        n = art.frame_count(self.type.sprite, "death")
        rate = art.fps(self.type.sprite, name="death")
        return min(1.2, max(0.25, n / max(0.1, rate)))

    def tick_death(self, dt):
        self._state_time += dt

    def _frames_for(self, name=None):
        key = name or ""
        if key not in self._anim_cache:
            self._anim_cache[key] = art.sprite_frames(
                self.type.sprite, self._size, self.tint, name=name)
        return self._anim_cache[key]

    def _current_frame(self):
        frames = self._frames_for(self.anim_state)
        if len(frames) > 1:
            i = int((self._state_time + self._anim_offset)
                    * art.fps(self.type.sprite, name=self.anim_state))
            n = len(frames)
            loop = art.loops(self.type.sprite, self.anim_state)
            idx = i % n if loop else min(n - 1, i)
            return frames[idx]
        return frames[0]

    # ------------------------------------------------------------- upgrades
    def upgrade_cost(self):
        if self.level >= S.UNIT_MAX_LEVEL:
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
        ratio = self.hp / max(1, self.max_hp)
        self.max_hp = self._base_max_hp()
        self.hp = min(self.max_hp, max(self.hp, int(self.max_hp * ratio)))
        self.hp = self.max_hp
        return True

    # ------------------------------------------------------------- combat
    def update(self, dt, attackers, defenders, spawn_projectile, effects=None):
        """Advance one step.  Returns True when the unit fired (for sound)."""
        if not self.alive:
            return False
        self.cooldown_left = max(0.0, self.cooldown_left - dt)
        fired = False
        if self.side == "defender":
            fired = self._update_defender(dt, attackers, spawn_projectile, effects)
        else:
            fired = self._update_attacker(dt, defenders, spawn_projectile, effects)
        self._update_anim_state(dt, fired)
        return fired

    def _update_anim_state(self, dt, fired):
        """Pick idle / walk / attack / death for the next frame."""
        self._state_time += dt
        self._attack_flash = max(0.0, self._attack_flash - dt)
        self._move_flash = max(0.0, self._move_flash - dt)
        moved = (abs(self.pos[0] - self._last_pos[0])
                 + abs(self.pos[1] - self._last_pos[1])) > 0.05
        self._last_pos = [self.pos[0], self.pos[1]]
        if moved:
            self._move_flash = 0.18
        if fired:
            self._attack_flash = 0.30
        if self.hp <= 0:
            state = "death"
        elif self._attack_flash > 0:
            state = "attack"
        elif self._move_flash > 0:
            state = "walk"
        else:
            state = "idle"
        if state != self.anim_state:
            self.anim_state = state
            self._state_time = 0.0

    def _update_defender(self, dt, attackers, spawn_projectile, effects):
        detect = self.type.aggro if self.type.movement == "chase" else self.range
        target = self._pick_target(attackers, detect)
        if self.type.movement == "chase":
            if target is not None:
                if self._dist(target.pos) > self.range * 0.85:
                    self._move_toward(target.pos, dt)
                else:
                    self.heading = art.angle_between(self.pos, target.pos)
            elif self.home is not None and self._dist(self.home) > 2.0:
                self._move_toward(self.home, dt)
        if target is not None:
            self.heading = art.angle_between(self.pos, target.pos)
            if self.cooldown_left <= 0 and self._dist(target.pos) <= self.range:
                return self._do_attack(target, spawn_projectile, effects)
        return False

    def _update_attacker(self, dt, defenders, spawn_projectile, effects):
        target = None
        if self.type.attack != "none":
            rng = self.type.aggro if self.type.movement in ("hunt", "chase") else self.range
            target = self._pick_target(defenders, rng)
        self.hunt_target = target

        moving = not (target is not None and self.type.stop_to_attack)
        if self.type.movement == "route":
            if moving:
                self._follow_route(dt)
        elif self.type.movement == "direct":
            if moving:
                self._fly_to(dt)
        elif self.type.movement == "hunt":
            if target is not None:
                if self._dist(target.pos) > self.range * 0.85:
                    self._move_toward(target.pos, dt)
                else:
                    self.heading = art.angle_between(self.pos, target.pos)
            else:
                self._follow_route(dt)

        fired = False
        if target is not None and self.type.attack != "none":
            self.heading = art.angle_between(self.pos, target.pos)
            if self.cooldown_left <= 0 and self._dist(target.pos) <= self.range:
                fired = self._do_attack(target, spawn_projectile, effects)

        # arrival / leak
        if self.type.movement in ("route", "hunt"):
            if (self.route_index >= len(self.route)
                    and (self.hunt_target is None or not self.hunt_target.alive)):
                self.reached_base = True
                self.alive = False
        elif self.type.movement == "direct":
            if self.base_pos is not None and self._dist(self.base_pos) <= 6.0:
                self.reached_base = True
                self.alive = False
        return fired

    def _do_attack(self, target, spawn_projectile, effects):
        self.cooldown_left = self.cooldown
        if self.type.attack == "projectile":
            spawn_projectile(self, target)
            return True
        if self.type.attack == "melee":
            died = target.take_hit(self.damage)
            if effects is not None:
                effects.append(("hit", list(target.pos)))
            if died:
                self.kills += 1
            return True
        return False

    def _pick_target(self, units, rng):
        mode = self.type.default_targeting
        can_air = self.type.targets in ("air", "both")
        can_ground = self.type.targets in ("ground", "both")
        rng2 = rng * rng
        best, best_score = None, None
        for unit in units:
            if not unit.alive or not unit.type.can_be_attacked:
                continue
            if unit.is_flying and not can_air:
                continue
            if not unit.is_flying and not can_ground:
                continue
            d2 = ((unit.pos[0] - self.pos[0]) ** 2
                  + (unit.pos[1] - self.pos[1]) ** 2)
            if d2 > rng2:
                continue
            if mode == "first":
                score = unit.progress
            elif mode == "strongest":
                score = unit.hp
            elif mode == "weakest":
                score = -unit.hp
            else:                      # nearest
                score = -d2
            if best_score is None or score > best_score:
                best_score, best = score, unit
        return best

    # ------------------------------------------------------------- movement
    def _dist(self, point):
        return math.hypot(point[0] - self.pos[0], point[1] - self.pos[1])

    def _move_toward(self, point, dt):
        dx, dy = point[0] - self.pos[0], point[1] - self.pos[1]
        dist = math.hypot(dx, dy)
        if dist < 0.5:
            return
        step = min(self.speed_step(dt), dist)
        self.pos[0] += dx / dist * step
        self.pos[1] += dy / dist * step
        self.heading = art.angle_between(self.pos, point)

    def speed_step(self, dt):
        return self.type.speed * dt

    def _advance_route(self, dt, target_point):
        dist = self._dist(target_point)
        remaining = self.speed_step(dt)
        if dist <= remaining:
            self.pos[0], self.pos[1] = target_point
            return True
        self.pos[0] += (target_point[0] - self.pos[0]) / dist * remaining
        self.pos[1] += (target_point[1] - self.pos[1]) / dist * remaining
        self.heading = art.angle_between(self.pos, target_point)
        return False

    def _follow_route(self, dt):
        remaining = self.speed_step(dt)
        while remaining > 0 and self.route_index < len(self.route):
            target = self.route[self.route_index]
            dx, dy = target[0] - self.pos[0], target[1] - self.pos[1]
            dist = math.hypot(dx, dy)
            if dist <= remaining:
                self.pos[0], self.pos[1] = target
                remaining -= dist
                self.route_index += 1
            else:
                self.pos[0] += dx / dist * remaining
                self.pos[1] += dy / dist * remaining
                remaining = 0
            if dist > 0.001:
                self.heading = art.angle_between(self.pos, target)

    def _fly_to(self, dt):
        if self.base_pos is None:
            self.route_index = len(self.route)
            return
        remaining = self.speed_step(dt)
        dx, dy = self.base_pos[0] - self.pos[0], self.base_pos[1] - self.pos[1]
        dist = math.hypot(dx, dy)
        if dist <= remaining:
            self.pos[0], self.pos[1] = self.base_pos
        else:
            self.pos[0] += dx / dist * remaining
            self.pos[1] += dy / dist * remaining
            self.heading = art.angle_between(self.pos, self.base_pos)

    # ------------------------------------------------------------------ draw
    def take_hit(self, dmg):
        if not self.alive:
            return False
        self.hp -= dmg
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
            return True
        return False

    def draw(self, canvas, show_hp=True, force=False, offset=(0, 0)):
        """Draw at ``pos - offset``: ``offset`` is the camera scroll, matching
        :meth:`engine.camera.Camera.world_to_screen`."""
        if not self.alive and not force:
            return
        img = art.rot(self._current_frame(), self.heading)
        canvas.blit(img, img.get_rect(center=(self.pos[0] - offset[0],
                                              self.pos[1] - offset[1])))
        if show_hp and self.hp < self.max_hp:
            self._draw_hp_bar(canvas, offset)

    def _draw_hp_bar(self, canvas, offset=(0, 0)):
        w = max(22, int(self.radius * 2))
        frac = max(0.0, self.hp / self.max_hp)
        x = int(self.pos[0] - offset[0] - w // 2)
        y = int(self.pos[1] - offset[1] - self.radius - 9)
        pygame.draw.rect(canvas, (40, 40, 40), (x, y, w, 5), border_radius=2)
        color = (120, 220, 120) if frac > 0.5 else (
            (240, 200, 60) if frac > 0.25 else (230, 80, 80))
        pygame.draw.rect(canvas, color, (x, y, int(w * frac), 5), border_radius=2)

    def draw_range(self, canvas, color=(255, 255, 255), offset=(0, 0)):
        rng = int(self.range)
        ring = pygame.Surface((rng * 2 + 4, rng * 2 + 4), pygame.SRCALPHA)
        center = (ring.get_width() // 2, ring.get_height() // 2)
        pygame.draw.circle(ring, tuple(color) + (36,), center, rng)
        pygame.draw.circle(ring, tuple(color) + (120,), center, rng, 2)
        canvas.blit(ring, (int(self.pos[0] - offset[0] - ring.get_width() // 2),
                           int(self.pos[1] - offset[1] - ring.get_height() // 2)))


def spawn_attacker(utype, level, spawn_pos, base_pos, wave_number, race_tint=None):
    """Convenience constructor used by the game scene."""
    return Unit(utype, spawn_pos, base_pos=base_pos,
                waypoints=level.waypoints, wave_number=wave_number,
                race_tint=race_tint)


def spawn_defender(utype, cell, center, race_tint=None):
    return Unit(utype, center, home=center, race_tint=race_tint)

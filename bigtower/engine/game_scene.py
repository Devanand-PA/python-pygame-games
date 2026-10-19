"""The playable tower-defense scene.

Loads a level from the content database, offers its available defender units in
the shop, spawns the level's own attacker waves, and drives the unified unit
engine.  Both sides can shoot each other: enemies with an ``attack`` hurt
towers, and mobile defenders (like the Scorpion) walk after the enemy.
"""
import pygame

from core import settings as S
from core.content import get_content
from core.scene import Scene
from engine import art
from engine import stats_panel
from engine.camera import Camera
from engine.level import Level
from engine.projectiles import Effects, Projectile
from engine.units import Unit


class GameScene(Scene):
    scene_type = "game"

    def __init__(self, game, level_id):
        super().__init__(game)
        self.content = get_content()
        self.level_id = level_id
        self.level_def = self.content.level(level_id)
        if self.level_def is None:
            raise ValueError(f"unknown level '{level_id}'")
        self.race = self.content.race(self.level_def.get("race")) or {}
        self.race_tint = self.race.get("tint")
        self.level = Level(self.level_def, self.content)

        self.gold = self.level_def["gold"]
        self.lives = self.level_def["lives"]
        self.wave_number = 0
        self.waves = self.level_def["waves"]
        self.state = "build"                 # build | wave | won | lost
        self.countdown = 0.0
        self.first_wave_pending = True

        self.attackers = []                  # enemy units
        self.defenders = []                  # player units
        self.towers_by_cell = {}             # home cell -> defender
        self.dying_units = []                # [unit, seconds_left] death anims
        self.projectiles = []
        self.effects = Effects()
        self.spawn_queue = []                # [(due_time, unit_id)]
        self.wave_time = 0.0
        self.session_kills = 0
        self.gold_earned = 0
        self.speed_mult = 1

        self.shop_units = self.content.level_defenders(self.level_def)
        self.selected_shop = None            # UnitType while placing
        self.selected_unit = None            # Unit while inspecting
        self.mouse_pos = (S.CANVAS_W // 2, S.CANVAS_H // 2)   # map space
        self.mouse_screen = (S.CANVAS_W // 2, S.CANVAS_H // 2)  # canvas space

        # --- camera ---------------------------------------------------------
        self.view_rect = pygame.Rect(0, 0, S.VIEW_W, S.VIEW_H)
        self.camera = Camera(self.view_rect, self.level.pixel_size)
        self._drag = None                    # map point grabbed, while panning
        self._drag_moved = False
        self._hover_shop = None              # UnitType under the cursor in the HUD

        self._make_hud()

    # ================================================================= HUD
    def _make_hud(self):
        self.hud_rect = pygame.Rect(0, S.CANVAS_H - S.HUD_H, S.CANVAS_W, S.HUD_H)
        n = max(1, len(self.shop_units))
        card_w = min(122, max(88, (S.CANVAS_W - 300) // n - 8))
        self.shop_buttons = []
        x = 12
        for utype in self.shop_units:
            rect = pygame.Rect(x, self.hud_rect.y + 8, card_w,
                               self.hud_rect.height - 16)
            self.shop_buttons.append((rect, utype))
            x += card_w + 8
        self.wave_btn = pygame.Rect(S.CANVAS_W - 150, self.hud_rect.y + 8, 138, 30)
        self.speed_btn = pygame.Rect(S.CANVAS_W - 150, self.hud_rect.y + 44, 66, 28)
        self.pause_btn = pygame.Rect(S.CANVAS_W - 78, self.hud_rect.y + 44, 66, 28)
        self.info_panel = pygame.Rect(S.CANVAS_W - 336, self.hud_rect.y - 140, 324, 134)
        # minimap lives in the top-right corner of the viewport
        self.minimap_rect = pygame.Rect(
            S.CANVAS_W - S.MINIMAP_W - S.MINIMAP_MARGIN, S.MINIMAP_MARGIN,
            S.MINIMAP_W, S.MINIMAP_H)

    # ================================================================= waves
    def start_wave(self, early=False):
        if self.state != "build" or self.wave_number >= len(self.waves):
            return
        if early and self.countdown > 0.0:
            bonus = int(self.countdown * S.EARLY_CALL_BONUS)
            self.gold += bonus
            self.gold_earned += bonus
        self.wave_number += 1
        self.state = "wave"
        self.wave_time = 0.0
        self.spawn_queue = []
        for uid, count, interval in self.waves[self.wave_number - 1]:
            for i in range(count):
                self.spawn_queue.append((i * interval, uid))
        self.spawn_queue.sort(key=lambda item: item[0])
        self.countdown = 0.0
        self.game.play("wave", 0.5)

    def _wave_cleared(self):
        bonus = 20 + self.wave_number * 5
        self.gold += bonus
        self.gold_earned += bonus
        if self.wave_number >= len(self.waves):
            self.state = "won"
            self.game.play("victory", 0.6)
            self.finishbattle(record_victory=True)
        else:
            self.state = "build"
            self.countdown = S.WAVE_COUNTDOWN

    def finishbattle(self, record_victory=False, record=False):
        from core import savestate
        user = self.game.user
        if not user:
            return
        try:
            if record_victory:
                savestate.record_level_completed(
                    user, self.level_id, self.session_kills,
                    self.race.get("levels") or [self.level_id])
            elif record and self.session_kills:
                savestate.update_stats(user, Kills=self.session_kills)
        except OSError:
            pass

    # ================================================================= update
    def on_update(self, delta_time):
        if self.state in ("won", "lost"):
            return
        for _ in range(max(1, self.speed_mult)):
            self._step(delta_time)

    def _step(self, dt):
        if self.state == "build" and not self.first_wave_pending:
            self.countdown -= dt
            if self.countdown <= 0.0:
                self.start_wave()
        if self.state == "wave":
            self.wave_time += dt
            while self.spawn_queue and self.spawn_queue[0][0] <= self.wave_time:
                _, uid = self.spawn_queue.pop(0)
                self._spawn(uid)

        for attacker in self.attackers:
            if attacker.update(dt, self.attackers, self.defenders,
                               self._fire, self.effects):
                self.game.play(attacker.type.sound, 0.18)
        for defender in self.defenders:
            if defender.update(dt, self.attackers, self.defenders,
                               self._fire, self.effects):
                self.game.play(defender.type.sound, 0.25)
        for proj in self.projectiles:
            targets = (self.defenders if proj.side == "defender"
                       else self.attackers)
            proj.update(dt, targets, self.effects)
        self.effects.update(dt)

        for entry in self.dying_units:
            entry[0].tick_death(dt)
            entry[1] -= dt
        self.dying_units = [e for e in self.dying_units if e[1] > 0.0]

        self._reap()
        self.projectiles = [p for p in self.projectiles if not p.dead]

        if self.state == "wave" and not self.spawn_queue and not self.attackers:
            self._wave_cleared()

    def _queue_death(self, unit):
        """Play a one-shot death animation before the unit disappears."""
        duration = unit.death_duration()
        if duration > 0.0:
            unit.anim_state = "death"
            unit._state_time = 0.0
            self.dying_units.append([unit, duration])

    def _reap(self):
        survivors = []
        for attacker in self.attackers:
            if attacker.alive:
                survivors.append(attacker)
                continue
            if attacker.reached_base:
                self.lives -= attacker.type.damage_to_base
                self.game.play("leak", 0.5)
                if self.lives <= 0:
                    self.lives = 0
                    self.state = "lost"
                    self.game.play("defeat", 0.6)
                    self.finishbattle(record=True)
            else:
                self.gold += attacker.type.bounty
                self.gold_earned += attacker.type.bounty
                self.session_kills += 1
                self.game.play("death", 0.3)
                self.effects.append(("boom", list(attacker.pos)))
                self._queue_death(attacker)
        self.attackers = survivors

        alive = []
        for defender in self.defenders:
            if defender.alive:
                alive.append(defender)
                continue
            if defender.home is not None:
                self.towers_by_cell.pop(defender.home, None)
            if self.selected_unit is defender:
                self.selected_unit = None
            self.effects.append(("boom", list(defender.pos)))
            self.game.play("death", 0.4)
            self._queue_death(defender)
        self.defenders = alive

    def _spawn(self, uid):
        utype = self.content.unit(uid)
        if utype is None:
            return
        spawn_pos = self.level.cell_center(self.level.spawn_cell)
        base_pos = self.level.cell_center(self.level.base_cell)
        self.attackers.append(Unit(
            utype, spawn_pos, base_pos=base_pos, waypoints=self.level.waypoints,
            wave_number=self.wave_number, race_tint=self.race_tint))

    def _fire(self, unit, target):
        self.projectiles.append(Projectile(unit, target))

    # ================================================================= events
    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self._on_mouse_move(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button in (1, 2):
                self._drag = self.camera.screen_to_world(event.pos)
                self._drag_moved = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.selected_shop or self.selected_unit:
                    self.selected_shop = None
                    self.selected_unit = None
                else:
                    from menus.pause_overlay import Scene as Pause
                    self.push_overlay(Pause(self.game, self))
            elif event.key == pygame.K_SPACE and self.state == "build":
                self.first_wave_pending = False
                self.start_wave(early=True)
            elif event.key in (pygame.K_b, pygame.K_v) and self.selected_unit is None:
                # snap the view to the base (B) or the spawn (V)
                target = (self.level.base_cell if event.key == pygame.K_b
                          else self.level.spawn_cell)
                self.camera.center_on(self.level.cell_center(target))
                self.camera.snap()
            elif pygame.K_1 <= event.key <= pygame.K_9:
                idx = event.key - pygame.K_1
                if idx < len(self.shop_units):
                    self._select_shop(self.shop_units[idx])
        elif event.type == pygame.MOUSEWHEEL:
            self.camera.pan_by(0, -event.y * 3 * S.TILE)
            self.camera.snap()
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button in (1, 2):
                dragged, self._drag = self._drag_moved, None
                self._drag_moved = False
                if event.button == 1 and not dragged:
                    self._click(event.pos)
                elif event.button == 2:
                    self.camera.snap()
            elif event.button == 3:
                self.selected_shop = None
                self.selected_unit = None

    def _on_mouse_move(self, screen_pos):
        self.mouse_screen = tuple(screen_pos)
        self.mouse_pos = self.camera.screen_to_world(screen_pos)
        self._hover_shop = None
        for rect, utype in self.shop_buttons:
            if rect.collidepoint(screen_pos):
                self._hover_shop = utype
                break
        if self._drag is None:
            return
        grab = self._drag
        world = self.camera.screen_to_world(screen_pos)
        if (abs(world[0] - grab[0]) >= S.CAMERA_DRAG_THRESHOLD
                or abs(world[1] - grab[1]) >= S.CAMERA_DRAG_THRESHOLD):
            self._drag_moved = True
        if self._drag_moved:
            self.camera.drag_to(world, grab)
            self.mouse_pos = self.camera.screen_to_world(screen_pos)

    # ------------------------------------------------- continuous camera keys
    def handle_keypress(self):
        """Called every frame by the game loop: held keys drive the camera."""
        if self.state in ("won", "lost"):
            return
        dt = self.game.delta_time
        if dt <= 0.0:
            return
        keys = pygame.key.get_pressed()
        dx = (1 if keys[pygame.K_d] or keys[pygame.K_RIGHT] else 0) - \
             (1 if keys[pygame.K_a] or keys[pygame.K_LEFT] else 0)
        dy = (1 if keys[pygame.K_s] or keys[pygame.K_DOWN] else 0) - \
             (1 if keys[pygame.K_w] or keys[pygame.K_UP] else 0)
        if dx or dy:
            norm = (dx * dx + dy * dy) ** 0.5
            self.camera.pan_screen(dx / norm, dy / norm, dt)
            return                       # held keys cancel edge scrolling
        if self._cursor_over_view():
            self._edge_scroll(dt)
        elif self._cursor_at_screen_bottom():
            self.camera.pan_by(0, S.CAMERA_EDGE_SPEED * dt)

    def _cursor_over_view(self):
        pos = self.mouse_screen
        return (self.view_rect.collidepoint(pos)
                and not self.minimap_rect.collidepoint(pos)
                and not (self.info_panel.collidepoint(pos)
                         and self.selected_unit is not None))

    def _cursor_at_screen_bottom(self):
        """True in the strip along the very bottom of the screen that is clear
        of the HUD controls.

        Panning *down* deliberately has no band above the shop bar: that band
        used to sit right on top of it, so reaching for a card to deploy scrolled
        the map instead of just selecting a unit.  Down-panning by mouse is now
        confined to the bottom edge of the window (see ``_edge_scroll``); WASD,
        dragging, the wheel and the minimap are unaffected.
        """
        pos = self.mouse_screen
        if pos[1] < S.CANVAS_H - S.CAMERA_EDGE:
            return False
        blocked = [rect for rect, _u in self.shop_buttons]
        blocked += [self.wave_btn, self.speed_btn, self.pause_btn]
        return not any(rect.inflate(4, 4).collidepoint(pos) for rect in blocked)

    def _edge_scroll(self, dt):
        """Scroll when the cursor rests against an edge of the viewport.

        Left/right/top only -- the bottom edge is handled by
        :meth:`_cursor_at_screen_bottom` so the shop bar is never a pan trigger.
        """
        pos = self.mouse_screen
        edge = S.CAMERA_EDGE
        dx = dy = 0.0
        if pos[0] < self.view_rect.x + edge:
            dx = -1.0
        elif pos[0] > self.view_rect.right - edge:
            dx = 1.0
        if pos[1] < self.view_rect.y + edge:
            dy = -1.0
        if dx or dy:
            self.camera.pan_by(dx * S.CAMERA_EDGE_SPEED * dt,
                               dy * S.CAMERA_EDGE_SPEED * dt)

    def _select_shop(self, utype):
        if self.gold < utype.cost:
            self.game.play("error", 0.5)
            return
        self.selected_shop = None if self.selected_shop is utype else utype
        self.selected_unit = None

    def _click(self, pos):
        if self.state in ("won", "lost"):
            self._end_screen_click(pos)
            return
        if self.wave_btn.collidepoint(pos) and self.state == "build":
            self.first_wave_pending = False
            self.start_wave(early=True)
            return
        if self.speed_btn.collidepoint(pos):
            self.speed_mult = 2 if self.speed_mult == 1 else 1
            return
        if self.pause_btn.collidepoint(pos):
            from menus.pause_overlay import Scene as Pause
            self.push_overlay(Pause(self.game, self))
            return
        for rect, utype in self.shop_buttons:
            if rect.collidepoint(pos):
                self._select_shop(utype)
                return
        if pos[1] >= self.hud_rect.y:
            return
        if self.info_panel.collidepoint(pos) and self.selected_unit is not None:
            self._panel_click(pos)
            return
        if self.minimap_rect.collidepoint(pos):
            world = self.camera.minimap_click(self.minimap_rect, pos)
            if world is not None:
                self.camera.center_on(world)
                self.camera.snap()
            return

        world = self.camera.screen_to_world(pos)
        unit = self._unit_at(world)
        if unit is not None:
            self.selected_unit = unit
            self.selected_shop = None
            return
        if self.selected_shop is not None:
            self._try_place(self.level.cell_of(world))
            return
        self.selected_unit = None

    def _unit_at(self, pos):
        cell = self.level.cell_of(pos)
        if cell in self.towers_by_cell and self.towers_by_cell[cell].alive:
            return self.towers_by_cell[cell]
        best, best_d = None, None
        for unit in self.defenders:
            if not unit.alive:
                continue
            d = ((unit.pos[0] - pos[0]) ** 2 + (unit.pos[1] - pos[1]) ** 2) ** 0.5
            if d <= max(24, unit.radius + 8) and (best_d is None or d < best_d):
                best, best_d = unit, d
        return best

    def _try_place(self, cell):
        utype = self.selected_shop
        if not self.level.is_buildable(*cell) or cell in self.towers_by_cell:
            self.game.play("error", 0.4)
            return
        if self.gold < utype.cost:
            self.game.play("error", 0.5)
            return
        center = self.level.cell_center(cell)
        unit = Unit(utype, center, home=center, race_tint=self.race_tint)
        self.defenders.append(unit)
        self.towers_by_cell[cell] = unit
        self.gold -= utype.cost
        self.game.play("place", 0.5)
        if self.gold < utype.cost:
            self.selected_shop = None

    def _panel_click(self, pos):
        unit = self.selected_unit
        if unit is None:
            return
        if self._panel_upgrade_rect().collidepoint(pos):
            cost = unit.upgrade_cost()
            if cost is None:
                return
            if self.gold >= cost:
                self.gold -= cost
                unit.upgrade()
                self.game.play("upgrade", 0.5)
            else:
                self.game.play("error", 0.5)
        elif self._panel_sell_rect().collidepoint(pos):
            self.gold += unit.sell_value()
            if unit.home is not None:
                self.towers_by_cell.pop(unit.home, None)
            if unit in self.defenders:
                self.defenders.remove(unit)
            self.selected_unit = None
            self.game.play("sell", 0.5)

    def _panel_upgrade_rect(self):
        return pygame.Rect(self.info_panel.x + 12, self.info_panel.bottom - 44,
                           146, 34)

    def _panel_sell_rect(self):
        return pygame.Rect(self.info_panel.right - 158,
                           self.info_panel.bottom - 44, 146, 34)

    def _end_screen_click(self, pos):
        box = self._end_box()
        btn_w, btn_h = 170, 44
        if self.state == "won":
            buttons = [("continue", self._go_career)]
        else:
            buttons = [("retry", self._retry), ("give_up", self._go_career)]
        y = box.bottom - btn_h - 18
        x = box.centerx - (len(buttons) * (btn_w + 14) - 14) // 2
        for _key, fn in buttons:
            r = pygame.Rect(x, y, btn_w, btn_h)
            if r.collidepoint(pos):
                self.game.play("click", 0.4)
                fn()
                return
            x += btn_w + 14

    def _retry(self):
        self.game.scene = GameScene(self.game, self.level_id)

    def _go_career(self):
        from menus.career_menu import Scene as Career
        self.game.scene = Career(self.game)

    # ================================================================= draw
    def on_draw(self):
        self.camera.update(self.game.delta_time)
        self._draw_world()
        self._draw_hud()
        if self.selected_unit is not None:
            self._draw_info_panel()
        self._draw_minimap()
        self._draw_shop_tooltip()
        if self.state in ("won", "lost"):
            self._draw_end_screen()

    def _draw_world(self):
        """Draw the map and everything on it, offset by the camera.

        The world is painted straight onto the canvas but only inside the
        viewport, so nothing can bleed into the HUD and nothing off-screen is
        blitted.
        """
        canvas = self.game.canvas
        view = self.view_rect
        offset = self.camera.offset

        pygame.draw.rect(canvas, (8, 8, 12), view)      # void beyond the map
        self.level.draw(canvas, offset, view)

        cam = self.camera
        if self.selected_unit is not None:
            self.selected_unit.draw_range(canvas, offset=offset)
        for defender in self.defenders:
            if cam.is_visible(defender.pos, S.TILE):
                defender.draw(canvas, offset=offset)
        for attacker in self.attackers:
            if cam.is_visible(attacker.pos, S.TILE):
                attacker.draw(canvas, offset=offset)
        for proj in self.projectiles:
            if cam.is_visible(proj.pos, 24):
                proj.draw(canvas, offset=offset)
        for unit, _left in self.dying_units:
            if cam.is_visible(unit.pos, S.TILE):
                unit.draw(canvas, show_hp=False, force=True, offset=offset)
        self.effects.draw(canvas, offset=offset)
        if self.selected_shop is not None:
            self._draw_ghost()

    # ---------------------------------------------------------------- minimap
    def _draw_minimap(self):
        """A scaled-down overview; click it to jump the camera."""
        if not self.camera.scrollable:
            return
        canvas = self.game.canvas
        box = self.minimap_rect
        mw, mh = self.level.pixel_size
        pygame.draw.rect(canvas, (14, 14, 22), box, border_radius=6)
        # scaled-down copy of the terrain, cached per (map size, colour depth)
        thumb = self._minimap_thumb()
        if thumb is not None:
            canvas.blit(thumb, (box.x + 1, box.y + 1),
                        pygame.Rect(0, 0, box.width - 2, box.height - 2))
        pygame.draw.rect(canvas, S.PANEL_EDGE, box, 2, border_radius=6)

        # spawn and base markers
        for cell, color in ((self.level.spawn_cell, (110, 230, 140)),
                            (self.level.base_cell, (120, 170, 255))):
            cx = box.x + 2 + (self.level.cell_center(cell)[0] / mw) * (box.width - 4)
            cy = box.y + 2 + (self.level.cell_center(cell)[1] / mh) * (box.height - 4)
            pygame.draw.circle(canvas, color, (int(cx), int(cy)), 3)

        # defenders as tiny dots, so the player can find their towers
        for defender in self.defenders:
            px, py = defender.pos
            canvas.fill((255, 220, 120),
                        (int(box.x + 2 + px / mw * (box.width - 4)),
                         int(box.y + 2 + py / mh * (box.height - 4)), 2, 2))

        view_box = self.camera.minimap_view_rect(
            pygame.Rect(box.x + 2, box.y + 2, box.width - 4, box.height - 4))
        pygame.draw.rect(canvas, (250, 250, 255), view_box, 2, border_radius=3)

        hint = self.game.fonts["small"].render(
            "drag/WASD \u00b7 B base \u00b7 V spawn",
            True, (196, 196, 216))
        hint_rect = hint.get_rect(midright=(box.right, box.bottom + 6))
        backing = hint_rect.inflate(8, 4)
        pygame.draw.rect(canvas, (10, 10, 16), backing, border_radius=4)
        canvas.blit(hint, hint_rect)

    def _minimap_thumb(self):
        size = (self.minimap_rect.width - 2, self.minimap_rect.height - 2)
        cached = getattr(self, "_thumb_cache", None)
        if cached is not None and cached[0] == size:
            return cached[1]
        thumb = pygame.transform.smoothscale(self.level.terrain, size)
        self._thumb_cache = (size, thumb)
        return thumb

    # --------------------------------------------------------- shop tooltip
    def _draw_shop_tooltip(self):
        """Show the full stat card for the shop unit under the cursor."""
        utype = self._hover_shop
        if utype is None or self.state in ("won", "lost"):
            return
        fonts = self.game.fonts
        width = 320
        height = stats_panel.panel_height(utype)
        rect = pygame.Rect(0, 0, width, height)
        rect.bottom = self.hud_rect.y - 8          # sit just above the HUD
        rect.left = min(max(S.MINIMAP_MARGIN, self.mouse_screen[0] - width // 2),
                        S.CANVAS_W - width - S.MINIMAP_MARGIN)
        rect.top = max(4, rect.bottom - height)
        stats_panel.draw_tooltip(
            self.game.canvas, rect, utype, fonts, race_tint=self.race_tint,
            affordable=self.gold >= utype.cost,
            hotkey=self._hotkey_for(utype))

    def _hotkey_for(self, utype):
        for idx, (_rect, candidate) in enumerate(self.shop_buttons):
            if candidate is utype and idx < 9:
                return idx + 1
        return None

    def _draw_ghost(self):
        utype = self.selected_shop
        if not self.view_rect.collidepoint(self.mouse_screen):
            return
        cell = self.level.cell_of(self.mouse_pos)
        center = self.level.cell_center(cell)
        valid = (self.level.is_buildable(*cell)
                 and cell not in self.towers_by_cell
                 and self.gold >= utype.cost)
        screen = self.camera.world_to_screen(center)
        view = self.view_rect
        ghost = pygame.Surface((view.width, view.height), pygame.SRCALPHA)
        local = (screen[0] - view.x, screen[1] - view.y)
        color = (120, 220, 120, 60) if valid else (230, 80, 80, 60)
        pygame.draw.circle(ghost, color, local, int(utype.range))
        pygame.draw.circle(ghost, (255, 255, 255, 110), local,
                           int(utype.range), 2)
        size = int(S.TILE * utype.sprite_scale)
        sprite = art.sprite(utype.sprite, size, self.race_tint)
        if not valid:
            sprite = art.sprite_alpha(sprite, 150)
        ghost.blit(sprite, sprite.get_rect(center=local))
        self.game.canvas.blit(ghost, (view.x, view.y))

    # ---------------------------------------------------------------- HUD
    def _draw_hud(self):
        canvas = self.game.canvas
        pygame.draw.rect(canvas, S.HUD_BG, self.hud_rect)
        pygame.draw.line(canvas, S.HUD_LINE, (0, self.hud_rect.y),
                         (self.hud_rect.width, self.hud_rect.y), 2)

        name_font = pygame.font.Font(None, 15)
        for idx, (rect, utype) in enumerate(self.shop_buttons):
            selected = self.selected_shop is utype
            color = (96, 120, 70) if selected else (58, 54, 84)
            pygame.draw.rect(canvas, color, rect, border_radius=6)
            pygame.draw.rect(canvas, S.HUD_LINE, rect, 1, border_radius=6)
            size = 40
            sprite = art.sprite(utype.sprite, size, self.race_tint)
            canvas.blit(sprite, sprite.get_rect(topleft=(rect.x + 5, rect.y + 6)))
            label = name_font.render(utype.name, True, S.TEXT_LIGHT)
            canvas.blit(label, (rect.x + 48, rect.y + 7))
            cost = name_font.render("${}".format(utype.cost), True,
                                    S.GOLD_COLOR if self.gold >= utype.cost
                                    else S.BAD_RED)
            canvas.blit(cost, (rect.x + 48, rect.y + 25))
            move = ("hunts" if utype.movement == "chase"
                    else ("moves" if utype.speed else "static"))
            tag = name_font.render(move, True, (150, 150, 170))
            canvas.blit(tag, (rect.x + 48, rect.y + 43))
            if idx < 9:
                hot = name_font.render(str(idx + 1), True, (150, 150, 170))
                canvas.blit(hot, (rect.right - 12, rect.y + 3))

        font = self.game.fonts["default"]
        x = self.shop_buttons[-1][0].right + 20
        canvas.blit(font.render("Gold: {}".format(self.gold), True,
                                S.GOLD_COLOR), (x, self.hud_rect.y + 8))
        canvas.blit(font.render("Lives: {}".format(self.lives), True,
                                S.LIFE_COLOR), (x, self.hud_rect.y + 38))
        canvas.blit(font.render("Wave {}/{}".format(max(1, self.wave_number),
                                                    len(self.waves)), True,
                                S.TEXT_LIGHT), (x + 180, self.hud_rect.y + 8))
        canvas.blit(self.game.fonts["small"].render(
            "Kills: {}".format(self.session_kills), True, (170, 170, 190)),
            (x + 180, self.hud_rect.y + 42))

        if self.state == "wave":
            txt, color = "Wave in progress", (60, 56, 80)
        elif self.state == "build":
            if self.first_wave_pending:
                txt, color = "Start Wave 1", (96, 120, 70)
            else:
                txt, color = ("Call wave (+{}g)".format(
                    int(self.countdown * S.EARLY_CALL_BONUS)), (96, 120, 70))
        else:
            txt, color = "-", (60, 56, 80)
        pygame.draw.rect(canvas, color, self.wave_btn, border_radius=6)
        label = self.game.fonts["small"].render(txt, True, S.TEXT_LIGHT)
        canvas.blit(label, label.get_rect(center=self.wave_btn.center))

        for rect, text in ((self.speed_btn, "x{}".format(self.speed_mult)),
                           (self.pause_btn, "II")):
            pygame.draw.rect(canvas, (58, 54, 84), rect, border_radius=6)
            pygame.draw.rect(canvas, S.HUD_LINE, rect, 1, border_radius=6)
            lab = self.game.fonts["small"].render(text, True, S.TEXT_LIGHT)
            canvas.blit(lab, lab.get_rect(center=rect.center))

    # ------------------------------------------------------------- info panel
    def _draw_info_panel(self):
        canvas = self.game.canvas
        unit = self.selected_unit
        panel = self.info_panel
        pygame.draw.rect(canvas, S.PANEL_BG, panel, border_radius=8)
        pygame.draw.rect(canvas, S.PANEL_EDGE, panel, 2, border_radius=8)
        title = "{}  Lv {}".format(unit.type.name, unit.level)
        canvas.blit(self.game.fonts["default"].render(title, True, S.TEXT_LIGHT),
                    (panel.x + 12, panel.y + 6))
        small = self.game.fonts["small"]
        canvas.blit(small.render(
            "hp {:.0f}/{:.0f}   dmg {:5.1f}   range {:4.0f}   rate {:4.1f}/s".format(
                unit.hp, unit.max_hp, unit.damage, unit.range,
                1.0 / max(0.01, unit.cooldown)), True, (200, 200, 215)),
            (panel.x + 12, panel.y + 32))
        mode = "{} / {}".format(unit.type.movement, unit.type.attack)
        canvas.blit(small.render("mode {}   targets {}".format(
            mode, unit.type.targets), True, (170, 170, 200)),
            (panel.x + 12, panel.y + 54))

        upg = self._panel_upgrade_rect()
        sell = self._panel_sell_rect()
        cost = unit.upgrade_cost()
        if cost is None:
            upg_text, enabled = "MAX", False
        else:
            upg_text, enabled = "Upgrade ${}".format(cost), self.gold >= cost
        pygame.draw.rect(canvas, (96, 120, 70) if enabled else (58, 54, 84),
                         upg, border_radius=6)
        canvas.blit(small.render(upg_text, True, S.TEXT_LIGHT),
                    small.render(upg_text, True, S.TEXT_LIGHT).get_rect(center=upg.center))
        pygame.draw.rect(canvas, (140, 70, 60), sell, border_radius=6)
        sell_text = "Sell +${}".format(unit.sell_value())
        canvas.blit(small.render(sell_text, True, S.TEXT_LIGHT),
                    small.render(sell_text, True, S.TEXT_LIGHT).get_rect(center=sell.center))

    # -------------------------------------------------------------- end screen
    def _end_box(self):
        box = pygame.Rect(0, 0, 540, 320)
        box.center = self.view_rect.center
        return box

    def _draw_end_screen(self):
        canvas = self.game.canvas
        veil = pygame.Surface((S.CANVAS_W, S.CANVAS_H), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 170))
        canvas.blit(veil, (0, 0))
        box = self._end_box()
        pygame.draw.rect(canvas, (18, 18, 26), box, border_radius=10)
        pygame.draw.rect(canvas, (90, 86, 120), box, 3, border_radius=10)
        if self.state == "won":
            title = self.game.fonts["title"].render("VICTORY!", True, (140, 230, 120))
        else:
            title = self.game.fonts["title"].render("DEFEAT", True, (240, 100, 100))
        canvas.blit(title, title.get_rect(midtop=(box.centerx, box.y + 24)))
        lines = [
            "{} - {}".format(self.race.get("name", ""),
                             self.level_def.get("name", "")),
            "Waves survived: {}/{}".format(
                self.wave_number if self.state == "won"
                else max(0, self.wave_number - 1), len(self.waves)),
            "Kills: {}".format(self.session_kills),
            "Gold earned: {}".format(self.gold_earned),
        ]
        y = box.y + 100
        for line in lines:
            text = self.game.fonts["default"].render(line, True, S.TEXT_LIGHT)
            canvas.blit(text, text.get_rect(midtop=(box.centerx, y)))
            y += 32
        btn_w, btn_h = 170, 44
        if self.state == "won":
            buttons = [("Continue", self._go_career)]
        else:
            buttons = [("Retry", self._retry), ("Give up", self._go_career)]
        y = box.bottom - btn_h - 18
        x = box.centerx - (len(buttons) * (btn_w + 14) - 14) // 2
        for label_text, _fn in buttons:
            r = pygame.Rect(x, y, btn_w, btn_h)
            pygame.draw.rect(canvas, (96, 120, 70), r, border_radius=6)
            lab = self.game.fonts["default"].render(label_text, True, S.TEXT_LIGHT)
            canvas.blit(lab, lab.get_rect(center=r.center))
            x += btn_w + 14

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
        self.mouse_pos = (S.CANVAS_W // 2, S.CANVAS_H // 2)

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
            self.mouse_pos = event.pos
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
            elif pygame.K_1 <= event.key <= pygame.K_9:
                idx = event.key - pygame.K_1
                if idx < len(self.shop_units):
                    self._select_shop(self.shop_units[idx])
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self._click(event.pos)
            elif event.button == 3:
                self.selected_shop = None
                self.selected_unit = None

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

        unit = self._unit_at(pos)
        if unit is not None:
            self.selected_unit = unit
            self.selected_shop = None
            return
        if self.selected_shop is not None:
            self._try_place(self.level.cell_of(pos))
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
        self.level.draw(self.game.canvas)
        if self.selected_unit is not None:
            self.selected_unit.draw_range(self.game.canvas)
        for defender in self.defenders:
            defender.draw(self.game.canvas)
        for attacker in self.attackers:
            attacker.draw(self.game.canvas)
        for proj in self.projectiles:
            proj.draw(self.game.canvas)
        for unit, _left in self.dying_units:
            unit.draw(self.game.canvas, show_hp=False, force=True)
        self.effects.draw(self.game.canvas)
        if self.selected_shop is not None:
            self._draw_ghost()
        self._draw_hud()
        if self.selected_unit is not None:
            self._draw_info_panel()
        if self.state in ("won", "lost"):
            self._draw_end_screen()

    def _draw_ghost(self):
        utype = self.selected_shop
        cell = self.level.cell_of(self.mouse_pos)
        center = self.level.cell_center(cell)
        valid = (self.level.is_buildable(*cell)
                 and cell not in self.towers_by_cell
                 and self.gold >= utype.cost)
        ghost = pygame.Surface((S.CANVAS_W, S.CANVAS_H), pygame.SRCALPHA)
        color = (120, 220, 120, 60) if valid else (230, 80, 80, 60)
        pygame.draw.circle(ghost, color, center, int(utype.range))
        pygame.draw.circle(ghost, (255, 255, 255, 110), center,
                           int(utype.range), 2)
        size = int(S.TILE * utype.sprite_scale)
        sprite = art.sprite(utype.sprite, size, self.race_tint)
        if not valid:
            sprite = art.sprite_alpha(sprite, 150)
        ghost.blit(sprite, sprite.get_rect(center=center))
        self.game.canvas.blit(ghost, (0, 0))

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
        box.center = (S.CANVAS_W // 2, (self.level.rows_n * S.TILE) // 2)
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

"""The playable tower-defense scene: map, waves, towers, HUD, end screens."""
import pygame

from core import settings as S
from core.scene import Scene
from engine import art
from engine.enemies import ENEMY_TYPES, Enemy
from engine.level import Level
from engine.projectiles import Effects, Projectile
from engine.towers import TOWER_TYPES, Tower


class GameScene(Scene):
    scene_type = "game"

    def __init__(self, game, level_index: int):
        super().__init__(game)
        self.level_index = level_index
        from engine.levels import LEVELS
        self.level_def = LEVELS[level_index]
        self.level = Level(self.level_def["map"])

        self.gold = self.level_def["gold"]
        self.lives = self.level_def["lives"]
        self.wave_number = 0                 # waves completed / current index
        self.waves = self.level_def["waves"]
        self.state = "build"                 # build | wave | won | lost
        self.countdown = 0.0                 # >0 while auto-start counts down
        self.first_wave_pending = True

        self.enemies = []
        self.towers = {}                     # cell -> Tower
        self.projectiles = []
        self.effects = Effects()
        self.spawn_queue = []                # [(due_time, enemy_key)]
        self.wave_time = 0.0
        self.session_kills = 0
        self.gold_earned = 0
        self.speed_mult = 1

        self.selected_shop = None            # TowerType while placing
        self.selected_tower = None           # Tower while inspecting
        self.mouse_pos = (S.CANVAS_W // 2, S.CANVAS_H // 2)

        self._make_hud()

    # ================================================================= HUD
    def _make_hud(self):
        self.hud_rect = pygame.Rect(0, S.MAP_ROWS * S.TILE, S.CANVAS_W, S.HUD_H)
        self.shop_buttons = []
        x = 12
        for ttower in TOWER_TYPES:
            rect = pygame.Rect(x, self.hud_rect.y + 8, 118, self.hud_rect.height - 16)
            self.shop_buttons.append((rect, ttower))
            x += 124
        self.wave_btn = pygame.Rect(S.CANVAS_W - 150, self.hud_rect.y + 8, 138, 30)
        self.speed_btn = pygame.Rect(S.CANVAS_W - 150, self.hud_rect.y + 44, 66, 28)
        self.pause_btn = pygame.Rect(S.CANVAS_W - 78, self.hud_rect.y + 44, 66, 28)
        self.info_panel = pygame.Rect(S.CANVAS_W - 330, self.hud_rect.y - 128, 318, 122)

    # ================================================================= waves
    def start_wave(self, early=False):
        if self.state != "build":
            return
        if early and self.countdown > 0.0:
            bonus = int(self.countdown * S.EARLY_CALL_BONUS)
            self.gold += bonus
            self.gold_earned += bonus
        self.wave_number += 1
        self.state = "wave"
        self.wave_time = 0.0
        self.spawn_queue = []
        for key, count, interval in self.waves[self.wave_number - 1]:
            for i in range(count):
                self.spawn_queue.append((i * interval, key))
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
        """Persist stats (best-effort; safe when storage is read-only)."""
        from core import savestate
        from engine.levels import LEVELS
        user = self.game.user
        if not user:
            return
        try:
            if record_victory:
                savestate.record_level_completed(
                    user, self.level_def["number"], self.session_kills,
                    len(LEVELS))
            elif record and self.session_kills:
                savestate.update_stats(user, Kills=self.session_kills)
        except OSError:
            pass

    # ================================================================= update
    def on_update(self, delta_time):
        if self.state in ("won", "lost"):
            return
        steps = self.speed_mult
        for _ in range(steps):
            self._step(delta_time)

    def _step(self, dt):
        # wave scheduling
        if self.state == "build" and not self.first_wave_pending:
            self.countdown -= dt
            if self.countdown <= 0.0:
                self.first_wave_pending = False
                self.start_wave()
        if self.state == "wave":
            self.wave_time += dt
            while self.spawn_queue and self.spawn_queue[0][0] <= self.wave_time:
                _, key = self.spawn_queue.pop(0)
                self._spawn(key)

        # units
        for enemy in self.enemies:
            enemy.update(dt)
        for tower in self.towers.values():
            fired = tower.update(dt, self.enemies, self._fire)
            if fired:
                self.game.play(tower.type.sound, 0.25)
        for proj in self.projectiles:
            proj.update(dt, self.enemies, self.effects)
        self.effects.update(dt)

        # deaths / leaks
        survivors = []
        for enemy in self.enemies:
            if enemy.alive:
                survivors.append(enemy)
                continue
            if enemy.reached_base:
                self.lives -= enemy.type.damage
                self.game.play("leak", 0.5)
                if self.lives <= 0:
                    self.lives = 0
                    self.state = "lost"
                    self.game.play("defeat", 0.6)
                    self.finishbattle(record=True)
            else:
                # killed
                self.gold += enemy.type.bounty
                self.gold_earned += enemy.type.bounty
                self.session_kills += 1
                self.game.play("death", 0.35)
                self.effects.append(("boom", list(enemy.pos)))
        self.enemies = survivors
        self.projectiles = [p for p in self.projectiles if not p.dead]

        if (self.state == "wave" and not self.spawn_queue
                and not self.enemies):
            self._wave_cleared()

    def _spawn(self, key):
        etype = ENEMY_TYPES[key]
        spawn_pos = self.level.cell_center(self.level.spawn_cell)
        base_pos = self.level.cell_center(self.level.base_cell)
        self.enemies.append(Enemy(etype, self.wave_number, spawn_pos,
                                  base_pos, self.level.waypoints))

    def _fire(self, tower, target):
        self.projectiles.append(Projectile(tower, target))

    # ================================================================= events
    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.mouse_pos = event.pos
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.selected_shop or self.selected_tower:
                    self.selected_shop = None
                    self.selected_tower = None
                else:
                    from menus.pause_overlay import Scene as Pause
                    self.push_overlay(Pause(self.game, self))
            elif event.key == pygame.K_SPACE and self.state == "build":
                self.start_wave(early=True)
            elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                idx = event.key - pygame.K_1
                if idx < len(TOWER_TYPES):
                    self._select_shop(TOWER_TYPES[idx])
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self._click(event.pos)
            elif event.button == 3:
                self.selected_shop = None
                self.selected_tower = None

    def _select_shop(self, ttower):
        if self.gold < ttower.cost:
            self.game.play("error", 0.5)
            return
        self.selected_shop = None if self.selected_shop is ttower else ttower
        self.selected_tower = None

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
        for btn in self.shop_buttons:
            if btn[0].collidepoint(pos):
                self._select_shop(btn[1])
                return
        if pos[1] >= self.hud_rect.y:
            return
        if self.info_panel.collidepoint(pos):
            self._panel_click(pos)
            return

        cell = self.level.cell_of(pos)
        # clicking a tower selects it
        if cell in self.towers:
            self.selected_tower = self.towers[cell]
            self.selected_shop = None
            return
        if self.selected_shop is not None:
            self._try_place(cell)
            return
        self.selected_tower = None

    def _try_place(self, cell):
        ttower = self.selected_shop
        if not self.level.is_buildable(*cell) or cell in self.towers:
            self.game.play("error", 0.4)
            return
        if self.gold < ttower.cost:
            self.game.play("error", 0.5)
            return
        tower = Tower(ttower, cell, self.level.cell_center(cell))
        self.towers[cell] = tower
        self.gold -= ttower.cost
        self.game.play("place", 0.5)
        # keep placing more of the same if shift is held; else keep for chains
        if self.gold < ttower.cost:
            self.selected_shop = None

    def _panel_click(self, pos):
        tower = self.selected_tower
        if tower is None:
            return
        upg = self._panel_upgrade_rect()
        sell = self._panel_sell_rect()
        if upg.collidepoint(pos):
            cost = tower.upgrade_cost()
            if cost is None:
                return
            if self.gold >= cost:
                self.gold -= cost
                tower.upgrade()
                self.game.play("upgrade", 0.5)
            else:
                self.game.play("error", 0.5)
        elif sell.collidepoint(pos):
            self.gold += tower.sell_value()
            del self.towers[tower.cell]
            self.selected_tower = None
            self.game.play("sell", 0.5)

    def _panel_upgrade_rect(self):
        return pygame.Rect(self.info_panel.x + 12, self.info_panel.bottom - 44,
                           140, 34)

    def _panel_sell_rect(self):
        return pygame.Rect(self.info_panel.right - 152,
                           self.info_panel.bottom - 44, 140, 34)

    def _end_screen_click(self, pos):
        game = self.game
        box = self._end_box()
        btn_w, btn_h = 170, 44
        if self.state == "won":
            buttons = [("continue", self._go_career)]
        else:
            buttons = [("retry", self._retry), ("give_up", self._go_career)]
        y = box.bottom - btn_h - 18
        x = box.centerx - (len(buttons) * (btn_w + 14) - 14) // 2
        for key, fn in buttons:
            r = pygame.Rect(x, y, btn_w, btn_h)
            if r.collidepoint(pos):
                game.play("click", 0.4)
                fn()
                return
            x += btn_w + 14

    def _retry(self):
        from engine.game_scene import GameScene
        self.game.scene = GameScene(self.game, self.level_index)

    def _go_career(self):
        from menus.career_menu import Scene as Career
        self.game.scene = Career(self.game)

    # ================================================================= draw
    def on_draw(self):
        self.level.draw(self.game.canvas)
        # ground layer: range rings under towers
        if self.selected_tower:
            self.selected_tower.draw_range(self.game.canvas)
        for tower in self.towers.values():
            tower.draw(self.game.canvas)
        for enemy in self.enemies:
            enemy.draw(self.game.canvas)
        for proj in self.projectiles:
            proj.draw(self.game.canvas)
        self.effects.draw(self.game.canvas)
        if self.selected_shop is not None:
            self._draw_ghost()
        self._draw_hud()
        if self.selected_tower:
            self._draw_info_panel()
        if self.state in ("won", "lost"):
            self._draw_end_screen()

    def _draw_ghost(self):
        ttower = self.selected_shop
        cell = self.level.cell_of(self.mouse_pos)
        center = self.level.cell_center(cell)
        valid = (self.level.is_buildable(*cell) and cell not in self.towers
                 and self.gold >= ttower.cost)
        ghost = pygame.Surface((S.CANVAS_W, S.CANVAS_H), pygame.SRCALPHA)
        color = (120, 220, 120, 60) if valid else (230, 80, 80, 60)
        pygame.draw.circle(ghost, color, center, int(ttower.range))
        pygame.draw.circle(ghost, (255, 255, 255, 110), center,
                           int(ttower.range), 2)
        size = int(S.TILE * ttower.sprite_scale)
        if ttower.custom_art:
            sprite = art.custom(ttower.custom_art, size)
        else:
            sprite = art.scaled(art.tile(ttower.sprite), (size, size))
        if not valid:
            sprite = sprite.copy()
            sprite.fill((255, 70, 70, 130), special_flags=pygame.BLEND_RGBA_MULT)
        ghost.blit(sprite, sprite.get_rect(center=center))
        self.game.canvas.blit(ghost, (0, 0))

    # ---------------------------------------------------------------- HUD
    def _draw_hud(self):
        canvas = self.game.canvas
        pygame.draw.rect(canvas, S.HUD_BG, self.hud_rect)
        pygame.draw.line(canvas, S.HUD_LINE, (0, self.hud_rect.y),
                         (self.hud_rect.width, self.hud_rect.y), 2)

        # shop cards
        for btn, ttower in self.shop_buttons:
            selected = self.selected_shop is ttower
            color = (58, 54, 84) if not selected else (96, 120, 70)
            pygame.draw.rect(canvas, color, btn, border_radius=6)
            pygame.draw.rect(canvas, S.HUD_LINE, btn, 1, border_radius=6)
            size = 40
            if ttower.custom_art:
                sprite = art.custom(ttower.custom_art, size)
            else:
                sprite = art.scaled(art.tile(ttower.sprite), (size, size))
            canvas.blit(sprite, sprite.get_rect(
                topleft=(btn.x + 6, btn.y + 6)))
            name = game_font(canvas, 15)
            label = name.render(ttower.name, True, S.TEXT_LIGHT)
            canvas.blit(label, (btn.x + 50, btn.y + 8))
            cost = name.render("${}".format(ttower.cost), True,
                               S.GOLD_COLOR if self.gold >= ttower.cost
                               else S.BAD_RED)
            canvas.blit(cost, (btn.x + 50, btn.y + 30))
            hotkey = name.render(str(TOWER_TYPES.index(ttower) + 1), True,
                                 (150, 150, 170))
            canvas.blit(hotkey, (btn.right - 14, btn.y + 4))

        # economy
        font_small = self.game.fonts["default"]
        x = self.shop_buttons[-1][0].right + 30
        gold_text = font_small.render("Gold: {}".format(self.gold), True,
                                      S.GOLD_COLOR)
        canvas.blit(gold_text, (x, self.hud_rect.y + 10))
        lives_text = font_small.render("Lives: {}".format(self.lives), True,
                                       S.LIFE_COLOR)
        canvas.blit(lives_text, (x, self.hud_rect.y + 40))
        wave_text = font_small.render(
            "Wave {}/{}".format(max(1, self.wave_number), len(self.waves)),
            True, S.TEXT_LIGHT)
        canvas.blit(wave_text, (x + 170, self.hud_rect.y + 10))
        kills_text = self.game.fonts["small"].render(
            "Kills: {}".format(self.session_kills), True, (170, 170, 190))
        canvas.blit(kills_text, (x + 170, self.hud_rect.y + 42))

        # wave button
        if self.state == "wave":
            txt = "Wave in progress"
            pygame.draw.rect(canvas, (60, 56, 80), self.wave_btn,
                             border_radius=6)
        elif self.state == "build":
            if self.first_wave_pending:
                txt = "Start Wave 1"
            else:
                txt = "Call wave (+{}g)".format(
                    int(self.countdown * S.EARLY_CALL_BONUS))
            pygame.draw.rect(canvas, (96, 120, 70), self.wave_btn,
                             border_radius=6)
        else:
            txt = "-"
            pygame.draw.rect(canvas, (60, 56, 80), self.wave_btn,
                             border_radius=6)
        label = self.game.fonts["small"].render(txt, True, S.TEXT_LIGHT)
        canvas.blit(label, label.get_rect(center=self.wave_btn.center))
        if self.state == "build" and not self.first_wave_pending:
            cd = self.game.fonts["small"].render(
                "auto in {:4.1f}s".format(max(0.0, self.countdown)), True,
                (170, 170, 190))
            canvas.blit(cd, (self.wave_btn.x, self.hud_rect.bottom - 20))

        for rect, label_text in ((self.speed_btn,
                                  "x{}".format(self.speed_mult)),
                                 (self.pause_btn, "II")):
            pygame.draw.rect(canvas, (58, 54, 84), rect, border_radius=6)
            pygame.draw.rect(canvas, S.HUD_LINE, rect, 1, border_radius=6)
            lab = self.game.fonts["small"].render(label_text, True,
                                                  S.TEXT_LIGHT)
            canvas.blit(lab, lab.get_rect(center=rect.center))

    # ------------------------------------------------------------- info panel
    def _draw_info_panel(self):
        canvas = self.game.canvas
        tower = self.selected_tower
        panel = self.info_panel
        pygame.draw.rect(canvas, S.PANEL_BG, panel, border_radius=8)
        pygame.draw.rect(canvas, S.PANEL_EDGE, panel, 2, border_radius=8)
        title = "{}  Lv {}".format(tower.type.name, tower.level)
        head = self.game.fonts["default"].render(title, True, S.TEXT_LIGHT)
        canvas.blit(head, (panel.x + 12, panel.y + 8))
        stats = self.game.fonts["small"].render(
            "dmg {:5.1f}   range {:4.0f}   rate {:4.1f}/s".format(
                tower.damage, tower.range, 1.0 / max(0.01, tower.cooldown)),
            True, (200, 200, 215))
        canvas.blit(stats, (panel.x + 12, panel.y + 36))

        upg = self._panel_upgrade_rect()
        sell = self._panel_sell_rect()
        cost = tower.upgrade_cost()
        if cost is None:
            upg_text = "MAX"
            enabled = False
        else:
            upg_text = "Upgrade ${}".format(cost)
            enabled = self.gold >= cost
        up_color = (96, 120, 70) if enabled else (58, 54, 84)
        pygame.draw.rect(canvas, up_color, upg, border_radius=6)
        lab = self.game.fonts["small"].render(upg_text, True, S.TEXT_LIGHT)
        canvas.blit(lab, lab.get_rect(center=upg.center))
        pygame.draw.rect(canvas, (140, 70, 60), sell, border_radius=6)
        lab = self.game.fonts["small"].render(
            "Sell +${}".format(tower.sell_value()), True, S.TEXT_LIGHT)
        canvas.blit(lab, lab.get_rect(center=sell.center))

    # -------------------------------------------------------------- end screen
    def _end_box(self):
        box = pygame.Rect(0, 0, 520, 300)
        box.center = (S.CANVAS_W // 2, (S.MAP_ROWS * S.TILE) // 2)
        return box

    def _draw_end_screen(self):
        canvas = self.game.canvas
        veil = pygame.Surface((S.CANVAS_W, S.MAP_ROWS * S.TILE), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 170))
        canvas.blit(veil, (0, 0))
        box = self._end_box()
        pygame.draw.rect(canvas, (18, 18, 26), box, border_radius=10)
        pygame.draw.rect(canvas, (90, 86, 120), box, 3, border_radius=10)
        if self.state == "won":
            title = self.game.fonts["title"].render("VICTORY!", True,
                                                    (140, 230, 120))
        else:
            title = self.game.fonts["title"].render("DEFEAT", True,
                                                    (240, 100, 100))
        canvas.blit(title, title.get_rect(midtop=(box.centerx, box.y + 24)))
        lines = [
            "Waves survived: {}/{}".format(
                self.wave_number if self.state == "won" else max(0, self.wave_number - 1),
                len(self.waves)),
            "Kills: {}".format(self.session_kills),
            "Gold earned: {}".format(self.gold_earned),
        ]
        y = box.y + 110
        for line in lines:
            text = self.game.fonts["default"].render(line, True, S.TEXT_LIGHT)
            canvas.blit(text, text.get_rect(midtop=(box.centerx, y)))
            y += 34
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
            lab = self.game.fonts["default"].render(label_text, True,
                                                    S.TEXT_LIGHT)
            canvas.blit(lab, lab.get_rect(center=r.center))
            x += btn_w + 14


_font_cache = {}


def game_font(canvas, size):
    key = ("font", size)
    if key not in _font_cache:
        _font_cache[key] = pygame.font.Font(None, size)
    return _font_cache[key]

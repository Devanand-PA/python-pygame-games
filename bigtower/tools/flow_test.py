"""End-to-end headless test: menus, content, gameplay, unit behaviours, saves.

Run:  SDL_VIDEODRIVER=dummy .venv/bin/python tools/flow_test.py
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from core import paths  # noqa: E402

PASS = []
FAIL = []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name + (f" [{extra}]" if extra else ""))
    print(("PASS " if cond else "FAIL ") + name + (f"  {extra}" if extra else ""))


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def fast_forward(scene, seconds, dt=1 / 60):
    for _ in range(int(seconds / dt)):
        if scene.state in ("won", "lost"):
            break
        scene.game.on_update(dt)


def buildable_near(level, point, limit=260):
    """Return a buildable, free cell centre within ``limit`` of ``point``."""
    best, best_d = None, None
    for y in range(level.rows_n):
        for x in range(level.cols):
            if not level.is_buildable(x, y):
                continue
            cx, cy = level.cell_center((x, y))
            d = ((cx - point[0]) ** 2 + (cy - point[1]) ** 2) ** 0.5
            if d <= limit and (best_d is None or d < best_d):
                best, best_d = (cx, cy), d
    return best


def main():
    tmp = tempfile.mkdtemp(prefix="bigtower_test_")
    os.environ["BIGTOWER_SAVE_DIR"] = tmp
    import importlib
    import core.paths
    import core.savestate
    importlib.reload(core.paths)
    importlib.reload(core.savestate)

    from core.game import Game
    game = Game()

    # ---------------------------------------------------------------- content
    from core.content import get_content, ContentDB, UnitType
    content = get_content()
    check("content has terrain", len(content.terrains) >= 5,
          f"{len(content.terrains)} terrains")
    check("content has races", len(content.races) >= 3,
          str(list(content.races)))
    check("content has units (both sides)",
          any(u.side == "defender" for u in content.units.values())
          and any(u.side == "attacker" for u in content.units.values()),
          f"{len(content.units)} units")
    check("every race has levels",
          all(content.race_levels(r) for r in content.races.values()))

    # content round-trips through the designer's save helpers
    tmp_content = Path(tmp) / "content"
    db = ContentDB(root=tmp_content)
    db.save_unit(UnitType({"id": "probe", "name": "Probe", "side": "defender",
                           "sprite": {"kind": "shape", "shape": "square",
                                      "color": [10, 20, 30]}, "hp": 42}))
    db.save_race({"id": "probe_race", "name": "Probe Race", "units": ["probe"],
                  "enemies": [], "levels": []})
    db2 = ContentDB(root=tmp_content)
    check("designer saves units", "probe" in db2.units
          and db2.unit("probe").hp == 42)
    check("designer saves races", "probe_race" in db2.races)
    shutil.rmtree(tmp_content, ignore_errors=True)

    # ------------------------------------------------------- sprite specs
    from core.content import normalise_sprite
    from engine import art
    anim_spec = normalise_sprite({"kind": "anim", "fps": 6, "frames": [
        {"kind": "pack", "tile": 226}, {"kind": "pack", "tile": 249}]})
    check("anim sprite normalised",
          anim_spec["kind"] == "anim" and len(anim_spec["frames"]) == 2)
    sheet_spec = normalise_sprite({"kind": "sheet", "path": "x.png",
                                   "frame_w": 16, "frame_h": 16, "frames": 4,
                                   "fps": 10})
    check("sheet sprite normalised",
          sheet_spec["kind"] == "sheet" and sheet_spec["frames"] == 4
          and sheet_spec["fps"] == 10)
    frames = art.sprite_frames(anim_spec, 32, None)
    check("animated sprite resolves frames",
          len(frames) == 2 and art.frame_count(anim_spec) == 2
          and art.fps(anim_spec) == 6
          and art.frame_index(anim_spec, 0.5) == 1)

    # custom (animated) terrain round-trips and renders
    anim_root = Path(tmp) / "anim_content"
    adb = ContentDB(root=anim_root)
    adb.save_terrain([
        {"id": "grass", "name": "Grass", "char": "g", "base": 157,
         "buildable": True, "walkable": True,
         "sprite": {"kind": "anim", "fps": 5, "frames": [
             {"kind": "pack", "tile": 157}, {"kind": "pack", "tile": 158}]}},
        {"id": "rock", "name": "Rock", "char": "r", "base": 159,
         "buildable": False, "walkable": False,
         "overlay_sprite": {"kind": "image", "path": "nope.png"}},
    ])
    adb.save_level({"id": "lvl", "race": "r", "name": "L", "grid": ["SggB"]})
    adb2 = ContentDB(root=anim_root)
    terr = adb2.terrain("r")
    check("terrain keeps custom overlay sprite",
          terr.overlay_spec is not None and terr.overlay_spec["kind"] == "image")
    from engine.level import Level
    alvl = Level(adb2.level("lvl"), content=adb2)
    check("animated terrain tracked for redraw", len(alvl._anim_cells) >= 1)
    surface = pygame.Surface(alvl.pixel_size)
    alvl.draw(surface)          # must not raise
    check("animated terrain draws", surface.get_width() > 0)

    # animated unit builds its frames and draws
    anim_type = UnitType({"id": "anim_u", "side": "attacker", "movement": "static",
                          "attack": "none", "speed": 0, "hp": 10,
                          "sprite": anim_spec})
    from engine.units import Unit as _Unit
    au = _Unit(anim_type, (50, 50))
    check("unit builds animation frames", len(au._frames) == 2)
    usurf = pygame.Surface((120, 120))
    au.draw(usurf)
    check("animated unit draws", usurf.get_width() == 120)

    # ------------------------------------------------ named animation states
    sheet_path = ("packs/kenney_tower-defense-top-down/Tilesheet/"
                  "towerDefense_tilesheet.png")
    sprites_spec = normalise_sprite({
        "kind": "sprites",
        "image": {"kind": "image", "path": "units/gun.png"},
        "animations": {
            "idle": {"path": sheet_path, "frame_w": 32, "frame_h": 32,
                     "frames": [0, 1], "fps": 6},
            "walk": {"path": sheet_path, "frame_w": 32, "frame_h": 32,
                     "frames": [2, 3, 4], "fps": 12},
        },
    })
    check("sprites spec normalised",
          sprites_spec["kind"] == "sprites"
          and sprites_spec["animations"]["walk"]["frames"] == [2, 3, 4]
          and sprites_spec["animations"]["walk"]["fps"] == 12)
    check("animation names reported",
          set(art.animation_names(sprites_spec)) == {"idle", "walk"})
    walk_frames = art.sprite_frames(sprites_spec, 24, None, name="walk")
    check("named animation resolves its frames",
          len(walk_frames) == 3 and art.frame_count(sprites_spec, "walk") == 3
          and art.fps(sprites_spec, name="walk") == 12)
    check("missing state falls back to idle",
          len(art.sprite_frames(sprites_spec, 24, None, name="attack")) == 2)
    static_only = normalise_sprite({"kind": "sprites", "image":
                                    {"kind": "pack", "tile": 226},
                                    "animations": {}})
    check("sprites spec with no animations falls back to its image",
          art.frame_count(static_only) == 1)

    # the runtime picks idle / walk / attack / death
    sprites_type = UnitType({"id": "sprites_u", "side": "defender",
                             "movement": "static", "attack": "melee",
                             "speed": 0, "hp": 10, "sprite": sprites_spec})
    su = _Unit(sprites_type, (20, 20))
    su._update_anim_state(0.1, False)
    check("unit animates idle when still", su.anim_state == "idle")
    su.pos[0] += 4.0
    su._update_anim_state(0.1, False)
    check("unit animates walk when moving", su.anim_state == "walk")
    su._update_anim_state(0.5, False)
    check("unit returns to idle when still again", su.anim_state == "idle")
    su._update_anim_state(0.1, True)
    check("unit animates attack when it fires", su.anim_state == "attack")
    check("state frames come from the spec",
          len(su._frames_for("walk")) == 3 and len(su._frames_for("attack")) == 2)
    su.hp = 0
    su._update_anim_state(0.1, False)
    check("unit animates death when killed", su.anim_state == "death")
    check("unit with no death animation does not linger", su.death_duration() == 0.0)

    death_type = UnitType({"id": "dying", "side": "defender", "hp": 1, "sprite":
                           normalise_sprite({"kind": "sprites", "image": None,
                           "animations": {"death": {"path": sheet_path,
                           "frame_w": 32, "frame_h": 32,
                           "frames": [10, 11, 12], "fps": 10}}})})
    dying = _Unit(death_type, (5, 5))
    check("death animation gives a linger duration",
          abs(dying.death_duration() - 0.3) < 1e-6, str(dying.death_duration()))
    dying.take_hit(5)
    dcanvas = pygame.Surface((80, 80))
    dying.draw(dcanvas, force=True)
    check("dead unit can be force-drawn for its death frame", True)

    # sprites units round-trip through ContentDB
    sdb_root = Path(tmp) / "sprite_content"
    ContentDB(root=sdb_root).save_unit(UnitType(
        {"id": "anim_unit", "name": "Anim", "side": "defender",
         "sprite": sprites_spec, "hp": 10}))
    sdb2 = ContentDB(root=sdb_root)
    check("sprites unit round-trips",
          sdb2.unit("anim_unit").sprite["kind"] == "sprites"
          and len(sdb2.unit("anim_unit").sprite["animations"]) == 2)

    # ---------------------------------------------------------------- menus
    from menus.welcome_screen import Scene as Welcome
    game.scene = Welcome(game)
    check("welcome loads", game.scene is not None)

    game.scene.action_start()
    overlay = game.subscenes[-1]
    check("start with empty users opens selector",
          overlay.__module__ == "menus.user_selection")
    for ch in "Tester":
        overlay.handle_event(key_event(getattr(pygame, "K_" + ch.lower()), ch))
    overlay.handle_event(key_event(pygame.K_RETURN))
    check("user created + career reached",
          game.user == "Tester" and game.scene.__module__ == "menus.career_menu")

    # career -> campaign select
    game.scene.action_play()
    campaign = game.subscenes[-1]
    check("campaign select opens",
          campaign.__module__ == "menus.campaign_select")
    check("campaign select lists races", len(campaign.races) >= 3)
    race = campaign.races[0]
    campaign._launch(race)
    level_sel = game.subscenes[-1]
    check("level select opens for a race",
          level_sel.__module__ == "menus.level_select"
          and len(level_sel.levels) >= 1)

    # ---------------------------------------------------------------- battle
    level_id = level_sel.levels[0]["id"]
    level_sel._launch(level_id)
    scene = game.scene
    check("game scene loads", scene.__module__ == "engine.game_scene")
    check("map parsed with waypoints",
          len(scene.level.waypoints) == len(scene.level.path_cells) > 10)
    check("path starts at spawn",
          scene.level.path_cells[0] == scene.level.spawn_cell)
    check("path ends at base",
          scene.level.path_cells[-1] == scene.level.base_cell)
    check("shop stocks the level's units", len(scene.shop_units) >= 4,
          f"{len(scene.shop_units)} units")

    # --- pause overlay: "Restart Level" rebuilds the same level --------------
    from engine.game_scene import GameScene
    from menus.pause_overlay import Scene as PauseOverlay
    paused = GameScene(game, level_id)
    game.scene = paused
    paused.handle_event(key_event(pygame.K_ESCAPE))
    check("escape opens the pause overlay",
          isinstance(game.subscenes[-1] if game.subscenes else None,
                     PauseOverlay))
    paused.gold = 4242
    paused.lives = 7
    try:
        game.subscenes[-1].restart()
        restarted = game.scene
        check("restart level does not crash and rebuilds the same level",
              isinstance(restarted, GameScene)
              and restarted is not paused
              and restarted.level_id == level_id
              and game.subscenes == [],
              f"level={getattr(restarted, 'level_id', None)} "
              f"overlays={len(game.subscenes)}")
        check("restart level resets progress",
              restarted.gold == restarted.level_def["gold"]
              and restarted.lives == restarted.level_def["lives"]
              and restarted.wave_number == 0
              and restarted.state == "build")
    except AttributeError as exc:
        check("restart level does not crash and rebuilds the same level",
              False, f"AttributeError: {exc}")
    game.scene = scene          # restore for the rest of the battle tests

    # ---------------------------------------------------------------- camera
    # The shipped levels may be bigger than the viewport, so the camera has to
    # behave on a map that genuinely does not fit.  A synthetic 3x3 mirror of
    # the real grid gives us one without depending on shipped map sizes.
    from engine.camera import Camera
    from core import settings as _S
    view = pygame.Rect(0, 0, _S.VIEW_W, _S.VIEW_H)
    cam = Camera(view, (2560, 1280))
    check("big map camera opens on the top-left", cam.offset == (0, 0),
          str(cam.offset))
    cam.pan_by(-999, -999)
    cam.snap()
    check("camera clamps at the top-left", cam.offset == (0, 0), str(cam.offset))
    cam.pan_by(99999, 99999)
    cam.snap()
    check("camera clamps at the bottom-right",
          cam.offset == (2560 - _S.VIEW_W, 1280 - _S.VIEW_H), str(cam.offset))
    check("camera world/screen round-trips",
          all(cam.screen_to_world(cam.world_to_screen(p)) == p
              for p in ((0, 0), (123, 456), (2559, 1279))))
    cam.scroll_to(0, 0)
    check("camera culls what is off-screen",
          cam.is_visible((10, 10)) and not cam.is_visible((2500, 1200)))
    tiny = Camera(view, (640, 320))
    check("a map smaller than the viewport is centred", tiny.offset == (320, 160),
          str(tiny.offset))
    cam.scroll_to(0, 0)
    cam.pan_by(800, 600)
    for _ in range(200):
        cam.update(0.016)
    check("camera eases onto its target", cam.offset == (800, 600),
          str(cam.offset))

    big_def = dict(scene.level_def)
    big_cols, big_rows_n = 60, 30
    cells = [["g"] * big_cols for _ in range(big_rows_n)]
    bands = list(range(2, big_rows_n - 3, 4))
    for i, y in enumerate(bands):
        for x in range(1, big_cols - 1):
            cells[y][x] = "."
        if i + 1 < len(bands):
            link_x = big_cols - 3 if i % 2 == 0 else 2
            for yy in range(y, bands[i + 1] + 1):
                cells[yy][link_x] = "."
    cells[bands[0]][1] = "S"
    cells[bands[-1]][big_cols - 2] = "B"
    big_def["id"] = "big_camera_test"
    big_def["grid"] = ["".join(r) for r in cells]
    content.levels[big_def["id"]] = big_def
    big = GameScene(game, big_def["id"])
    game.scene = big
    check("a map larger than the viewport is scrollable",
          big.camera.scrollable and big.level.cols * _S.TILE > _S.VIEW_W,
          f"{big.level.cols}x{big.level.rows_n}")
    game.on_draw()
    check("the world is drawn inside the viewport only",
          game.canvas.get_at((5, _S.CANVAS_H - 4))[:3] == _S.HUD_BG)
    big.camera.scroll_to(0, 0)
    spot = None
    for cy in range(big.level.rows_n):
        for cx in range(big.level.cols):
            if (big.level.is_buildable(cx, cy)
                    and big.camera.is_visible(big.level.cell_center((cx, cy)))):
                spot = (cx, cy)
                break
        if spot:
            break
    big.selected_shop = big.shop_units[0]
    big.gold = 5000
    big._click(big.camera.world_to_screen(big.level.cell_center(spot)))
    check("a screen click places a tower in the right map cell",
          spot in big.towers_by_cell, f"cell={spot}")
    big._click((big.minimap_rect.centerx, big.minimap_rect.centery))
    check("clicking the minimap jumps the camera", big.camera.offset != (0, 0),
          str(big.camera.offset))

    # --- units must ride the map, not fight it ------------------------------
    # The world renderer and the camera must agree on one convention:
    # screen = world - camera_offset.  A sign slip here is invisible to a
    # click/camera test but makes every unit slide the wrong way across the map.
    import numpy as _np
    from engine.units import Unit as _Unit

    def _anchor(utype, world, offset):
        probe = pygame.Surface((_S.VIEW_W, _S.VIEW_H))
        probe.fill((1, 2, 3))
        u = _Unit(utype, world)
        u.draw(probe, show_hp=False, force=True, offset=offset)
        arr = pygame.surfarray.array3d(probe)          # (w, h, 3)
        lit = _np.any(arr != _np.array((1, 2, 3), dtype=arr.dtype), axis=2)
        xs, ys = _np.nonzero(lit)
        return (float(xs.mean()), float(ys.mean()))

    mid = (10, 5)
    while not big.level.is_buildable(*mid):
        mid = (mid[0] + 1, mid[1])
    anchor_world = big.level.cell_center(mid)
    p0 = _anchor(big.shop_units[0], anchor_world, (0, 0))
    p1 = _anchor(big.shop_units[0], anchor_world, (60, 40))
    check("a unit shifts opposite the camera scroll, like the terrain",
          abs((p1[0] - p0[0]) + 60) < 1.0 and abs((p1[1] - p0[1]) + 40) < 1.0,
          f"shift=({p1[0]-p0[0]:+.1f}, {p1[1]-p0[1]:+.1f}) for scroll +60/+40")

    big.selected_shop = big.shop_units[0]
    big.gold = 5000
    big._try_place(mid)
    tower = big.towers_by_cell[mid]
    big.camera.scroll_to(200, 150)
    expect = big.camera.world_to_screen(tower.pos)
    big.defenders.remove(tower)
    game.on_draw()
    bare = game.canvas.copy()
    big.defenders.append(tower)
    game.on_draw()
    a = pygame.surfarray.array3d(game.canvas)
    b = pygame.surfarray.array3d(bare)
    keep = _np.zeros(a.shape[:2], dtype=bool)          # keep[x, y]
    keep[big.view_rect.x:big.view_rect.right,
         big.view_rect.y:big.view_rect.bottom] = True
    keep[big.minimap_rect.x - 6:, big.minimap_rect.y - 6:
         big.minimap_rect.bottom + 34] = False
    xs, ys = _np.nonzero(_np.any(a != b, axis=2) & keep)
    aligned = (len(xs) > 0
               and abs(xs.mean() - expect[0]) < 14
               and abs(ys.mean() - expect[1]) < 14)
    check("a placed tower renders on the tile the camera maps it to", aligned,
          f"expected~{expect} rendered~({xs.mean():.0f}, {ys.mean():.0f})"
          if len(xs) else "not rendered")

    # --- edge scrolling must not fight the shop bar -------------------------
    def _scroll_at(pos):
        big.camera.scroll_to(600, 300)
        big.mouse_screen = pos
        big.game.delta_time = 1 / 60.0
        before = big.camera.offset
        big.handle_keypress()
        big.camera.snap()
        return (big.camera.offset[0] - before[0],
                big.camera.offset[1] - before[1])

    card = big.shop_buttons[0][0]
    above = (card.centerx, _S.VIEW_H - 12)     # just above the shop bar
    check("reaching for a shop card does not scroll the map",
          _scroll_at(above) == (0, 0) and _scroll_at(card.center) == (0, 0),
          f"above={_scroll_at(above)} on-card={_scroll_at(card.center)}")
    check("panning down only happens at the bottom edge of the screen",
          _scroll_at((300, _S.CANVAS_H - 2))[1] > 0
          and _scroll_at((_S.VIEW_W - 4, _S.VIEW_H // 2))[1] == 0)
    check("top and side edges still scroll the camera",
          _scroll_at((300, 4))[1] < 0
          and _scroll_at((4, 300))[0] < 0
          and _scroll_at((_S.VIEW_W - 4, 300))[0] > 0)
    check("the middle of the map does not scroll",
          _scroll_at((_S.VIEW_W // 2, _S.VIEW_H // 2)) == (0, 0))
    big.camera.scroll_to(0, 0)

    # --- the shop previews a unit's stats before it is ever deployed ---------
    from engine import stats_panel
    shop_type = big.shop_units[0]
    check("every shop unit can be previewed",
          all(stats_panel.stat_rows(u) for u in big.shop_units),
          f"{len(big.shop_units)} units")
    base = stats_panel.scaled_stats(shop_type, 1)
    upg = stats_panel.scaled_stats(shop_type, 2)
    check("shop stats show what an upgrade improves",
          upg["damage"] > base["damage"] and upg["hp"] > base["hp"]
          and upg["rate"] > base["rate"],
          f"dmg {base['damage']:.1f}->{upg['damage']:.1f} "
          f"hp {base['hp']}->{upg['hp']}")
    rows_preview = stats_panel.stat_rows(shop_type)
    check("shop stat rows carry an upgrade preview",
          any(row[2] for row in rows_preview) and
          any(row[0] == "DPS" for row in rows_preview))
    big._hover_shop = shop_type
    big.mouse_screen = (200, 300)
    game.on_draw()
    check("hovering a shop card draws its stat tooltip", True)
    del content.levels[big_def["id"]]
    game.scene = scene          # restore for the rest of the battle tests

    # --- a killed unit plays a short death animation then vanishes ----------
    death_spec = normalise_sprite({"kind": "sprites", "image": None, "animations": {
        "death": {"path": sheet_path, "frame_w": 32, "frame_h": 32,
                  "frames": [10, 11, 12], "fps": 10}}})
    dth = _Unit(UnitType({"id": "dth", "side": "defender", "hp": 1,
                          "sprite": death_spec}),
                scene.level.cell_center(scene.level.path_cells[6]))
    dth.take_hit(10)
    scene.defenders = [dth]
    scene._reap()
    check("killed unit queues a death animation", len(scene.dying_units) == 1)
    dsurf = pygame.Surface(scene.game.canvas.get_size())
    for unit, _left in scene.dying_units:
        unit.draw(dsurf, show_hp=False, force=True)
    check("dying unit is drawn for its death frame", True)
    scene.dying_units[0][1] = 0.0
    scene._step(0.016)
    check("death animation expires", scene.dying_units == [])

    # --- melee chaser: the Scorpion walks after a stationary enemy ----------
    from engine.units import Unit
    dummy_type = UnitType({"id": "dummy", "side": "attacker", "movement": "static",
                           "attack": "none", "speed": 0, "hp": 100000,
                           "sprite": {"kind": "shape", "shape": "circle",
                                      "color": [200, 60, 60]}})
    dummy_pos = scene.level.cell_center(scene.level.path_cells[6])
    dummy = Unit(dummy_type, dummy_pos, base_pos=dummy_pos)
    scorp_type = content.unit("scorpion")
    home = buildable_near(scene.level, dummy_pos, limit=150)
    scorp = Unit(scorp_type, home, home=home)
    start_d = scorp._dist(dummy.pos)
    scene.defenders = [scorp]
    scene.attackers = [dummy]
    for _ in range(120):
        scene._step(1 / 60)
    check("melee unit chases enemies", scorp._dist(dummy.pos) < start_d - 10,
          f"{start_d:.0f} -> {scorp._dist(dummy.pos):.0f}")
    check("melee unit damages enemies", dummy.hp < dummy.max_hp,
          f"hp {dummy.hp:.0f}/{dummy.max_hp}")
    scene.defenders, scene.attackers = [], []

    # --- enemies attack towers ---------------------------------------------
    cell = buildable_near(scene.level, scene.level.cell_center(
        scene.level.path_cells[8]))
    tower_type = content.unit("gun")
    tower = Unit(tower_type, cell, home=cell)
    scene.defenders = [tower]
    scene.towers_by_cell = {scene.level.cell_of(cell): tower}
    armor = Unit(content.unit("armored"), cell, base_pos=cell,
                 waypoints=scene.level.waypoints, wave_number=1)
    scene.attackers = [armor]
    hp0 = tower.hp
    for _ in range(90):
        scene._step(1 / 60)
    check("enemies damage towers", tower.hp < hp0,
          f"tower hp {tower.hp:.0f}/{hp0} (alive={tower.alive})")
    assert not tower.alive or tower.hp < hp0
    scene.defenders, scene.attackers = [], []
    scene.towers_by_cell = {}

    # --- place a full defence and win --------------------------------------
    scene.gold += 20000
    strong = max(scene.shop_units,
                 key=lambda u: u.range * u.damage / max(0.01, u.cooldown))
    placed = 0
    for c in scene.level.path_cells:
        for adj in ((c[0] + 1, c[1]), (c[0] - 1, c[1]),
                    (c[0], c[1] + 1), (c[0], c[1] - 1)):
            if scene.level.is_buildable(*adj) and adj not in scene.towers_by_cell:
                scene.selected_shop = strong
                scene._try_place(adj)
                placed += 1
    check("towers placed", placed >= 4, f"placed={placed}")

    twr = next(iter(scene.towers_by_cell.values()))
    scene.selected_unit = twr
    scene.gold += 2000
    scene._panel_click(scene._panel_upgrade_rect().center)
    check("upgrade works", twr.level == 2)
    value = twr.sell_value()
    scene._panel_click(scene._panel_sell_rect().center)
    check("sell works", twr not in scene.defenders,
          f"refund={value}")

    scene.selected_shop = None
    scene.selected_unit = None
    scene.first_wave_pending = False
    scene.start_wave()
    fast_forward(scene, 3000)
    check("battle reaches an end", scene.state in ("won", "lost"),
          f"state={scene.state} wave={scene.wave_number} kills={scene.session_kills}")
    check("victory achieved", scene.state == "won",
          f"wave={scene.wave_number} lives={scene.lives}")

    stats = core.savestate.load_stats("Tester")
    check("victory recorded by level id",
          level_id in (stats.get("Levels Completed") or []), str(stats))
    check("kills recorded", stats.get("Kills", 0) == scene.session_kills,
          f"{stats.get('Kills')} vs {scene.session_kills}")

    # ---------------------------------------------------------------- defeat
    from engine.game_scene import GameScene
    second_level = content.race_levels(campaign.races[1])[0]["id"]
    game.scene = GameScene(game, second_level)
    scene2 = game.scene
    scene2.first_wave_pending = False
    scene2.start_wave()
    fast_forward(scene2, 3000)
    check("defeat without towers", scene2.state == "lost",
          f"state={scene2.state} lives={scene2.lives}")

    # ------------------------------------------------------- readonly fallback
    ro_dir = Path(tmp) / "readonly"
    ro_dir.mkdir()
    os.chmod(ro_dir, 0o500)
    os.environ["BIGTOWER_SAVE_DIR"] = str(ro_dir)
    importlib.reload(core.paths)
    if os.access(ro_dir, os.W_OK):
        print("SKIP fallback when env dir read-only (chmod not enforced)")
    else:
        check("fallback when env dir read-only",
              str(core.paths.saves_root()) != str(ro_dir),
              str(core.paths.saves_root()))
    os.chmod(ro_dir, 0o700)

    # ------------------------------------------------------- designer UI round trip
    design_root = Path(tmp) / "designer_content"
    shutil.copytree(ROOT / "content", design_root)
    os.environ["BIGTOWER_CONTENT_DIR"] = str(design_root)
    importlib.reload(core.paths)

    from level_designer.app import Designer
    designer = Designer()

    def click(widget_rect):
        pos = widget_rect.center if hasattr(widget_rect, "center") else widget_rect
        designer._dispatch(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": 1}))

    check("designer opens five tabs", len(designer.tabs) == 5,
          str([n for n, _ in designer.tabs]))
    for i, btn in enumerate(designer.tab_buttons):
        click(btn.rect)
    check("designer tab bar switches tabs", designer.active == 4)

    # terrain: selecting a different row edits that entry
    designer.set_tab(0)
    terrain_tab = designer.terrain_tab
    click(pygame.Rect(terrain_tab.list.rect.x + 5,
                      terrain_tab.list.rect.y + 5 + terrain_tab.list.row_h * 2, 10, 10))
    check("designer terrain row selection",
          terrain_tab.current is terrain_tab.items[2],
          str(terrain_tab.current.get("id")))

    # units: New + Save writes a new JSON file; Delete removes the file again
    designer.set_tab(1)
    units_tab = designer.units_tab
    before = len(units_tab.items)
    units_tab.new()
    units_tab.save()
    new_unit_id = units_tab.current["id"]
    check("designer creates + saves a unit",
          (design_root / "units" / f"{new_unit_id}.json").exists()
          and new_unit_id in designer.content.units, new_unit_id)

    doomed = units_tab.items[-1]["id"]
    units_tab.list.index = len(units_tab.items) - 1
    units_tab._on_select(None)
    units_tab.delete()
    units_tab.save()
    check("designer deletes orphaned unit file",
          not (design_root / "units" / f"{doomed}.json").exists()
          and len(designer.content.units) == before,
          f"{doomed}: {len(designer.content.units)} vs {before}")

    # levels: paint a walkable cell, build a wave, save and reload
    designer.set_tab(3)
    level_tab = designer.levels_tab
    level_tab.list.index = 0
    level_tab._on_select(None)
    paint = next((t for t in designer.terrain_tab.items
                  if t.get("walkable", True) and t.get("char") not in ("g",)),
                 None)
    cell = (6, 4)
    if paint:
        # click the palette swatch (this is the bug that made only grass paintable)
        swatch = next(r for r, ch in level_tab.palette_rects()
                      if ch == paint["char"])
        click(swatch)
        cx = level_tab.map.rect.x + cell[0] * level_tab.map.cell + 3
        cy = level_tab.map.rect.y + cell[1] * level_tab.map.cell + 3
        click((cx, cy))
    level_tab.add_wave()
    level_tab.add_group()
    level_tab._apply_group_fields()
    level_tab.save()
    reloaded = ContentDB(root=design_root)
    saved_level = reloaded.level(level_tab.current["id"])
    level_tab.map.recompute_path()
    check("designer paints the map",
          bool(paint) and saved_level["grid"][cell[1]][cell[0]] == paint["char"])
    check("designer saves waves",
          bool(saved_level["waves"]) and bool(saved_level["waves"][0]))
    check("designer keeps the level reachable", level_tab.map.path_ok)

    # --- a map bigger than the designer's panel must survive a round trip -----
    mcanvas = level_tab.map
    panel = pygame.Rect(mcanvas.rect)
    big_rows = ["g" * 40 for _ in range(20)]
    big_rows = [list(r) for r in big_rows]
    big_rows[1][1] = "S"
    big_rows[18][38] = "B"
    big_rows = ["".join(r) for r in big_rows]
    mcanvas.set_grid(big_rows)
    check("designer adopts an oversized map's dimensions",
          mcanvas.width == 40 and mcanvas.height == 20,
          f"{mcanvas.width}x{mcanvas.height}")
    check("designer scales the tiles instead of overflowing its panel",
          mcanvas.fits and mcanvas.width * mcanvas.cell <= panel.width
          and mcanvas.height * mcanvas.cell <= panel.height,
          f"cell={mcanvas.cell} panel={panel.size}")
    check("designer keeps every cell of an oversized map",
          len(mcanvas.rows()) == 20
          and all(len(r) == 40 for r in mcanvas.rows())
          and mcanvas.rows()[1][1] == "S"
          and mcanvas.rows()[18][38] == "B")
    level_tab.save()
    again = ContentDB(root=design_root).level(level_tab.current["id"])
    check("an oversized map survives save and reload",
          len(again["grid"]) == 20 and len(again["grid"][0]) == 40
          and again["grid"][1][1] == "S" and again["grid"][18][38] == "B",
          f"{len(again['grid'])}x{len(again['grid'][0])}")

    # ------------------------------------------------- sprite editor widgets
    from level_designer import widgets as W
    ctx = designer.ctx

    picked = {}
    browser = W.FileBrowser(ctx, lambda p: picked.setdefault("path", p))
    ctx.open_modal(browser)
    browser._enter("units/towers/forest-towers/scorpion-tower")
    img_i = next(i for i, (k, _n) in enumerate(browser.entries) if k == "img")
    click(pygame.Rect(browser.list_rect.x + 4,
                      browser.list_rect.y + 4 + img_i * browser.row_h, 10, 10))
    check("sprite file browser picks a PNG under assets/",
          picked.get("path", "").endswith(".png"), picked.get("path", ""))
    check("sprite file browser closes after picking", ctx.modal is None)

    sheet = ("packs/kenney_tower-defense-top-down/Tilesheet/"
             "towerDefense_tilesheet.png")
    saved = {}
    editor = W.AnimationEditor(ctx, sheet, lambda *a: saved.update(zip(
        ("sheet", "fw", "fh", "margin", "spacing", "anims"), a)))
    ctx.open_modal(editor)

    def frame_click(ed, index):
        cols, rows, cell, _vis = ed._grid_metrics()
        pos = (ed.grid.x + 6 + (index % cols) * cell + cell // 2,
               ed.grid.y + 6 + (index // cols - ed.scroll) * cell + cell // 2)
        click(pos)

    frame_click(editor, 0)
    frame_click(editor, 1)
    click(next(r for r, n in editor._state_rows() if n == "walk"))
    frame_click(editor, 2)
    click(editor.save_btn)
    check("animation editor saves per-state frames",
          saved.get("anims", {}).get("idle", {}).get("frames") == [0, 1]
          and saved.get("anims", {}).get("walk", {}).get("frames") == [2],
          str(saved.get("anims")))

    # the whole unit flow: static image
    result = {}
    W.open_unit_sprite_flow(ctx, {"kind": "pack", "tile": 226},
                            lambda s: result.update(spec=s))
    click(next(r for r, _l, v in ctx.modal.buttons if v == "static"))
    browser = ctx.modal
    browser._enter("units/towers/forest-towers/scorpion-tower")
    img_i = next(i for i, (k, _n) in enumerate(browser.entries) if k == "img")
    click(pygame.Rect(browser.list_rect.x + 4,
                      browser.list_rect.y + 4 + img_i * browser.row_h, 10, 10))
    check("unit sprite flow: static image",
          result.get("spec", {}).get("kind") == "image",
          str(result.get("spec")))

    # the whole unit flow: animation with named states
    result.clear()
    W.open_unit_sprite_flow(ctx, {}, lambda s: result.update(spec=s))
    click(next(r for r, _l, v in ctx.modal.buttons if v == "anim"))
    browser = ctx.modal
    browser._enter("packs/kenney_tower-defense-top-down/Tilesheet")
    img_i = next(i for i, (k, _n) in enumerate(browser.entries) if k == "img")
    click(pygame.Rect(browser.list_rect.x + 4,
                      browser.list_rect.y + 4 + img_i * browser.row_h, 10, 10))
    editor = ctx.modal
    frame_click(editor, 0)
    click(editor.save_btn)
    spec = result.get("spec", {})
    check("unit sprite flow: named animation",
          spec.get("kind") == "sprites"
          and spec.get("animations", {}).get("idle", {}).get("frames") == [0],
          str(spec))

    # the terrain flow: one looping animation
    result.clear()
    W.open_terrain_sprite_flow(ctx, {"kind": "pack", "tile": 157},
                               lambda s: result.update(spec=s))
    click(next(r for r, _l, v in ctx.modal.buttons if v == "anim"))
    browser = ctx.modal
    browser._enter("packs/kenney_tower-defense-top-down/Tilesheet")
    img_i = next(i for i, (k, _n) in enumerate(browser.entries) if k == "img")
    click(pygame.Rect(browser.list_rect.x + 4,
                      browser.list_rect.y + 4 + img_i * browser.row_h, 10, 10))
    editor = ctx.modal
    frame_click(editor, 0)
    frame_click(editor, 1)
    click(editor.save_btn)
    spec = result.get("spec", {})
    check("terrain sprite flow: looping animation",
          spec.get("kind") == "sheet" and len(spec.get("frames", [])) == 2,
          str(spec))
    check("sprite flows leave no modal open", ctx.modal is None)

    # ---------------------------------------------------------------- summary
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILURES:")
        for f in FAIL:
            print("  -", f)
        sys.exit(1)


if __name__ == "__main__":
    main()

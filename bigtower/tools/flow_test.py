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

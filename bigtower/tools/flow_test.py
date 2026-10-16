"""End-to-end headless test: menus, gameplay, persistence, fallback saves.

Run:  BIGTOWER_SAVE_DIR=.build_tmp/saves .venv/bin/python tools/flow_test.py
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
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


def click_event(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=pos)


def motion_event(pos):
    return pygame.event.Event(pygame.MOUSEMOTION, pos=pos)


def fast_forward(scene, seconds, dt=1 / 60):
    frames = int(seconds / dt)
    for _ in range(frames):
        if scene.state in ("won", "lost"):
            break
        scene.game.on_update(dt)


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

    # ---------------------------------------------------------------- menus
    from menus.welcome_screen import Scene as Welcome
    game.scene = Welcome(game)
    check("welcome loads", game.scene is not None)

    # fresh save dir -> no users -> overlay must open without crash
    game.scene.action_start()
    check("start with empty users opens overlay",
          len(game.subscenes) == 1 and type(game.subscenes[-1]).__name__ == "Scene"
          and game.subscenes[-1].__module__ == "menus.user_selection")

    overlay = game.subscenes[-1]
    # old read-only save dirs on this machine may still list legacy users;
    # the regression is that an *empty* list must not crash selection logic
    if overlay.userlist.items:
        overlay.userlist.handle_event(key_event(pygame.K_DOWN))
        overlay.userlist.handle_event(key_event(pygame.K_UP))
    check("user list selection safe (even when empty)",
          overlay.userlist.sel_text is None or
          overlay.userlist.sel_text in overlay.userlist.items)
    # type a name and confirm
    for ch in "Tester":
        overlay.handle_event(key_event(getattr(pygame, "K_" + ch.lower(), pygame.K_a), ch))
    overlay.handle_event(key_event(pygame.K_RETURN))
    check("user created + career reached",
          game.user == "Tester" and game.scene.__module__ == "menus.career_menu")
    check("overlay closed", not game.subscenes)

    # --- user selection screen: picking a saved user must actually work ----
    game.scene.action_change_user()
    sel = game.subscenes[-1]
    check("change user opens selector",
          sel.__module__ == "menus.user_selection")
    # Enter with an empty box must be refused with a visible message, not
    # silently ignored (the old bug: a row looked selected but the box was empty)
    sel.handle_event(key_event(pygame.K_RETURN))
    check("empty confirm refused with a message",
          len(game.subscenes) == 1 and bool(sel.status))
    # clicking a saved name selects it and copies it into the box
    idx = sel.userlist.items.index("Tester")
    row = sel.userlist._row_rect(idx - sel.userlist.scroll)
    sel.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                                        pos=row.center))
    sel.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1,
                                        pos=row.center))
    check("clicking a saved user fills the name box",
          sel.input.text == "Tester")
    sel.handle_event(key_event(pygame.K_RETURN))
    check("picking a saved user reaches career",
          not game.subscenes and game.user == "Tester"
          and game.scene.__module__ == "menus.career_menu")

    # settings overlay toggles
    game.scene.action_settings()
    sfx_before = game.settings["sfx"]
    game.subscenes[-1].toggle_sfx()
    check("sfx toggle works", game.settings["sfx"] != sfx_before)
    game.subscenes[-1].close_overlay()

    # level select from career
    game.scene.action_play()
    check("level select opens", len(game.subscenes) == 1
          and game.subscenes[-1].__module__ == "menus.level_select")

    # ---------------------------------------------------------------- battle
    game.subscenes[-1]._launch(0)
    scene = game.scene
    check("game scene loads", scene.__module__ == "engine.game_scene")
    check("map parsed with waypoints",
          len(scene.level.waypoints) == len(scene.level.path_cells) > 10)
    check("path starts at spawn", scene.level.path_cells[0] == scene.level.spawn_cell)
    check("path ends at base", scene.level.path_cells[-1] == scene.level.base_cell)

    # place towers along the path (cheat gold for determinism)
    scene.gold += 5000
    from engine.towers import TOWER_TYPES
    sniper = TOWER_TYPES[3]
    missile = TOWER_TYPES[2]
    placed = 0
    for cell in scene.level.path_cells[3:40:4]:
        adj = (cell[0] + 1, cell[1])
        if scene.level.is_buildable(*adj) and adj not in scene.towers:
            scene.selected_shop = sniper
            scene._try_place(adj)
            placed += 1
        adj2 = (cell[0] - 1, cell[1])
        if placed < 6 and scene.level.is_buildable(*adj2) and adj2 not in scene.towers:
            scene.selected_shop = missile
            scene._try_place(adj2)
            placed += 1
    check("towers placed", placed >= 4, f"placed={placed}")

    # upgrade one tower via the panel logic
    twr = next(iter(scene.towers.values()))
    scene.selected_tower = twr
    scene.gold += 1000
    cost = twr.upgrade_cost()
    scene._panel_click(scene._panel_upgrade_rect().center)
    check("upgrade works", twr.level == 2)
    # sell it back
    value = twr.sell_value()
    scene._panel_click(scene._panel_sell_rect().center)
    check("sell works", twr.cell not in scene.towers and scene.gold >= value)

    # run waves to victory
    scene.selected_shop = None
    scene.selected_tower = None
    scene.first_wave_pending = False
    scene.start_wave()
    fast_forward(scene, 2000)     # up to ~33 min of game time, stops at won/lost
    check("battle reaches an end", scene.state in ("won", "lost"),
          f"state={scene.state} wave={scene.wave_number} kills={scene.session_kills}")
    check("victory achieved", scene.state == "won",
          f"wave={scene.wave_number} lives={scene.lives}")

    stats = core.savestate.load_stats("Tester")
    check("victory recorded", 1 in (stats.get("Levels Completed") or []),
          str(stats))
    check("kills recorded", stats.get("Kills", 0) == scene.session_kills,
          f"{stats.get('Kills')} vs {scene.session_kills}")

    # ---------------------------------------------------------------- defeat
    game.scene = type(scene)(game, 1)   # level 2 fresh
    scene2 = game.scene
    scene2.first_wave_pending = False
    scene2.start_wave()
    fast_forward(scene2, 2000)
    check("defeat without towers", scene2.state == "lost",
          f"state={scene2.state} lives={scene2.lives}")

    # save/load of stats untouched by defeat (kills recorded)
    stats2 = core.savestate.load_stats("Tester")
    check("defeat kills recorded", stats2.get("Kills", 0) >= scene2.session_kills)

    # ------------------------------------------------------- readonly fallback
    ro_dir = Path(tmp) / "readonly"
    ro_dir.mkdir()
    os.chmod(ro_dir, 0o500)  # read-only
    os.environ["BIGTOWER_SAVE_DIR"] = str(ro_dir)
    importlib.reload(core.paths)
    if os.access(ro_dir, os.W_OK):
        # chmod does not restrict directories on this platform (e.g. Windows,
        # or when running as root), so the fallback cannot be exercised here.
        print("SKIP fallback when env dir read-only (chmod not enforced)")
    else:
        check("fallback when env dir read-only",
              str(core.paths.saves_root()) != str(ro_dir),
              str(core.paths.saves_root()))
    os.chmod(ro_dir, 0o700)

    # ---------------------------------------------------------------- summary
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILURES:")
        for f in FAIL:
            print("  -", f)
        sys.exit(1)


if __name__ == "__main__":
    main()

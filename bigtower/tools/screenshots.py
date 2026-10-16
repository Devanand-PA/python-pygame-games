"""Capture screenshots of key screens for visual review (headless).

Run: .venv/bin/python tools/screenshots.py   -> writes .build_tmp/shot_*.png
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pygame

OUT = ROOT / ".build_tmp"
OUT.mkdir(exist_ok=True)


def snap(game, name):
    game.on_draw()
    pygame.image.save(game.canvas, str(OUT / f"shot_{name}.png"))
    print("saved", name)


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def main():
    tmp = tempfile.mkdtemp(prefix="bigtower_shot_")
    os.environ["BIGTOWER_SAVE_DIR"] = tmp
    import importlib
    import core.paths, core.savestate
    importlib.reload(core.paths)
    importlib.reload(core.savestate)

    from core.game import Game
    game = Game()

    # 1. welcome
    from menus.welcome_screen import Scene as Welcome
    game.scene = Welcome(game)
    snap(game, "01_welcome")

    # 2. user selection over welcome
    game.scene.action_start()
    overlay = game.subscenes[-1]
    overlay.input.set_text("Dendaro")
    snap(game, "02_user_select")

    # 3. career
    overlay.confirm()
    snap(game, "03_career")

    # 4. level select
    game.scene.action_play()
    snap(game, "04_level_select")

    # 5. game with towers + enemies mid-wave
    game.subscenes[-1]._launch(0)
    scene = game.scene
    scene.gold += 800
    from engine.towers import TOWER_TYPES
    spots = []
    for cell in scene.level.path_cells:
        for adj in ((cell[0] + 1, cell[1]), (cell[0], cell[1] + 1),
                    (cell[0] - 1, cell[1]), (cell[0], cell[1] - 1)):
            if scene.level.is_buildable(*adj) and adj not in scene.towers:
                spots.append(adj)
        if len(spots) >= 8:
            break
    for i, spot in enumerate(spots[:8]):
        ttower = TOWER_TYPES[i % 4]
        scene.selected_shop = ttower
        scene._try_place(spot)
    scene.selected_shop = None
    scene.first_wave_pending = False
    scene.start_wave()
    for _ in range(int(14 / (1 / 60))):
        if scene.state in ("won", "lost"):
            break
        game.on_update(1 / 60)
    snap(game, "05_battle")

    # 6. tower selected -> info panel
    scene.selected_tower = next(iter(scene.towers.values()))
    snap(game, "06_panel")
    scene.selected_tower = None

    # 7. pause overlay
    from menus.pause_overlay import Scene as Pause
    game.subscenes.append(Pause(game, scene))
    snap(game, "07_pause")
    game.subscenes.pop()

    # 8. settings overlay
    from menus.settings_overlay import Scene as Settings
    game.subscenes.append(Settings(game))
    snap(game, "08_settings")
    game.subscenes.pop()

    # 9. victory screen (force)
    scene.state = "won"
    snap(game, "09_victory")

    # 10. ghost placement
    scene2 = type(scene)(game, 2)
    game.scene = scene2
    scene2.gold = 500
    scene2.selected_shop = TOWER_TYPES[3]
    scene2.mouse_pos = scene2.level.cell_center((9, 0))
    snap(game, "10_ghost")

    print("done")


if __name__ == "__main__":
    main()

"""Capture screenshots of key screens for visual review (headless).

Run: .venv/bin/python tools/screenshots.py   -> writes .build_tmp/shot_*.png
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
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

    # 4. campaign select
    game.scene.action_play()
    campaign = game.subscenes[-1]
    snap(game, "04_campaign_select")

    # 5. level select
    campaign._launch(campaign.races[0])
    level_sel = game.subscenes[-1]
    snap(game, "05_level_select")

    # 6. game with units + enemies mid-wave
    level_id = level_sel.levels[0]["id"]
    level_sel._launch(level_id)
    scene = game.scene
    scene.gold += 800
    spots = []
    for cell in scene.level.path_cells:
        for adj in ((cell[0] + 1, cell[1]), (cell[0], cell[1] + 1),
                    (cell[0] - 1, cell[1]), (cell[0], cell[1] - 1)):
            if scene.level.is_buildable(*adj) and adj not in scene.towers_by_cell:
                spots.append(adj)
        if len(spots) >= 8:
            break
    for i, spot in enumerate(spots[:8]):
        scene.selected_shop = scene.shop_units[i % len(scene.shop_units)]
        scene._try_place(spot)
    scene.selected_shop = None
    scene.first_wave_pending = False
    scene.start_wave()
    for _ in range(int(14 / (1 / 60))):
        if scene.state in ("won", "lost"):
            break
        game.on_update(1 / 60)
    snap(game, "06_battle")

    # 7. unit selected -> info panel
    scene.selected_unit = next(iter(scene.towers_by_cell.values()))
    snap(game, "07_panel")
    scene.selected_unit = None

    # 8. pause overlay
    from menus.pause_overlay import Scene as Pause
    game.subscenes.append(Pause(game, scene))
    snap(game, "08_pause")
    game.subscenes.pop()

    # 9. settings overlay
    from menus.settings_overlay import Scene as Settings
    game.subscenes.append(Settings(game))
    snap(game, "09_settings")
    game.subscenes.pop()

    # 10. victory screen (force)
    scene.state = "won"
    snap(game, "10_victory")

    # 11. ghost placement on an alien map
    from core.content import get_content
    from engine.game_scene import GameScene
    content = get_content()
    alien_race = content.race("aliens")
    alien_level = content.race_levels(alien_race)[0]["id"]
    scene2 = GameScene(game, alien_level)
    game.scene = scene2
    scene2.gold = 500
    scene2.selected_shop = scene2.shop_units[-1]
    scene2.mouse_pos = scene2.level.cell_center((9, 4))
    snap(game, "11_ghost_alien")

    print("done")


if __name__ == "__main__":
    main()

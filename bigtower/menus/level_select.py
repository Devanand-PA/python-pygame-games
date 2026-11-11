"""Level select: the race's campaign region as a pannable, zoomable world map.

What used to be a vertical stack of level buttons is now a map (see
:mod:`engine.worldmap`): every level is a pin on the campaign region, the
road between them shows progress, and the player pans and zooms to reach
the one they want.  Clicking a pin opens its briefing; Play (or Enter)
launches the level.  ``Esc`` closes the briefing, then steps back to the
campaign picker.

The scene keeps the old public surface -- ``self.levels`` (ordered level
dicts) and ``_launch(level_id)`` -- so the flow tests and screenshot tools
that drive the menus keep working unchanged.
"""
import pygame

from core import savestate
from core.content import get_content
from core.scene import Scene
from engine.worldmap import WorldMap


class Scene(Scene):
    scene_type = "menu"

    def __init__(self, game, race):
        super().__init__(game)
        self.content = get_content()
        self.race = race or {}
        self.levels = self.content.race_levels(self.race)
        self.completed = savestate.levels_completed(game.user or "Player")
        self.world = WorldMap(
            game, self.race, self.content, self.completed,
            on_play=self._launch, on_back=self.action_back)

    # ---------------------------------------------------------------- actions
    def _launch(self, level_id):
        from engine.game_scene import GameScene
        if self in self.game.subscenes:
            self.game.subscenes.remove(self)
        self.game.scene = GameScene(self.game, level_id)

    def action_back(self):
        """Return to the campaign picker (the race list), same overlay slot."""
        from menus.campaign_select import Scene as Campaign
        if self in self.game.subscenes:
            self.game.subscenes.remove(self)
            self.game.subscenes.append(Campaign(self.game))
        else:
            self.replace_with(Campaign(self.game))

    # ---------------------------------------------------------------- events
    def handle_event(self, event):
        self.world.handle_event(event)

    def handle_keypress(self):
        self.world.handle_keypress()

    def on_update(self, delta_time):
        self.world.update(delta_time)

    def on_draw(self):
        self.world.draw(self.game.canvas)

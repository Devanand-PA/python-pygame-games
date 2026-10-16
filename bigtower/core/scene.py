"""Base class for all scenes (menus, overlays, gameplay)."""


class Scene:
    """A full-screen scene or an overlay subscene.

    Lifecycle driven by core.game.Game:
        on_update(delta_time)  -- simulation (only for the active scene)
        on_draw(surface)       -- rendering (back to front)
        handle_event(event)    -- one SDL event
        handle_keypress()      -- legacy continuous-key hook (kept for menus)
        on_resize()            -- window size changed
    """

    scene_type = "menu"

    def __init__(self, game):
        self.game = game

    # -- optional hooks -----------------------------------------------------
    def on_update(self, delta_time):
        pass

    def on_draw(self):
        pass

    def handle_event(self, event):
        pass

    def handle_keypress(self):
        pass

    def on_resize(self):
        pass

    # -- convenience --------------------------------------------------------
    @property
    def screen(self):
        return self.game.canvas

    def replace_with(self, scene):
        """Swap the current scene for another (menus chain via this)."""
        self.game.scene = scene

    def push_overlay(self, scene):
        self.game.subscenes.append(scene)

    def close_overlay(self):
        if self.game.subscenes:
            self.game.subscenes.pop()

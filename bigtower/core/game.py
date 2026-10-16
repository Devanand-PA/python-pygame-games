"""The Game object: window, main loop, scene stack, audio.

Rendering model: the game always draws onto a fixed 1280x720 canvas surface,
which is then scaled (letterboxed) into the real window.  This keeps layouts
stable on any window size / monitor, and lets fullscreen be a pure toggle.
"""
import json

import pygame

from core import paths
from core import settings as S


class Game:
    def __init__(self, fullscreen=False):
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        pygame.display.set_caption(S.WINDOW_TITLE)

        cfg = self._load_config()
        self.settings = {
            "sfx": bool(cfg.get("sfx", True)),
            "fullscreen": bool(cfg.get("fullscreen", fullscreen)),
            "last_user": str(cfg.get("last_user", "") or ""),
        }

        self.window = pygame.display.set_mode(
            (S.CANVAS_W, S.CANVAS_H), pygame.RESIZABLE)
        if self.settings["fullscreen"]:
            self._apply_fullscreen()

        self.canvas = pygame.Surface((S.CANVAS_W, S.CANVAS_H)).convert()
        self._view_flags = None       # (win_size, fullscreen) -> scaled cache
        self._view_rect = (0, 0, S.CANVAS_W, S.CANVAS_H)
        self._refresh_view_cache()

        self.clock = pygame.time.Clock()
        self.delta_time = 0.0
        self.user = None
        self.scene = None
        self.subscenes = []           # overlay stack (pause, dialogs, ...)
        self.running = True
        self._sounds = self._load_sounds()

        self.fonts = {
            "small": pygame.font.Font(None, 22),
            "default": pygame.font.Font(None, 30),
            "big": pygame.font.Font(None, 48),
            "title": pygame.font.Font(None, 60),
        }

    # ------------------------------------------------------------------ config
    def _load_config(self):
        data = {}
        try:
            with open(paths.config_file(), "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError, ValueError):
            data = {}
        return data if isinstance(data, dict) else {}

    def save_config(self):
        try:
            path = paths.config_file()
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(self.settings, fh)
        except OSError:
            pass

    # ------------------------------------------------------------------ window
    def _apply_fullscreen(self):
        info = pygame.display.Info()
        self.window = pygame.display.set_mode(
            (info.current_w, info.current_h), pygame.FULLSCREEN)

    def toggle_fullscreen(self):
        self.settings["fullscreen"] = not self.settings["fullscreen"]
        if self.settings["fullscreen"]:
            self._apply_fullscreen()
        else:
            self.window = pygame.display.set_mode(
                (S.CANVAS_W, S.CANVAS_H), pygame.RESIZABLE)
        self._refresh_view_cache()
        self.save_config()

    def _refresh_view_cache(self):
        win = self.window.get_size()
        flags = (win, self.settings["fullscreen"])
        if self._view_flags == flags:
            return
        self._view_flags = flags
        ww, wh = win
        scale = min(ww / S.CANVAS_W, wh / S.CANVAS_H)
        w, h = max(1, round(S.CANVAS_W * scale)), max(1, round(S.CANVAS_H * scale))
        self._view_rect = ((ww - w) // 2, (wh - h) // 2, w, h)

    def _blit_to_window(self):
        self._refresh_view_cache()
        x, y, w, h = self._view_rect
        if (w, h) == (S.CANVAS_W, S.CANVAS_H):
            self.window.blit(self.canvas, (x, y))
        else:
            scaled = pygame.transform.smoothscale(self.canvas, (w, h))
            self.window.fill((10, 10, 14))
            self.window.blit(scaled, (x, y))
        pygame.display.flip()

    def _to_canvas_pos(self, pos):
        """Map a window-space mouse position into canvas space."""
        x, y, w, h = self._view_rect
        if w <= 0 or h <= 0:
            return (0, 0)
        cx = (pos[0] - x) * S.CANVAS_W / w
        cy = (pos[1] - y) * S.CANVAS_H / h
        return (int(cx), int(cy))

    # ------------------------------------------------------------------ audio
    def _load_sounds(self):
        names = {
            "click": "pepSound1.ogg",
            "place": "powerUp2.ogg",
            "upgrade": "powerUp5.ogg",
            "sell": "lowDown.ogg",
            "gun": "laser3.ogg",
            "missile": "zap2.ogg",
            "sniper": "laser8.ogg",
            "sting": "laser1.ogg",
            "death": "spaceTrash2.ogg",
            "boom": "spaceTrash5.ogg",
            "leak": "lowThreeTone.ogg",
            "wave": "threeTone2.ogg",
            "victory": "powerUp12.ogg",
            "defeat": "zapThreeToneDown.ogg",
            "error": "phaserDown1.ogg",
        }
        sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(44100, -16, 2, 512)
            for key, fname in names.items():
                path = paths.asset("audio", fname)
                if path.exists():
                    try:
                        sounds[key] = pygame.mixer.Sound(str(path))
                    except pygame.error:
                        pass
        except pygame.error:
            pass  # no audio device (headless) - play silently
        return sounds

    def play(self, name, volume=0.5):
        snd = self._sounds.get(name)
        if snd is not None:
            try:
                snd.set_volume(volume)
                snd.play()
            except pygame.error:
                pass

    def set_sfx(self, enabled: bool):
        self.settings["sfx"] = bool(enabled)
        if enabled and not self._sounds:
            self._sounds = self._load_sounds()
        self.save_config()

    def set_user(self, name: str):
        """Remember the active profile so the menu can offer to continue it."""
        self.user = name or None
        self.settings["last_user"] = name or ""
        self.save_config()

    # ------------------------------------------------------------------ scenes
    def on_quit(self):
        self.running = False

    def on_update(self, delta_time):
        if self.subscenes:
            self.subscenes[-1].on_update(delta_time)
        elif self.scene is not None:
            self.scene.on_update(delta_time)

    def on_draw(self):
        self.canvas.fill((10, 10, 14))
        if self.scene is not None:
            self.scene.on_draw()
        for scene in self.subscenes:
            scene.on_draw()

    def _dispatch_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
            self.toggle_fullscreen()
            return
        if event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN,
                          pygame.MOUSEBUTTONUP):
            event.pos = self._to_canvas_pos(event.pos)
        elif event.type == pygame.MOUSEWHEEL:
            # MOUSEWHEEL has no position of its own; some widgets need one,
            # so attach the current (canvas-space) cursor position.
            event.pos = self._to_canvas_pos(pygame.mouse.get_pos())
        target = self.subscenes[-1] if self.subscenes else self.scene
        if target is not None:
            target.handle_event(event)

    def run(self):
        while self.running:
            # 1. events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                else:
                    self._dispatch_event(event)

            # 2. simulate
            if self.delta_time > 0.0:
                self.on_update(self.delta_time)

            # 3. render
            self.on_draw()
            self._blit_to_window()

            # 4. continuous-key hook for menus
            target = self.subscenes[-1] if self.subscenes else self.scene
            if target is not None:
                target.handle_keypress()

            self.delta_time = min(self.clock.tick(S.FPS) / 1000.0, 0.05)

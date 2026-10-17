import pygame


class Game :
    def __init__(self) :
        pygame.init()
        self.screen_info = pygame.display.Info()
        
        self.screen_size = ( self.screen_info.current_w , self.screen_info.current_h )
        self.difficulty_level = None
        
        self.FULLSCREEN = True
        self.screen = pygame.display.set_mode(
                self.screen_size,
                pygame.FULLSCREEN
                )
        pygame.display.set_caption("paddle")

        self.clock = pygame.time.Clock()
        self.dt = 1/60  # seconds per frame; overwritten in run()
        self.default_font = pygame.font.Font(None, 30)
        self.title_font_size = 60
        self.title_font = pygame.font.Font(None, self.title_font_size)
        self.sel_color = (100,100,20)
        self.unsel_color = (20,20,20)

        from scenes.welcome_screen import Scene
        self.scene = Scene(self)

    def run(self) :
        self.running = True
        while self.running :
            # Tick once per frame; all code uses this single dt value.
            self.dt = self.clock.tick(120) / 1000.0
            self.scene.update()
            self.scene.draw()
            pygame.display.flip()

            for event in pygame.event.get() :
                if event.type == pygame.QUIT :
                    self.running = False
                self.scene.handle_event(event)

            self.scene.handle_keypress()

    def update_save(self) :
        if hasattr(self.scene,"update_savedata") :
            self.scene.update_savedata()

    def update_resolution(self) :
        if hasattr(self.scene,"update_resolution") :
            self.scene.update_resolution()

    def load_save(self) :
        import os
        if not os.path.exists('saves') :
            os.mkdir('saves')

        import json
        try :
            with open('saves/test.save') as savedata :
                savedata = json.load(savedata)
        except (FileNotFoundError, json.JSONDecodeError) :
            return  # no (valid) save file – keep the current scene

        if hasattr(self.scene,"load_savedata") :
            self.scene.load_savedata(savedata)
        else :
            import importlib
            sceneLib = importlib.import_module(savedata["scene"])
            loadedScene = getattr(sceneLib, "Scene")
            self.scene = loadedScene(self)
            self.scene.load_savedata(savedata)



game = Game()
game.run()

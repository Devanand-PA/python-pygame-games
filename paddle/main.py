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
            self.scene.update()
            self.scene.draw()
            pygame.display.flip()
            self.clock.tick(120)
            
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
        with open('saves/test.save') as savedata :
            savedata = json.load(savedata)

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

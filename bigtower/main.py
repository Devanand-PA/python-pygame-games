import pygame

# Screen settings
# SCREEN_WIDTH = 800
# SCREEN_HEIGHT = 600
SCREEN_TITLE = "Big Tower"


class Game():
    def __init__(self):
        pygame.init()
        self.screen_info = pygame.display.Info()
        self.user = None
        self.subscenes = []
        self.screen_size = [self.screen_info.current_w , self.screen_info.current_h ] 
        #self.screen_size = [ SCREEN_WIDTH ,SCREEN_HEIGHT ]
        self.screen = pygame.display.set_mode(
                self.screen_size,
                pygame.FULLSCREEN
                )
        self.clock = pygame.time.Clock()
        self.default_font = pygame.font.Font(None, 30)
        self.title_font = pygame.font.Font( None, 60)

        from menus.welcome_screen import Scene
        self.scene = Scene(self)
        self.running = True

    def on_quit(self) :
        self.running = False

    def on_draw(self):
        self.scene.on_draw()
        for scene in self.subscenes :
            scene.on_draw()


    def on_update(self, delta_time):
        if not self.subscenes :
            self.scene.on_update(delta_time)
        else :
            self.subscenes[-1].on_update(delta_time)

    def run(self) :
        self.delta_time = self.clock.tick(60) / 1000.0
        self.running = True
        while self.running :
            self.on_update(self.delta_time)
            self.on_draw()
            pygame.display.flip()
            
            for event in pygame.event.get() :
                if event.type == pygame.QUIT :
                    self.running = False
                
                if not self.subscenes :
                    self.scene.handle_event(event)
                elif self.subscenes : 
                    self.subscenes[-1].handle_event(event)

            if not self.subscenes :
                self.scene.handle_keypress()
            elif self.subscenes :
                self.subscenes[-1].handle_keypress()


if __name__ == "__main__":
    game = Game()
    game.run()
        

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
        self.child_process = None          # <-- add this

        self.clock = pygame.time.Clock()
        self.delta_time = self.clock.tick(60) / 1000.0
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

    def run(self):
        self.running = True
        while self.running:
            # Always drain events so Quit still works and the OS
            # doesn't consider the window unresponsive.
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    continue

                if self.child_process is None:
                    if not self.subscenes:
                        self.scene.handle_event(event)
                    elif self.subscenes:
                        self.subscenes[-1].handle_event(event)

            if self.child_process is not None:
                # Child is running: idle cheaply until it exits.
                if self.child_process.poll() is not None:
                    self.child_process = None
                    # Redraw once so the menu isn't stale.
                    self.on_draw()
                    pygame.display.flip()
                else:
                    # Sleep ~30 ms per frame instead of rendering at 60 FPS.
                    pygame.time.wait(30)
                    continue

            self.on_update(self.delta_time)
            self.on_draw()
            pygame.display.flip()

            if not self.subscenes:
                self.scene.handle_keypress()
            elif self.subscenes:
                self.subscenes[-1].handle_keypress()

            self.delta_time = self.clock.tick(60) / 1000.0

if __name__ == "__main__":
    game = Game()
    game.run()
        

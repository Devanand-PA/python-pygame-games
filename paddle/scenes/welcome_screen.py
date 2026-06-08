import pygame

from gui_utils.gui_elements import Button
class Scene :
    def __init__(self, game):
        self.game = game
        self.scene_type = "Menu"
        self.welcomeTextRaw = "__Bad Paddle__"
        self.welcome_text = self.game.title_font.render(
                self.welcomeTextRaw,
                True,
                (100,150,50)
                )
        self.selected_main_option = "New Game"
        self.title_rect = self.welcome_text.get_rect(
    center=(
        self.game.screen_size[0] // 2,
        self.game.screen_size[1] // 3
    )
        )
        
        # buttons
        self.newgame_button = Button(self.game,
                            (self.title_rect.x + 10, self.title_rect.y + 50),
                            (self.title_rect.width - 20, self.title_rect.height),"New Game", sel= True)

        self.loadgame_button = Button(self.game,
                            (self.title_rect.x + 10, self.title_rect.y + 110),
                            (self.title_rect.width - 20, self.title_rect.height),"Load Game")

        self.settings_button = Button(self.game,
                            (self.title_rect.x + 10, self.title_rect.y + 170),
                            (self.title_rect.width - 20, self.title_rect.height),"Settings")

        self.quitgame_button = Button(self.game,
                            (self.title_rect.x + 10 , self.title_rect.y + 230),
                            (self.title_rect.width - 20 , self.title_rect.height),"Quit Game")

        self.menubuttons = [self.newgame_button , self.loadgame_button , self.settings_button ,self.quitgame_button ]
        self.settings_menu_enabled = False
    def update(self) :
        pass

    def handle_event(self,event) :
        if self.settings_menu_enabled :
            self.settings_menu.handle_event(event)
        else :
            self.default_handle_event(event)

    def update_resolution(self) :
        self.title_rect = self.welcome_text.get_rect(
    center=(
        self.game.screen_size[0] // 2,
        self.game.screen_size[1] // 3
    )
        )
        
        # buttons
        self.newgame_button = Button(self.game,
                            (self.title_rect.x + 10, self.title_rect.y + 50),
                            (self.title_rect.width - 20, self.title_rect.height),"New Game", sel= True)

        self.loadgame_button = Button(self.game,
                            (self.title_rect.x + 10, self.title_rect.y + 110),
                            (self.title_rect.width - 20, self.title_rect.height),"Load Game")

        self.settings_button = Button(self.game,
                            (self.title_rect.x + 10, self.title_rect.y + 170),
                            (self.title_rect.width - 20, self.title_rect.height),"Settings")

        self.quitgame_button = Button(self.game,
                            (self.title_rect.x + 10 , self.title_rect.y + 230),
                            (self.title_rect.width - 20 , self.title_rect.height),"Quit Game")

        self.menubuttons = [self.newgame_button , self.loadgame_button , self.settings_button ,self.quitgame_button ]


    def default_handle_event(self,event) :
        if event.type == pygame.KEYDOWN :
            if (self.quitgame_button.sel == True) and (event.key == pygame.K_RETURN):
                self.game.running = False
    
            if (self.newgame_button.sel == True) and (event.key == pygame.K_RETURN):
                from scenes.scene_1 import Scene
                self.game.scene = Scene(self.game)

            if (self.loadgame_button.sel == True) and (event.key == pygame.K_RETURN):
                self.game.load_save()

            if (self.settings_button.sel == True) and (event.key == pygame.K_RETURN):
                from scenes.settings_menu import Scene as settings_menu
                self.settings_menu = settings_menu(self,self.game)
                self.settings_menu_enabled = True


            if event.key == pygame.K_UP :
                for i in range(len(self.menubuttons)) :
                    if (self.menubuttons[i].sel == True) :
                        self.menubuttons[i].sel = False
                        self.menubuttons[ (i-1) % len(self.menubuttons)].sel = True
                        break
    
            if event.key == pygame.K_DOWN :
                for i in range(len(self.menubuttons)) :
                    if (self.menubuttons[i].sel == True) :
                        self.menubuttons[i].sel = False
                        self.menubuttons[ (i+1) % len(self.menubuttons)].sel = True
                        break

    def handle_keypress(self) :
        pass
    
    def draw_menuoptions(self) :
        for button in self.menubuttons :
            button.draw()

    def draw(self) :
        self.game.screen.fill((0,0,0))
        if self.settings_menu_enabled :
            self.settings_menu.draw()
        else :
            self.game.screen.blit(self.welcome_text,
                                self.title_rect
            )
    
            # Border rectangle
            pygame.draw.rect(self.game.screen,
                            self.game.sel_color,
                            ( self.title_rect.x , self.title_rect.y - 10, 
                                self.title_rect.width , (len(self.menubuttons) + 1)*60),
                            5)
            self.draw_menuoptions()
        


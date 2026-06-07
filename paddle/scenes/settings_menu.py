import pygame

from gui_utils.gui_elements import Button
class Scene :
    def __init__(self, parent_scene ,game):
        self.game = game
        self.parent_scene = parent_scene
        self.welcomeTextRaw = "__________Settings_________"
        font = pygame.font.SysFont(None, 40)
        font.set_underline(True)
        self.welcome_text = self.game.title_font.render(
                self.welcomeTextRaw,
                True,
                (100,150,50)
                )
        self.title_rect = self.welcome_text.get_rect(
                            center=(
                                self.game.screen_size[0] // 2,
                                self.game.screen_size[1] // 3
                            ))

        #========== Objects =================

        self.display_settings_header = font.render(
                "Display Settings",
                True,
                (100,150,50)
                )
        
        self.toggle_fullscreen_button = Button(game,[0,0],[self.title_rect.width - 20, 60],"Toggle Fullscreen")


        #====================================

        self.settings_menu_objects  = [
                { "item" : self.display_settings_header , "type" : "Text" },
                { "item" : self.toggle_fullscreen_button, "type" : "Button"}

                ]



        self.displacement_y = 70
        for i in self.settings_menu_objects :
            if i["type"] == "Text" :
                    i["rect"] = i["item"].get_rect(center=(( self.title_rect.center[0] + self.title_rect.x ) /2 , self.title_rect.y + self.displacement_y))
            elif i["type"] == "Button" :
                    i["item"].coords = [self.title_rect.x + 10 , self.title_rect.y + self.displacement_y]
            self.displacement_y += 70

        self.button_list = [ i["item"] for i in self.settings_menu_objects if ( i["type"] == "Button" ) ]
        self.button_list[0].sel = True

    def update(self) :
        pass

    def  update_resolution(self) :
        self.title_rect = self.welcome_text.get_rect(
                            center=(
                                self.game.screen_size[0] // 2,
                                self.game.screen_size[1] // 3
                            ))
        self.displacement_y = 70
        for i in self.settings_menu_objects :
            if i["type"] == "Text" :
                    i["rect"] = i["item"].get_rect(center=(( self.title_rect.center[0] + self.title_rect.x ) /2 , self.title_rect.y + self.displacement_y))
            elif i["type"] == "Button" :
                    i["item"].coords = [self.title_rect.x + 10 , self.title_rect.y + self.displacement_y]
            self.displacement_y += 70

    def handle_event(self,event) :
        if event.type == pygame.KEYDOWN :
            if (event.key == pygame.K_ESCAPE):
                self.parent_scene.settings_menu_enabled  = False
            
            if (self.toggle_fullscreen_button.sel == True) and (event.key == pygame.K_RETURN):
                self.game.FULLSCREEN = not self.game.FULLSCREEN
                if  self.game.FULLSCREEN :
                            self.game.screen = pygame.display.set_mode(
                                    self.game.screen_size,
                                        pygame.FULLSCREEN
                                            )   
                            self.game.screen_info = pygame.display.Info()
                            self.game.screen_size = ( self.game.screen_info.current_w , self.game.screen_info.current_h )
                else :
                            self.game.screen = pygame.display.set_mode(
                                    (1280,720),
                                            )   
                            self.game.screen_size = ( 1280, 720)
                self.update_resolution()
                self.game.update_resolution()
                self.parent_scene.update_resolution()
                            



            if event.key == pygame.K_UP :
                for i in range(len(self.button_list)) :
                    if (self.button_list[i].sel == True) :
                        self.button_list[i].sel = False
                        self.button_list[ (i-1) % len(self.button_list)].sel = True
                        break
    
            if event.key == pygame.K_DOWN :
                for i in range(len(self.button_list)) :
                    if (self.button_list[i].sel == True) :
                        self.button_list[i].sel = False
                        self.button_list[ (i+1) % len(self.button_list)].sel = True
                        break

    def handle_keypress(self) :
        pass
    

    def draw_menuoptions(self) :
        pass

    def draw(self) :
        self.game.screen.blit(self.welcome_text,
                              self.title_rect
        )
        pygame.draw.rect(self.game.screen,
                            self.game.sel_color,
                            ( self.title_rect.x , self.title_rect.y - 10, 
                                self.title_rect.width , self.displacement_y + 70),
                            5)

        for i in self.settings_menu_objects :
            if i["type"] == "Text" :
                self.game.screen.blit(
                        i["item"],
                        i["rect"]
                        )
            elif i["type"] == "Button" :
                i["item"].draw()

        # Border rectangle

import pygame
from utils.gui_elements import Button , namecallableList

class Scene() :
    def __init__ (self,game) :
        self.game = game
        self.background = pygame.image.load("assets/menus/welcom_screen_background.jpg")
        self.on_resize()
        self.mainbox_color = (10,10,10)
        self.framebox_color = (0,0,0)
        self.framebox =  pygame.Rect(
                10,
                10,
                self.game.screen_size[0] - 20,
                self.game.screen_size[1] - 20
                    )
        self.mainbox_width = self.game.screen_size[0] // 4
        self.mainbox_height = self.game.screen_size[1] - 20

        self.mainbox =  pygame.Rect(
                10,
                10,
                self.mainbox_width,
                self.mainbox_height
                )
        
        self.mainboxitems = namecallableList([
            {   "name"  : "Campaign Button",
                "type"  : "Button" ,
                "text"  : "Campaign Menu",
                "item"  : None
                },

            {   "name"  : "Main Menu Button",
                "type"  : "Button" ,
                "text"  : "Back to Main Menu",
                "item"  : None
                },

            {   "name"  : "Settings Button",
                "type"  : "Button" ,
                "text"  : "Settings",
                "item"  : None
                }

            ])

        self.init_buttons()
    


    def init_buttons(self) :
        top_pad = 0
        button_height = 50
        for item in self.mainboxitems :
            if item["type"] == "Button" :
                item["item"] = Button(self.game,
                                    [self.mainbox.x + 10, self.mainbox.y + 10 + top_pad],
                                    [self.mainbox_width - 20 , button_height],
                                    fgcolor=[(0,0,0),(0,0,0)],
                                    bgcolor=[(100,100,0),(200,200,0)],
                                    text=item["text"],
                                    sel=False
                                      )

            top_pad += item["item"].size[1] + 10
        self.mainboxitems[0]["item"].sel = True
        self.mainbox.height = top_pad + 10


    def on_draw(self) :
        self.game.screen.blit(
                self.background,
                (0,0)
                )

        # Border Box
        pygame.draw.rect(
                self.game.screen,
            self.framebox_color,
            self.framebox,
            5
            )


        # Main Box
        pygame.draw.rect(
                self.game.screen,
            self.mainbox_color,
            self.mainbox,
            )
        
        for item in self.mainboxitems :
            item["item"].on_draw()




    def on_resize(self) :
        self.background = pygame.transform.scale(self.background,(self.game.screen_size[0], self.game.screen_size[1]))

    def default_handle_event(self,event) :
        if event.type == pygame.KEYDOWN :
            if (self.mainboxitems["Main Menu Button"]["item"].sel) and (event.key == pygame.K_RETURN):
                from menus.welcome_screen import Scene
                self.game.scene = Scene(self.game)
            
            elif event.key == pygame.K_UP :
                for i in range(len(self.mainboxitems)) :
                    if (self.mainboxitems[i]["item"].sel == True) :
                        self.mainboxitems[i]["item"].sel = False
                        self.mainboxitems[ (i-1) % len(self.mainboxitems)]["item"].sel = True
                        break
    
            elif event.key == pygame.K_DOWN :
                for i in range(len(self.mainboxitems)) :
                    if (self.mainboxitems[i]["item"].sel == True) :
                        self.mainboxitems[i]["item"].sel = False
                        self.mainboxitems[ (i+1) % len(self.mainboxitems)]["item"].sel = True
                        break


    def handle_event(self,event) :
        self.default_handle_event(event)
    
    def handle_keypress(self) :
        pass

    def on_update(self,delta_time) :
        pass

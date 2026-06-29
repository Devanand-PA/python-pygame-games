import pygame
import json
from utils.gui_elements import Button , namecallableList
from utils.savestate import save_game

class Scene() :
    def __init__ (self,game) :
        self.game = game
        self.background = pygame.image.load("assets/menus/welcom_screen_background.jpg")
        self.on_resize()
        self.scene_type = "menu"
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
                "item"  : None, 
                "function" : self.action_main_menu_button_pressed
                },
            {   "name"  : "Change User Button",
                "type"  : "Button" ,
                "text"  : "Change User",
                "item"  : None,
                "function" : self.action_change_user
                },

            {   "name"  : "Settings Button",
                "type"  : "Button" ,
                "text"  : "Settings",
                "item"  : None
                }

            ])

        self.init_buttons()
        self.init_stats_screen()
    


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
    
    def init_stats_screen(self) : 
        import pathlib
        userdir =   pathlib.Path.home() / "Documents"  / "Saves" / "bigtower" / self.game.user
        stats_file =  userdir / "user_stats.json"
        if not stats_file.exists() :
            self.user_stats = {
                    "Campaigns Cleared" : 0,
                    "Kills"             : 0
                    }
            with open (str(stats_file),'w') as FILE :
                json.dump(self.user_stats,FILE)

        else :
            with open (str(stats_file)) as FILE :
                self.user_stats = json.load(FILE)
        
        self.statlines = [self.game.user[:((2*self.framebox.width) // 3)//(self.game.default_font.size("A")[0])]]
        self.rendered_stats = []
        for stat in self.user_stats :
            self.statlines.append(f"{stat}:{self.user_stats[stat]}")
            if (len(self.statlines) * self.game.default_font.get_height()) >= (self.framebox.height - 10) :
                break
        
        for statline in self.statlines :
            self.rendered_stats.append(self.game.default_font.render(statline, True,(0,0,0)))
            




            

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

        # Stats
        for i, stat in enumerate(self.rendered_stats) :
            self.game.screen.blit(
                stat,
                ( ((self.mainbox.right + self.framebox.right)//3) ,
                  self.framebox.y + 10 + (i*self.game.default_font.get_height()) )
                    )
            if self.statlines[i] == self.game.user :
                pygame.draw.line(self.game.screen, (0,0,0) ,
                                 (((self.mainbox.right + self.framebox.right)//3),
                                  self.framebox.y + 5 + ((i+1)*self.game.default_font.get_height())
                                  ),
                                 (((self.mainbox.right + self.framebox.right)//3 + self.game.default_font.size(self.game.user)[0]),
                                  self.framebox.y + 5 + ((i+1)*self.game.default_font.get_height())
                                  ),
                                 2
                                )



    def action_change_user(self) :
                    from utils.savestate import list_users
                    enlisted_users = list_users()
                    from menus.user_selection import Scene as subscene
                    self.game.subscenes.append(subscene(self.game,enlisted_users,next_scene="menus.career_menu"))

    def action_main_menu_button_pressed(self) :
                from menus.welcome_screen import Scene
                self.game.scene = Scene(self.game)

    def on_resize(self) :
        self.background = pygame.transform.scale(self.background,(self.game.screen_size[0], self.game.screen_size[1]))

    def default_handle_event(self,event) :

        if event.type == pygame.MOUSEMOTION :
            for item in self.mainboxitems :
                if item["item"].rect.collidepoint(event.pos) :
                    for item2 in self.mainboxitems :
                        item2["item"].sel = False
                    item["item"].sel = True

        if event.type == pygame.MOUSEBUTTONUP :
            if event.button == 1 :
                for item in self.mainboxitems :
                    if item["item"].rect.collidepoint(event.pos) :
                        item["item"].sel = True
                        if "function" in item :
                            item["function"]()


        if event.type == pygame.KEYDOWN :
            if (event.key == pygame.K_RETURN):
                for item in self.mainboxitems :
                    if (item["item"].sel) and ("function" in item) :
                            item["function"]()
            
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

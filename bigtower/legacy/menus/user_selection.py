import pygame
from utils.gui_elements import namecallableList , InputBox , ListBox , Button

class Scene() :
    def __init__ (self, game , enlisted_users, next_scene=None) :
        self.game = game
        self.background = pygame.image.load("assets/menus/welcom_screen_background_2.jpg")
        self.subscene_index = len(game.subscenes)
        self.enlisted_users = enlisted_users or []
        self.next_scene = next_scene
        self.mainbox_width = self.game.screen_size[0] // 2
        self.mainbox_height = self.game.screen_size[1] // 2
        self.mainbox_color = (10,10,10)
        self.mainbox =  pygame.Rect(
                self.game.screen_size[0] // 4,
                self.game.screen_size[1] // 4,
                self.mainbox_width,
                self.mainbox_height
                )
        self.background = pygame.transform.scale(self.background,(self.mainbox.width, self.mainbox.height))
        self.mainboxitems = namecallableList([
            { "name" : "User Input",
                "type" : "InputBox",

                },
            { "name" : "User List",
                "type" : "ListBox",
                "list" : self.enlisted_users}

            ])
        self.init_menuitems()
        self.titleprompt = "Enter User Name"
        self.rendered_title = Button(self.game,
                                     [ self.mainbox.x ,self.mainbox.y - self.game.title_font.size(self.titleprompt)[1]],
                                     list(self.game.title_font.size(self.titleprompt)),
                                     text=self.titleprompt,
                                     font = pygame.font.Font(None,36)
                                     )


    def init_menuitems(self) :
        pad_y_init = 10
        pad_y = pad_y_init
        for item in self.mainboxitems :
            if item["type"] == "InputBox" :
                item["item"] = InputBox(self.game,
                                        [ self.mainbox.x + (self.mainbox.width// 10)  , self.mainbox.y + pad_y ],
                                        [(self.mainbox.width * 8) //10 , "doesn't matter" ],
                                        font_size=48,sel=True)
                pad_y += item["item"].size[1]
            elif item["type"] == "ListBox" :
                item["item"] = ListBox(self.game,
                                    [ self.mainbox.x + (self.mainbox.width// 10)  , self.mainbox.y + pad_y ],
                                        [(self.mainbox.width * 8) //10 , self.mainbox.height - (pad_y - pad_y_init) - self.mainboxitems["User Input"]["item"].size[1] ],
                                        item["list"], sel=True
                                       )
                item["item"].curr_sel = -1
                pad_y += self.mainboxitems["User Input"]["item"].size[1]

    def on_next_scene(self) :
        import importlib
        sceneLib = importlib.import_module(str(self.next_scene))
        loadedScene = getattr(sceneLib, "Scene")
        self.game.scene = loadedScene(self.game)


    def kill(self) :
        self.game.subscenes.pop(self.subscene_index) 

    def action_confirmed(self) :
                    self.game.user = self.mainboxitems["User Input"]["item"].text
                    from utils.savestate import create_user
                    create_user(self.game.user)
                    if self.next_scene :
                        self.on_next_scene()
                    self.kill()


    def update_inputbox(self) :
                self.mainboxitems["User Input"]["item"].text = self.mainboxitems["User List"]["item"].sel_text
                self.mainboxitems["User Input"]["item"].d_i = [0, 
                                        min( 
                    len(self.mainboxitems["User Input"]["item"].text) ,
                    (self.mainboxitems["User Input"]["item"].rect.width // self.mainboxitems["User Input"]["item"].font.size("A")[0]) - 1
                                            )]
                self.mainboxitems["User Input"]["item"].curpos = self.mainboxitems["User Input"]["item"].d_i[1]
    

    def default_handle_event(self,event) :
        if event.type == pygame.MOUSEBUTTONUP :
            if event.button == 1 :
                self.update_inputbox()

        if event.type == pygame.KEYDOWN :
            if (event.key == pygame.K_ESCAPE):
                self.kill()

            if (event.key == pygame.K_RETURN):
                if self.mainboxitems["User Input"]["item"].text :
                    self.action_confirmed()

        for item in self.mainboxitems :
            if ("item" in item) and (item["item"].sel) :
                item["item"].handle_event(event)
 
        if event.type == pygame.KEYDOWN :
            if (event.key in [pygame.K_UP,pygame.K_DOWN]):
                self.update_inputbox()
                

    def handle_event(self,event) :
        self.default_handle_event(event)

    def handle_keypress(self) :
        pass

 
    def on_update(self,delta_time) :
        pass


    def on_draw(self) :
        self.rendered_title.on_draw()
        self.game.screen.blit(
                self.background,
                (self.mainbox.x,self.mainbox.y)
                )
        pygame.draw.rect(
                self.game.screen,
            self.mainbox_color,
            self.mainbox,
            5
            )
        for item in self.mainboxitems :
            if "item" in item :
                item["item"].on_draw()
   



import pygame
from utils.gui_elements import namecallableList , InputBox

class Scene() :
    def __init__ (self, game , enlisted_users, next_scene=None) :
        self.game = game
        self.subscene_index = len(game.subscenes)
        self.enlisted_users = enlisted_users
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
        self.mainboxitems = namecallableList([
            { "name" : "User Input",
                "type" : "InputBox",

                }

            ])
        self.init_menuitems()


    def init_menuitems(self) :
        for item in self.mainboxitems :
            if item["type"] == "InputBox" :
                item["item"] = InputBox(self.game,
                                        [ self.mainbox.x + (self.mainbox.width// 10)  , self.mainbox.y + 10 ],
                                        [(self.mainbox.width * 8) //10 , "doesn't matter" ],
                                        font_size=48)

    def on_next_scene(self) :
        import importlib
        sceneLib = importlib.import_module(str(self.next_scene))
        loadedScene = getattr(sceneLib, "Scene")
        self.game.scene = loadedScene(self.game)


    def kill(self) :
        self.game.subscenes.pop(self.subscene_index) 

    def default_handle_event(self,event) :
        if event.type == pygame.KEYDOWN :
            if (event.key == pygame.K_ESCAPE):
                self.kill()

            if (event.key == pygame.K_RETURN) and (self.mainboxitems["User Input"]["item"].sel):
                if self.mainboxitems["User Input"]["item"].full_text :
                    self.game.user = self.mainboxitems["User Input"]["item"].full_text
                    self.on_next_scene()
                    self.kill()

        for item in self.mainboxitems :
            if ("item" in item) and (item["item"].sel) :
                item["item"].handle_event(event)

    def handle_event(self,event) :
        self.default_handle_event(event)

    def handle_keypress(self) :
        pass

 
    def on_update(self,delta_time) :
        pass


    def on_draw(self) :
        pygame.draw.rect(
                self.game.screen,
            self.mainbox_color,
            self.mainbox,
            5
            )
        for item in self.mainboxitems :
            if "item" in item :
                item["item"].on_draw()
   



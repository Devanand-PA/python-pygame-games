import arcade

# Screen settings
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
SCREEN_TITLE = "Basic Arcade Game"



class MyGame(arcade.Window):
    def __init__(self):
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
        from menus.welcome_screen import Scene
        self.scene = Scene(self)



    def on_draw(self):
        self.clear()
        self.scene.on_draw()


    def on_key_press(self, key, modifiers):
        self.scene.on_key_press(key,modifiers)

    def on_key_release(self, key, modifiers):
        self.scene.on_key_release(key,modifiers)

    def on_update(self, delta_time):
        self.scene.on_update(delta_time)


if __name__ == "__main__":
    game = MyGame()
    arcade.run()

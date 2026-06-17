import arcade
class Scene() :
    def __init__(self,game) :
        self.game = game

    def on_draw(self) :
        arcade.draw_rect_outline(
            arcade.XYWH(400,400,100,100),
            color=(80,120,20),
            border_width=5,
            tilt_angle=1)
        


    def on_key_press(self, key, modifiers):
        pass
    
    def on_key_release(self, key, modifiers):
        pass

    def on_update(self, delta_time):
        pass

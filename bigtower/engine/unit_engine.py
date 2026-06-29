import numpy as np
class MobUnit() :
    def __init__(self,game,player,coords,size) :
        self.game = game
        self.hp = 0
        self.coords = coords
        self.size = size
        self.player = player
        self.speed = 0
        self.range = 0
        self.cooldown = 0
        self.cooldown_time = 10000 # 10 seconds
    
    def init_unit(self) :
        if self.game.scene_type == "game" :
            self.game.unit_array[self.player] = self.game.unit_array[self.player].append(np.array([self.coords,self.size,self.speed,self.range,self.cooldown]))
            self.index = len(self.game.unit_array[self.player]) - 1
            self.game.units.append(self)

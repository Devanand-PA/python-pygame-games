import pygame
import random

class Buff :
    def __init__(self,game,parent_scene) :
        self.game = game
        self.radius = 10
        self.hitbox =  pygame.Rect(0,0,
                        2*self.radius,
                        2*self.radius,
                        )
        self.parent_scene = parent_scene
        self.hitbox.center = (random.randint(0, self.game.screen_size[0]) , 0) 
        self.buff = random.choice(["Fireball","Extraball"])
        if self.buff == "Extraball" :
            self.color = (0,200,0)
        elif self.buff == "Fireball" :
            self.color = (200,0,0)

        self.fall_speed = 300  # pixels per second


    def handle_keypress(self) :
        pass



    def update(self,dt=None) :
        if dt is None :
            dt = 1/60
        self.hitbox.y += self.fall_speed * dt

        

    
    def draw(self) :
        pygame.draw.circle(self.game.screen,
                           self.color,
                           self.hitbox.center,
                           self.radius)



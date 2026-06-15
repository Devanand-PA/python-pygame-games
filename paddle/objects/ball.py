import pygame
import math
import random

class Ball :
    def __init__(self,game,parent_scene,dt) :
        self.game = game
        self.radius = 10
        self.hitbox =  pygame.Rect(0,0,
                        2*self.radius,
                        2*self.radius,
                        )
        self.parent_scene = parent_scene
        self.hitbox.center = (random.randint(0, self.game.screen_size[0]) , 0) 
        self.color = (200,200,200)
        self.vel = [0,0]



        self.delta_t = dt  # seconds
        self.initialize_ball()
        self.fireball = False
        self.fireball_timer = 0
        self.gravity_enabled = True



    def normalize_speed(self):
        vx, vy = self.vel
    
        length = math.hypot(vx, vy)
    
        if length == 0:
            return
    
        scale = self.speed / length
    
        self.vel[0] = vx * scale
        self.vel[1] = vy * scale


    def handle_keypress(self) :
        pass

    def handle_gravity(self) :
        self.vel[1] += float(self.gravity * self.delta_t) # gravity

    def initialize_ball(self) :
        if self.game.difficulty_level in [None, "Easy"] :
            self.vel = [random.randint(-10,10), random.randint(1,10)]
            self.speed = 500
            self.normalize_speed()
            self.gravity = 40

        elif self.game.difficulty_level == "Normal" :
            self.vel = [random.randint(-20,20), random.randint(1,20)]
            self.speed = 750
            self.normalize_speed()
            self.gravity = 98

        elif self.game.difficulty_level == "Hard" :
            self.vel = [random.randint(-30,30), random.randint(1,30)]
            self.speed = 1000
            self.normalize_speed()
            self.gravity = 98

        elif self.game.difficulty_level == "Asian" :
            self.vel = [random.randint(-50,50), random.randint(1,50)]
            self.speed = 1250
            self.normalize_speed()
            self.gravity = 300

        elif self.game.difficulty_level == "Indian" :
            self.vel = [random.randint(-60,60), random.randint(1,60)]
            self.speed = 1500
            self.normalize_speed()
            self.gravity = 400


    def update(self,dt) :
        if (self.hitbox.x < 0) :
            self.vel[0] = abs(self.vel[0] )

        elif (self.hitbox.x > (self.game.screen_size[0] - self.hitbox.width) ) :
            self.vel[0] = -1*abs(self.vel[0] )

        self.delta_t = dt  # seconds


        if self.hitbox.colliderect(self.parent_scene.paddle.hitbox) :
            self.vel[1] = -1 * abs(self.vel[1]) + random.randint(-1,1)
            self.vel[0] += random.randint(-1,1)
        
        if self.gravity_enabled :
            self.handle_gravity()
        
        if self.hitbox.y < 0 :
            self.vel[1] = abs(self.vel[1])

        if self.game.difficulty_level in ["Indian" , "Asian"] :
                self.vel[0] += random.randint(-10,10)
                self.vel[1] += random.randint(-10,10)

        if not self.gravity_enabled :
            self.normalize_speed()
        self.hitbox.x += self.vel[0]*self.delta_t
        self.hitbox.y += self.vel[1]*self.delta_t

        if self.fireball_timer > 0 :
            import time
            if ( time.perf_counter() - self.fireball_timer ) > 10 :
                self.fireball = False
                self.fireball_timer = 0
                self.color = (200,200,200)
        

    
    def draw(self) :
        pygame.draw.circle(self.game.screen,
                           self.color,
                           self.hitbox.center,
                           self.radius)



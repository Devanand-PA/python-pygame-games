import pygame
import random

class Ball :
    def __init__(self,game,parent_scene) :
        self.game = game
        self.radius = 10
        self.hitbox =  pygame.Rect(0,0,
                        2*self.radius,
                        2*self.radius,
                        )
        self.parent_scene = parent_scene
        self.hitbox.center = (random.randint(0, self.game.screen_size[0]) , 0) 
        self.color = (200,200,200)

        print(self.game.difficulty_level)


        self.delta_t = self.game.clock.tick(60) / 1000.0  # seconds
        self.initialize_ball()
        self.fireball = False
        self.fireball_timer = 0

    def normalize_speed(self) :
        self.vel = [ (self.speed*self.vel[0])/( ((self.vel[1]**2)  + (self.vel[0]**2))**(1/2) ) ,
                     (self.speed*self.vel[1])/( ((self.vel[1]**2)  + (self.vel[0]**2))**(1/2) ) ]

    def handle_keypress(self) :
        pass

    def handle_gravity(self) :
        self.vel[1] += self.gravity * self.delta_t # gravity

    def initialize_ball(self) :
        if self.game.difficulty_level in [None, "Easy"] :
            self.vel = [random.randint(-10,10), random.randint(1,10)]
            self.speed = 20
            self.normalize_speed()
            self.gravity = 4
            self.gravity_enabled = True

        elif self.game.difficulty_level == "Normal" :
            self.vel = [random.randint(-20,20), random.randint(1,20)]
            self.speed = 25
            self.normalize_speed()
            self.gravity = 9.8
            self.gravity_enabled = True

        elif self.game.difficulty_level == "Hard" :
            self.vel = [random.randint(-30,30), random.randint(1,30)]
            self.speed = 30
            self.normalize_speed()
            self.gravity = 9.8
            self.gravity_enabled = True

        elif self.game.difficulty_level == "Asian" :
            self.vel = [random.randint(-50,50), random.randint(1,50)]
            self.speed = 40
            self.normalize_speed()
            self.gravity = 30
            self.gravity_enabled = True

        elif self.game.difficulty_level == "Indian" :
            self.vel = [random.randint(-60,60), random.randint(1,60)]
            self.speed = 60
            self.normalize_speed()
            self.gravity = 40
            self.gravity_enabled = True


    def update(self) :
        if (self.hitbox.x < 0) :
            self.vel[0] = abs(self.vel[0] )

        elif (self.hitbox.x > (self.game.screen_size[0] - self.hitbox.width) ) :
            self.vel[0] = -1*abs(self.vel[0] )

        self.delta_t = self.game.clock.tick(60) / 1000.0  # seconds


        if self.hitbox.colliderect(self.parent_scene.paddle.hitbox) :
            self.vel[1] = -1 * abs(self.vel[1]) + random.randint(-1,1)
            self.vel[0] += random.randint(-1,1)
        
        if self.gravity_enabled :
            self.delta_t = self.game.clock.tick(60) / 1000.0  # handle_gravity()
            self.handle_gravity()
        
        if self.hitbox.y < 0 :
            self.vel[1] = abs(self.vel[1])

        if self.game.difficulty_level == "Indian" :
                self.vel[0] += random.randint(-10,10)
                self.vel[1] += random.randint(-10,10)
        self.normalize_speed()
        self.hitbox.x += self.vel[0]
        self.hitbox.y += self.vel[1]

        if self.fireball_timer > 0 :
            import time
            if ( self.fireball_timer - time.perf_counter() ) > 10 :
                self.fireball = False
                self.fireball_timer = 0
                self.color = (200,200,200)
        

    
    def draw(self) :
        pygame.draw.circle(self.game.screen,
                           self.color,
                           self.hitbox.center,
                           self.radius)



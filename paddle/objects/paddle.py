import pygame

class Paddle :
    def __init__(self,game) :
        self.game = game
        self.color = (100,50,100)
        self.hitbox =  pygame.Rect(0,0,
                        200,
                        40
                        )
        self.hitbox.center = (self.game.screen_size[0] // 2 , self.game.screen_size[1] - self.hitbox.height)
   
    def update(self) :
       pass
   
    def handle_keypress(self) :
        pressed_keys = pygame.key.get_pressed()

        if pressed_keys[pygame.K_d] or pressed_keys[pygame.K_RIGHT]:
            self.hitbox.x += self.hitbox.width // 10
            if self.hitbox.x > self.game.screen_size[0] - self.hitbox.width :
                self.hitbox.x = self.game.screen_size[0] - self.hitbox.width

        if pressed_keys[pygame.K_a] or pressed_keys[pygame.K_LEFT]:
            self.hitbox.x -= self.hitbox.width // 10
            if self.hitbox.x < 0 :
                self.hitbox.x = 0

        if self.game.difficulty_level == "Indian" :
            import random
            cointoss = random.randint(0,1000)
            if cointoss > 990 :
                self.hitbox.x = random.randint(0,self.game.screen_size[0] - self.hitbox.width)

    

    def draw(self) :
        pygame.draw.rect(self.game.screen,
                         self.color,
                         self.hitbox
                         )



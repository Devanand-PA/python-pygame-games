import pygame
import random

class Unit() :
    def __init__(self,game,coords,damage):
        self.coords = coords
        self.damage = damage
        self.game = game
        pass

class Tower(Unit) :
    def __init__(self,game,coords,damage) :
        super().__init__(game,coords,damage)
        self.rect = pygame.Rect(coords[0],coords[1],10,10)


    def on_draw(self) :
        pygame.draw.rect(self.game.screen,
                         (0,0,200),self.rect
                )

class Mob(Unit) :
    def __init__(self,game,coords,damage,speed) :
        super().__init__(game,coords,damage)
        self.speed = speed

    def on_draw(self) :
        pygame.draw.circle(self.game.screen,
                           (200,0,0), self.coords,
                           5
                           )


pygame.init()

class Game() :
    def __init__(self) :
        self.screen = pygame.display.set_mode(
        [600,600]
        )
        self.running = True
        self.towers = []
        self.mobs = []
        for i in range(10) : 
            self.towers.append(
                    Tower(self,[random.randint(0,600) for i in range(2)],10)
                    )
            self.mobs.append(
                    Mob(self,[random.randint(0,600) for i in range(2)],10,2)
                    )

    def draw_units(self,units) :
        for unit in units :
            unit.on_draw()
   
    def on_draw(self) :
            self.screen.fill((0,0,0))
            self.draw_units(self.towers)
            self.draw_units(self.mobs)
    
    def handle_event(self,event) :
        if event.type == pygame.KEYDOWN :
            pass
        if event.type == pygame.QUIT :
            self.running = False

    def run(self) :
        while self.running :
            for event in pygame.event.get() :
                self.handle_event(event)
            self.on_draw()
            pygame.display.flip()


game = Game()
game.run()

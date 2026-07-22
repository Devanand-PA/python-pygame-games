import pygame
import numpy as np
import random
from units import *



def tint_surface(surface, color):
    # 1. Create a copy of the original surface to avoid altering the asset permanently
    tinted_surface = surface.copy()
    
    # 2. Create a solid color surface of the exact same size
    color_surface = pygame.Surface(surface.get_size()).convert_alpha()
    color_surface.fill(color)
    
    # 3. Blend the solid color with your image using BLEND_RGBA_MULT
    # This multiplies the color channels while maintaining the transparency mask
    tinted_surface.blit(color_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    
    return tinted_surface


class Player() :
    def __init__(self) :
        self.units = []
        self.group = ""

class Game() :
    def __init__(self) :
        # Set up players
        self.Players = [ Player() for i in range(2) ]
        self.Player_Groups = [
                [ self.Players[0] ],
                [ self.Players[1] ]
                ]

        for group in range(len(self.Player_Groups)) :
                for player in self.Player_Groups[group] :
                        player.group = "group-"+str(group)
        #===================


        self.screen_res = [600,600]
        self.map_size = [2000,2000]
        self.screen_topleft = np.array([0,0],dtype=int)
        self.screen = pygame.display.set_mode(
        self.screen_res
        )
        self.clock = pygame.time.Clock()
        self.tower_sprite = pygame.image.load("tower_1.png")
        self.tower_sprite2 = tint_surface(self.tower_sprite,(100,0,0))
        self.running = True
        from engine import Engine
        self.engine = Engine(self)
        self.towers = []
        self.mobs = []
        self.mobtypes = [Mob,Mob2,Mob3]
        self.towertypes = [Tower, Tower2]
        for i in range(100) : 
            self.towers.append(
                    random.choice(self.towertypes)(self.engine,self.Players[0],[random.randint(100,self.map_size[i]-101) for i in range(2)],10)
                    )

            self.mobs.append(
                                random.choice(self.mobtypes)(self.engine,self.Players[1],[random.randint(50,self.map_size[i]-51) for i in range(2)],10,self.engine.MOB_DEFAULT_SPEED)
                    )


            

    def draw_lattice(self) :
        for i in self.engine.all_cells :
            for j in i :
                # pygame.draw.circle(self.screen,
                #                    (0,200,0),
                #                    j.start_coords-self.screen_topleft,
                #                    4
                #                    )
                # pygame.draw.circle(self.screen,
                #                    (0,200,0),
                #                    j.end_coords-self.screen_topleft,
                #                    4
                #                    )
                pygame.draw.line(self.screen,(0,200,0),
                            list(j.start_coords-self.screen_topleft),
                            list([j.start_coords[0],j.end_coords[1]]-self.screen_topleft),
                                 )
                pygame.draw.line(self.screen,(0,200,0),
                            list([j.start_coords[0],j.end_coords[1]]-self.screen_topleft),
                            list(j.end_coords-self.screen_topleft),
                                 )



    def draw_units(self) :
        units_drawn = 0
        for cell in self.engine.in_cells :
            for unit in cell.units :
                    unit.on_draw()
                    units_drawn += 1
        # print("drawn",units_drawn,"units")
   
    def on_draw(self) :
            self.screen.fill((0,0,0))
            self.draw_units()
            self.draw_lattice()

    def handle_keypress(self) :
        pressed_keys = pygame.key.get_pressed()

        if pressed_keys[pygame.K_a] or pressed_keys[pygame.K_LEFT] :
            if self.screen_topleft[0] > self.engine.DEFAULT_SCROLL_SPEED :
                self.screen_topleft[0] -= self.engine.DEFAULT_SCROLL_SPEED
            else :
                self.screen_topleft[0] = 0
        elif pressed_keys[pygame.K_d] or pressed_keys[pygame.K_RIGHT] :
            if self.screen_topleft[0] < (self.map_size[0]-self.engine.DEFAULT_SCROLL_SPEED-self.screen_res[0]) :
                self.screen_topleft[0] += self.engine.DEFAULT_SCROLL_SPEED
            else :
                self.screen_topleft[0] = self.map_size[0] - self.screen_res[0]

        if pressed_keys[pygame.K_w] or pressed_keys[pygame.K_UP] :
            if self.screen_topleft[1] > self.engine.DEFAULT_SCROLL_SPEED :
                self.screen_topleft[1] -= self.engine.DEFAULT_SCROLL_SPEED
            else :
                self.screen_topleft[1] = 0
        elif pressed_keys[pygame.K_s] or pressed_keys[pygame.K_DOWN] :
            if self.screen_topleft[1] < (self.map_size[1]-self.engine.DEFAULT_SCROLL_SPEED-self.screen_res[1]) :
                self.screen_topleft[1] += self.engine.DEFAULT_SCROLL_SPEED
            else :
                self.screen_topleft[1] = self.map_size[1] - self.screen_res[1]


        # if any(pressed_keys) :
        #     print(self.screen_topleft)

    
    def handle_event(self,event) :
        if event.type == pygame.KEYDOWN :
            pass
        if event.type == pygame.QUIT :
            self.running = False

        if event.type == pygame.MOUSEBUTTONUP :
            if event.button == 1 :
                self.mobs.append(
                                random.choice(self.mobtypes)(self.engine,self.Players[1],list(self.screen_topleft + event.pos),10,self.engine.MOB_DEFAULT_SPEED)
                    )
            elif event.button == 3 :
                click_tower = True
                for tower in self.towers :
                    if tower.rect.collidepoint(event.pos) :
                        click_tower = False
                if click_tower :
                    self.towers.append(
                    random.choice(self.towertypes)(self.engine,self.Players[0],list(self.screen_topleft + event.pos),10)
                    )
                else :
                    print("Unable to create tower")




    def run(self) :
        self.delta_time = self.clock.tick(60) / 1000.0
        self.main_target = random.choice(self.towers)
        while self.running :
            self.delta_time = self.clock.tick(60) / 1000.0
            for event in pygame.event.get() :
                self.handle_event(event)
            self.handle_keypress()
            self.engine.on_update()
            self.on_draw()
            pygame.display.flip()


game = Game()
game.run()

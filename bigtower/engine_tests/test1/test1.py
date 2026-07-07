import pygame
import random
import numpy as np

class Unit() :
    def __init__(self,game,coords,damage):
        self.target = None
        self.coords = np.array(coords,dtype=np.float64)
        self.damage = damage
        self.game = game
        self.cell_x , self.cell_y = self.put_in_cell()
    
    def put_in_cell(self) :
        cell_x = int(np.ceil( ( self.coords[0] * (len(self.game.divs[0])) ) //
                  self.game.screen_res[0] ) - 1)

        cell_y = int(np.ceil( ( self.coords[1] * (len(self.game.divs[1])) ) //
                  self.game.screen_res[1] ) - 1)
        self.game.all_cells[cell_x][cell_y].units.append(self)
        return cell_x , cell_y

    def remove_from_cell(self) :
        cell_coords_start = self.game.all_cells[self.cell_x][self.cell_y].start_coords
        cell_coords_end = self.game.all_cells[self.cell_x][self.cell_y].end_coords
        if ( cell_coords_start[0] > self.coords[0] >= cell_coords_end[0] ) and \
            ( cell_coords_start[1] > self.coords[1] >= cell_coords_end[1] ) :
                return False
        else :
            for i,unit in enumerate(self.game.all_cells[self.cell_x][self.cell_y].units) :
                if unit is self :
                    del self.game.all_cells[self.cell_x][self.cell_y].units[i]
                    break

            return True

    def choose_target(self) :
        target_found = False
        for o_range in range(max(  len(self.game.divs[0]) , len(self.game.divs[1])  )) :
            for i_range in range(o_range) :
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
        self.vel =  np.array([0,0],dtype=np.float64)

    def on_draw(self) :
        pygame.draw.circle(self.game.screen,
                           (200,0,0), list(self.coords),
                           5
                           )
    def path_to(self,target) :
        target_distance = np.linalg.norm(target.coords - self.coords)
        if target_distance : 
            self.vel = ( (self.speed * (target.coords - self.coords)) / target_distance )
        else :
             self.vel = np.array([0,0])

        # print(f"\033[32m {self.vel} \033[0m")
        # if not self.vel.all() :
        #     self.vel = np.array([0,0])
        self.coords += self.vel
        

class Cell() :
    def __init__(self,start_coords=[0,0],end_coords=[0,0]) :
        self.units = []
        self.start_coords = np.array(start_coords)
        self.end_coords = np.array(end_coords)

pygame.init()

class Game() :
    def __init__(self) :
        self.screen_res = [600,600]
        self.screen = pygame.display.set_mode(
        self.screen_res
        )
        self.divide_areas()
        self.running = True
        self.towers = []
        self.mobs = []
        for i in range(100) : 
            self.towers.append(
                    Tower(self,[random.randint(100,500) for i in range(2)],10)
                    )
            self.mobs.append(
                    Mob(self,[random.randint(0,600) for i in range(2)],10,1)
                    )

    def draw_lattice(self) :
        for i in self.all_cells :
            for j in i :
                pygame.draw.circle(self.screen,
                                   (0,200,0),
                                   j.start_coords,
                                   10
                                   )
                pygame.draw.circle(self.screen,
                                   (0,200,0),
                                   j.end_coords,
                                   10
                                   )

    def divide_areas(self) :
        self.all_cells = []
        divs_h = np.linspace(0 , self.screen_res[0] , self.screen_res[0] // 100)
        divs_v = np.linspace( 0 , self.screen_res[1] , self.screen_res[1] // 100)
        self.divs = [ divs_h , divs_v ]
        for i in range(len(divs_h)-1) : # The last entry in divs_h is the right hand edge
            self.all_cells.append([])
            for j in range(len(divs_v)-1) :
                self.all_cells[i].append(
                    Cell(
                        start_coords=[divs_h[i],divs_v[j]],
                        end_coords=[divs_h[i+1],divs_v[j+1]]
                        ))


    def draw_units(self,units) :
        for unit in units :
            unit.on_draw()
   
    def on_draw(self) :
            self.screen.fill((0,0,0))
            self.draw_units(self.towers)
            self.draw_units(self.mobs)
            self.draw_lattice()
    
    def handle_event(self,event) :
        if event.type == pygame.KEYDOWN :
            pass
        if event.type == pygame.QUIT :
            self.running = False
    def on_update(self) :
        for mob in self.mobs :
            if not mob.target :
                mob.path_to(self.main_target)
            if mob.remove_from_cell() :
                mob.cell_x , mob.cell_y = mob.put_in_cell()
            print(f"\033[31m {mob.vel} , \033[30;42mCell : [{mob.cell_x}] [{mob.cell_y}]  \033[0m")

    def run(self) :
        self.main_target = random.choice(self.towers)
        while self.running :
            for event in pygame.event.get() :
                self.handle_event(event)
            self.on_update()
            self.on_draw()
            pygame.display.flip()


game = Game()
game.run()

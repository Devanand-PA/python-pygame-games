import pygame
import random
import numpy as np

DEFAULT_SCROLL_SPEED = 10
MOB_DEFAULT_SPEED = 50
class Unit() :
    def __init__(self,game,coords,damage):
        self.target = None
        self.coords = np.array(coords,dtype=np.float64)
        self.damage = damage
        self.game = game
        self.cell_x , self.cell_y = self.put_in_cell()
    
    def put_in_cell(self) :
        num_cells_x = len(self.game.all_cells)
        num_cells_y = len(self.game.all_cells[0]) if num_cells_x > 0 else 0
        
        cell_x = int(self.coords[0] * num_cells_x // self.game.map_size[0])
        cell_y = int(self.coords[1] * num_cells_y // self.game.map_size[1])
        cell_x = max(0, min(cell_x, num_cells_x - 1))
        cell_y = max(0, min(cell_y, num_cells_y - 1))

        # print("==================================")
        # print(cell_x , cell_y)
        # print(len(self.game.all_cells))
        # print("==================================")
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
        target = None
        target_distance = sum(self.game.map_size) # Set initially to an unreachable distance, practically infinity
        for max_range in range(max(  len(self.game.divs[0]) , len(self.game.divs[1])  )) :

            if target_found :
                    break
            for curr_row_rel , curr_row in enumerate(               #this is just a[b-c : b+c]
                self.game.all_cells[
                max(0,(self.cell_x - max_range)) :                  # I don't want this to go below 0
                min(len(self.game.all_cells),(self.cell_x + max_range)) # I don't want this to go beyond range
                ]) :

                        for curr_cell_rel , curr_cell in enumerate( # The reason I am using enumerate is just in case I need the relative index at some point
                            curr_row[
                            max(0,(self.cell_y - max_range)) :                  # I don't want this to go below 0
                            min(len(curr_row),(self.cell_y + max_range)) # I don't want this to go beyond range
                            ]):
                                for unit_idx , unit_considered in enumerate(curr_cell.units) :
                                    if unit_considered in self.game.towers :
                                        if ( curr_dist:=  np.linalg.norm(unit_considered.coords - self.coords)) < target_distance:
                                            target_distance = curr_dist
                                            target = unit_considered
                                            target_found = True
        return target


class Tower(Unit) :
    def __init__(self,game,coords,damage) :
        super().__init__(game,coords,damage)
        self.rect = pygame.Rect(coords[0],coords[1],10,10)
        self.rect.width , self.rect.height = self.game.tower_sprite.get_size()
        self.coords = self.rect.center
        self.apparent_rect = self.rect.copy()


    def on_draw(self) :
        self.apparent_rect.x = self.rect.x - self.game.screen_topleft[0]
        self.apparent_rect.y = self.rect.y - self.game.screen_topleft[1]
        # pygame.draw.rect(self.game.screen,
        #                  (0,0,200),self.apparent_rect
        #         )
        self.game.screen.blit(self.game.tower_sprite,self.apparent_rect)

class Mob(Unit) :
    def __init__(self,game,coords,damage,speed) :
        super().__init__(game,coords,damage)
        self.speed = speed
        self.vel =  np.array([0,0],dtype=np.float64)

    def on_draw(self) :
        pygame.draw.circle(self.game.screen,
                           (200,0,0), list(self.coords-self.game.screen_topleft),
                           5
                           )
    def path_to(self,target) :
        target_distance = np.linalg.norm(target.coords - self.coords)
        if (target_distance > (max(target.rect.width, target.rect.height)/2) ) : 
            self.vel = ( (self.speed * (target.coords - self.coords)) / target_distance )
        else :
             self.vel = np.array([0,0])

        # print(f"\033[32m {self.vel} \033[0m")
        # if not self.vel.all() :
        #     self.vel = np.array([0,0])
        self.coords += self.vel*self.game.delta_time
        

class Cell() :
    def __init__(self,start_coords=[0,0],end_coords=[0,0]) :
        self.units = []
        self.start_coords = np.array(start_coords)
        self.end_coords = np.array(end_coords)

pygame.init()

class Game() :
    def __init__(self) :
        self.screen_res = [600,600]
        self.map_size = [2000,2000]
        self.screen_topleft = np.array([0,0],dtype=int)
        self.screen = pygame.display.set_mode(
        self.screen_res
        )
        self.divide_areas()
        self.tower_sprite = pygame.image.load("tower_1.png")
        self.running = True
        self.towers = []
        self.clock = pygame.time.Clock()
        self.mobs = []
        for i in range(100) : 
            self.towers.append(
                    Tower(self,[random.randint(100,self.map_size[i]-101) for i in range(2)],10)
                    )
            self.mobs.append(
                    Mob(self,[random.randint(50,self.map_size[i]-51) for i in range(2)],10,MOB_DEFAULT_SPEED)
                    )


            

    def draw_lattice(self) :
        for i in self.all_cells :
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

    def divide_areas(self) :
        self.all_cells = []
        self.cell_size = [50,50]
        divs_h = np.linspace( 0 , self.map_size[0] , self.map_size[0] // (self.cell_size[0] + 1) )
        divs_v = np.linspace( 0 , self.map_size[1] , self.map_size[1] // (self.cell_size[1] + 1) )
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
        units_drawn = 0
        for cell in self.in_cells :
            for unit in cell.units :
                    unit.on_draw()
                    units_drawn += 1
        # print("drawn",units_drawn,"units")
   
    def on_draw(self) :
            self.screen.fill((0,0,0))
            self.draw_units(self.towers)
            self.draw_units(self.mobs)
            self.draw_lattice()

    def handle_keypress(self) :
        pressed_keys = pygame.key.get_pressed()

        if pressed_keys[pygame.K_a] or pressed_keys[pygame.K_LEFT] :
            if self.screen_topleft[0] > DEFAULT_SCROLL_SPEED :
                self.screen_topleft[0] -= DEFAULT_SCROLL_SPEED
            else :
                self.screen_topleft[0] = 0
        elif pressed_keys[pygame.K_d] or pressed_keys[pygame.K_RIGHT] :
            if self.screen_topleft[0] < (self.map_size[0]-DEFAULT_SCROLL_SPEED-self.screen_res[0]) :
                self.screen_topleft[0] += DEFAULT_SCROLL_SPEED
            else :
                self.screen_topleft[0] = self.map_size[0] - self.screen_res[0]

        if pressed_keys[pygame.K_w] or pressed_keys[pygame.K_UP] :
            if self.screen_topleft[1] > DEFAULT_SCROLL_SPEED :
                self.screen_topleft[1] -= DEFAULT_SCROLL_SPEED
            else :
                self.screen_topleft[1] = 0
        elif pressed_keys[pygame.K_s] or pressed_keys[pygame.K_DOWN] :
            if self.screen_topleft[1] < (self.map_size[1]-DEFAULT_SCROLL_SPEED-self.screen_res[1]) :
                self.screen_topleft[1] += DEFAULT_SCROLL_SPEED
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
                    Mob(self,list(self.screen_topleft + event.pos),10,MOB_DEFAULT_SPEED)
                    )
            elif event.button == 3 :
                self.towers.append(
                    Tower(self,list(self.screen_topleft + event.pos),10)
                    )



    def on_update(self) :
        cell_vis_idx = [ [(self.screen_topleft[0] // (self.cell_size[0] + 1)) ,((self.screen_topleft[0] + self.screen_res[0])// (self.cell_size[0] + 1)) ] ,
                        [(self.screen_topleft[1] // (self.cell_size[1] + 1)) ,((self.screen_topleft[1] + self.screen_res[1])// (self.cell_size[1] + 1))  ]]
        self.in_cells = []
        for i in range(max(0,cell_vis_idx[0][0]) , min(cell_vis_idx[0][1] , len(self.all_cells) - 1)+1 ) :
            for j in range(max(0,cell_vis_idx[1][0]) , min(cell_vis_idx[1][1] , len(self.all_cells[0]) - 1)+1 ) :
                self.in_cells.append(self.all_cells[i][j])


        for mob in self.mobs :
            if not mob.target :
                mob.target = mob.choose_target() or self.main_target
            mob.path_to(mob.target)
            # print("pathing",mob,"to",mob.target)
            if mob.remove_from_cell() :
                mob.cell_x , mob.cell_y = mob.put_in_cell()
            # print(f"\033[31m {mob.vel} , \033[30;42mCell : [{mob.cell_x}] [{mob.cell_y}]  \033[0m")

    def run(self) :
        self.delta_time = self.clock.tick(60) / 1000.0
        self.main_target = random.choice(self.towers)
        while self.running :
            for event in pygame.event.get() :
                self.handle_event(event)
            self.handle_keypress()
            self.on_update()
            self.on_draw()
            pygame.display.flip()


game = Game()
game.run()

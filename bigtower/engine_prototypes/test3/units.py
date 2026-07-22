import numpy as np
import pygame


class Unit() :
    def __init__(self,engine,player,coords,damage):
        self.target = None
        self.player = player
        player.units.append(self)
        self.coords = np.array(coords,dtype=np.float64)
        self.damage = damage
        self.engine = engine
        self.cell_x , self.cell_y = self.put_in_cell()
    
    def put_in_cell(self) :
        num_cells_x = len(self.engine.all_cells)
        num_cells_y = len(self.engine.all_cells[0]) if num_cells_x > 0 else 0
        
        cell_x = int(self.coords[0] * num_cells_x // self.engine.game.map_size[0])
        cell_y = int(self.coords[1] * num_cells_y // self.engine.game.map_size[1])
        cell_x = max(0, min(cell_x, num_cells_x - 1))
        cell_y = max(0, min(cell_y, num_cells_y - 1))

        # print("==================================")
        # print(cell_x , cell_y)
        # print(len(self.engine.all_cells))
        # print("==================================")
        self.engine.all_cells[cell_x][cell_y].units.append(self)
        return cell_x , cell_y

    def remove_from_cell(self) :
        cell_coords_start = self.engine.all_cells[self.cell_x][self.cell_y].start_coords
        cell_coords_end = self.engine.all_cells[self.cell_x][self.cell_y].end_coords
        if ( cell_coords_start[0] > self.coords[0] >= cell_coords_end[0] ) and \
            ( cell_coords_start[1] > self.coords[1] >= cell_coords_end[1] ) :
                return False
        else :
            for i,unit in enumerate(self.engine.all_cells[self.cell_x][self.cell_y].units) :
                if unit is self :
                    del self.engine.all_cells[self.cell_x][self.cell_y].units[i]
                    break

            return True

    def choose_target(self) :
        target_found = False
        target = None
        target_distance = sum(self.engine.game.map_size) # Set initially to an unreachable distance, practically infinity
        for max_range in range(max(  len(self.engine.divs[0]) , len(self.engine.divs[1])  )) :

            if target_found :
                    break
            for curr_row_rel , curr_row in enumerate(               #this is just a[b-c : b+c]
                self.engine.all_cells[
                max(0,(self.cell_x - max_range)) :                  # I don't want this to go below 0
                min(len(self.engine.all_cells),(self.cell_x + max_range)) # I don't want this to go beyond range
                ]) :

                        for curr_cell_rel , curr_cell in enumerate( # The reason I am using enumerate is just in case I need the relative index at some point
                            curr_row[
                            max(0,(self.cell_y - max_range)) :                  # I don't want this to go below 0
                            min(len(curr_row),(self.cell_y + max_range)) # I don't want this to go beyond range
                            ]):
                                for unit_idx , unit_considered in enumerate(curr_cell.units) :
                                    if unit_considered.player.group != self.player.group :
                                        if ( curr_dist:=  np.linalg.norm(unit_considered.coords - self.coords)) < target_distance:
                                            target_distance = curr_dist
                                            target = unit_considered
                                            target_found = True
        return target


class Tower(Unit) :
    def __init__(self,engine,player,coords,damage) :
        super().__init__(engine,player,coords,damage)
        self.rect = pygame.Rect(coords[0],coords[1],10,10)
        self.rect.width , self.rect.height = self.engine.game.tower_sprite.get_size()
        self.coords = self.rect.center
        self.apparent_rect = self.rect.copy()


    def on_draw(self) :
        self.apparent_rect.x = self.rect.x - self.engine.game.screen_topleft[0]
        self.apparent_rect.y = self.rect.y - self.engine.game.screen_topleft[1]
        # pygame.draw.rect(self.engine.screen,
        #                  (0,0,200),self.apparent_rect
        #         )
        self.engine.game.screen.blit(self.engine.game.tower_sprite,self.apparent_rect)

class Mob(Unit) :
    def __init__(self,engine,player,coords,damage,speed) :
        super().__init__(engine,player,coords,damage)
        self.speed = speed
        self.vel =  np.array([0,0],dtype=np.float64)

    def on_draw(self) :
        pygame.draw.circle(self.engine.game.screen,
                           (200,0,0), list(self.coords-self.engine.game.screen_topleft),
                           5
                           )
    def path_to(self,target) :
        target_distance = np.linalg.norm(target.coords - self.coords)
        if (target_distance > (max(target.rect.width, target.rect.height)/2) ) : 
            self.vel = ( (self.speed * (target.coords - self.coords)) / target_distance )
        else :
             self.vel = np.array([0,0])

        return self.vel
        # print(f"\033[32m {self.vel} \033[0m")
        # if not self.vel.all() :
        #     self.vel = np.array([0,0])

class Mob2(Mob) :
    def __init__(self,engine,player,coords,damage,speed) :
        super().__init__(engine,player,coords,damage,speed)
        self.speed = 200
    def on_draw(self) :
        pygame.draw.circle(self.engine.game.screen,
                           (200,200,0), list(self.coords-self.engine.game.screen_topleft),
                           5
                           )


class Mob3(Mob) :
    def __init__(self,engine,player,coords,damage,speed) :
        super().__init__(engine,player,coords,damage,speed)
        self.speed = 20
    def on_draw(self) :
        pygame.draw.circle(self.engine.game.screen,
                           (0,100,50), list(self.coords-self.engine.game.screen_topleft),
                           5
                           )


class Tower2(Tower) :
    def __init__(self,engine,player,coords,damage) :
        super().__init__(engine,player,coords,damage)

    def on_draw(self) :
        self.apparent_rect.x = self.rect.x - self.engine.game.screen_topleft[0]
        self.apparent_rect.y = self.rect.y - self.engine.game.screen_topleft[1]
        # pygame.draw.rect(self.engine.screen,
        #                  (0,0,200),self.apparent_rect
        #         )
        self.engine.game.screen.blit(self.engine.game.tower_sprite2,self.apparent_rect)

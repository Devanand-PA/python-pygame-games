import pygame
import random
import numpy as np

        

class Cell() :
    def __init__(self,start_coords=[0,0],end_coords=[0,0]) :
        self.units = []
        self.start_coords = np.array(start_coords)
        self.end_coords = np.array(end_coords)

pygame.init()


class Engine() :
    def __init__(self,game) :
        self.DEFAULT_SCROLL_SPEED = 10
        self.MOB_DEFAULT_SPEED = 50
        self.game = game
        self.divide_areas()

    def divide_areas(self) :
        self.all_cells = []
        self.cell_size = [50,50]
        divs_h = np.linspace( 0 , self.game.map_size[0] , self.game.map_size[0] // (self.cell_size[0] + 1) )
        divs_v = np.linspace( 0 , self.game.map_size[1] , self.game.map_size[1] // (self.cell_size[1] + 1) )
        self.divs = [ divs_h , divs_v ]
        for i in range(len(divs_h)-1) : # The last entry in divs_h is the right hand edge
            self.all_cells.append([])
            for j in range(len(divs_v)-1) :
                self.all_cells[i].append(
                    Cell(
                        start_coords=[divs_h[i],divs_v[j]],
                        end_coords=[divs_h[i+1],divs_v[j+1]]
                        ))

    def on_update(self) :
        cell_vis_idx = [ [(self.game.screen_topleft[0] // (self.cell_size[0] + 1)) ,((self.game.screen_topleft[0] + self.game.screen_res[0])// (self.cell_size[0] + 1)) ] ,
                        [(self.game.screen_topleft[1] // (self.cell_size[1] + 1)) ,((self.game.screen_topleft[1] + self.game.screen_res[1])// (self.cell_size[1] + 1))  ]]
        self.in_cells = []
        for i in range(max(0,cell_vis_idx[0][0]) , min(cell_vis_idx[0][1] , len(self.all_cells) - 1)+1 ) :
            for j in range(max(0,cell_vis_idx[1][0]) , min(cell_vis_idx[1][1] , len(self.all_cells[0]) - 1)+1 ) :
                self.in_cells.append(self.all_cells[i][j])


        for mob in self.game.mobs :
            if not mob.target :
                mob.target = mob.choose_target() or self.game.main_target

            if (vel := mob.path_to(mob.target) ).any :
                mob.coords +=  vel*self.game.delta_time
            # print("pathing",mob,"to",mob.target)
            if mob.remove_from_cell() :
                mob.cell_x , mob.cell_y = mob.put_in_cell()
            # print(f"\033[31m {mob.vel} , \033[30;42mCell : [{mob.cell_x}] [{mob.cell_y}]  \033[0m")

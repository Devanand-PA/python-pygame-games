import numpy as np
import pygame


class Unit:
    def __init__(self, engine, player, coords, damage):
        self.target = None
        self.player = player
        player.units.append(self)
        self.coords = np.array(coords, dtype=np.float64)
        self.damage = damage
        self.engine = engine
        self.cell_x, self.cell_y = self.put_in_cell()

    def put_in_cell(self):
        cw, ch = self.engine.cell_size
        cell_x = int(self.coords[0] // cw)
        cell_y = int(self.coords[1] // ch)

        cell_x = max(0, min(cell_x, self.engine.cols - 1))
        cell_y = max(0, min(cell_y, self.engine.rows - 1))

        self.engine.all_cells[cell_x][cell_y].units.append(self)
        return cell_x, cell_y

    def remove_from_cell(self):
        cell = self.engine.all_cells[self.cell_x][self.cell_y]
        x0, y0 = cell.start_coords
        x1, y1 = cell.end_coords

        if x0 <= self.coords[0] < x1 and y0 <= self.coords[1] < y1:
            return False

        cell.units.remove(self)
        return True

    def choose_target(self):
        max_r = max(self.engine.cols, self.engine.rows)

        for r in range(max_r + 1):
            best = None
            best_d2 = float("inf")

            for i, j in self.engine.iter_ring_cells(self.cell_x, self.cell_y, r):
                for unit in self.engine.all_cells[i][j].units:
                    if unit.player.group == self.player.group:
                        continue

                    dx = unit.coords[0] - self.coords[0]
                    dy = unit.coords[1] - self.coords[1]
                    d2 = dx * dx + dy * dy

                    if d2 < best_d2:
                        best_d2 = d2
                        best = unit

            if best is not None:
                return best

        return None

class Tower(Unit):
    def __init__(self, engine, player, coords, damage):
        super().__init__(engine, player, coords, damage)

        self.rect = pygame.Rect(coords[0], coords[1], 10, 10)
        self.rect.width, self.rect.height = self.engine.game.tower_sprite.get_size()
        self.coords = np.array(self.rect.center, dtype=np.float64)
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

    def path_to(self, target):
        if target is None:
            self.vel = np.array([0, 0], dtype=np.float64)
            return self.vel

        delta = target.coords - self.coords
        dist = np.hypot(delta[0], delta[1])

        stop_dist = 5
        if hasattr(target, "rect"):
            stop_dist = max(target.rect.width, target.rect.height) / 2

        if dist > stop_dist:
            self.vel = (self.speed * delta) / dist
        else:
            self.vel = np.array([0, 0], dtype=np.float64)

        return self.vel



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

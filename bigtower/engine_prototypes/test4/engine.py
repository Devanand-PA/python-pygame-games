import pygame
import numpy as np


class Cell:
    __slots__ = ("units", "start_coords", "end_coords", "rect")

    def __init__(self, start_coords, end_coords):
        self.units = []
        self.start_coords = np.array(start_coords, dtype=np.float64)
        self.end_coords = np.array(end_coords, dtype=np.float64)
        self.rect = pygame.Rect(
            int(self.start_coords[0]),
            int(self.start_coords[1]),
            int(self.end_coords[0] - self.start_coords[0]),
            int(self.end_coords[1] - self.start_coords[1]),
        )


pygame.init()


class Engine:
    def __init__(self, game):
        self.DEFAULT_SCROLL_SPEED = 10
        self.MOB_DEFAULT_SPEED = 50
        self.game = game
        self.cell_size = [50, 50]
        self.divide_areas()

    def divide_areas(self):
        self.all_cells = []
        cw, ch = self.cell_size
        map_w, map_h = self.game.map_size

        self.cols = (map_w + cw - 1) // cw
        self.rows = (map_h + ch - 1) // ch

        for i in range(self.cols):
            col = []
            x0 = i * cw
            x1 = min((i + 1) * cw, map_w)
            for j in range(self.rows):
                y0 = j * ch
                y1 = min((j + 1) * ch, map_h)
                col.append(Cell([x0, y0], [x1, y1]))
            self.all_cells.append(col)

    def get_visible_cells(self):
        cw, ch = self.cell_size
        left = max(0, int(self.game.screen_topleft[0] // cw))
        right = min(
            self.cols - 1,
            int((self.game.screen_topleft[0] + self.game.screen_res[0]) // cw),
        )
        top = max(0, int(self.game.screen_topleft[1] // ch))
        bottom = min(
            self.rows - 1,
            int((self.game.screen_topleft[1] + self.game.screen_res[1]) // ch),
        )

        cells = []
        for i in range(left, right + 1):
            for j in range(top, bottom + 1):
                cells.append(self.all_cells[i][j])
        return cells

    def iter_ring_cells(self, cx, cy, r):
        """Yield (i, j) cell indices exactly r cells away in Chebyshev distance."""
        if r == 0:
            if 0 <= cx < self.cols and 0 <= cy < self.rows:
                yield cx, cy
            return

        x0 = cx - r
        x1 = cx + r
        y0 = cy - r
        y1 = cy + r

        # top edge
        if 0 <= y0 < self.rows:
            for x in range(max(0, x0), min(self.cols - 1, x1) + 1):
                yield x, y0

        # bottom edge
        if 0 <= y1 < self.rows and y1 != y0:
            for x in range(max(0, x0), min(self.cols - 1, x1) + 1):
                yield x, y1

        # left edge (skip corners)
        if 0 <= x0 < self.cols:
            for y in range(max(0, y0 + 1), min(self.rows - 1, y1 - 1) + 1):
                yield x0, y

        # right edge (skip corners)
        if 0 <= x1 < self.cols and x1 != x0:
            for y in range(max(0, y0 + 1), min(self.rows - 1, y1 - 1) + 1):
                yield x1, y

    def on_update(self):
        self.in_cells = self.get_visible_cells()

        for mob in self.game.mobs:
            if mob.target is None:
                mob.target = mob.choose_target() or self.game.main_target

            vel = mob.path_to(mob.target)
            if np.any(vel):
                mob.coords += vel * self.game.delta_time

            if mob.remove_from_cell():
                mob.cell_x, mob.cell_y = mob.put_in_cell()

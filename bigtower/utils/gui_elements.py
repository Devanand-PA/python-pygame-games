import pygame

class namecallableList:
        def __init__(self, buttons):
            self._list = buttons
            self._dict = {b["name"] : b for b in buttons}

        def __getitem__(self, key):
            if isinstance(key, str):
                return self._dict[key]
            return self._list[key]
        
        def __iter__(self):
            return iter(self._list)

        def __len__(self):
            return len(self._list)

        def append(self,item) :
            self._list.append(item)
            self._dict[item["name"]] = item

class Button :
    def __init__ (self, 
                  game, coords, size, text="" ,
                  fgcolor=None, 
                  bgcolor=None,
                    sel=False , font=None) :
        if not fgcolor :
            fgcolor = [(0,0,0),(0,0,0)]
        if not bgcolor :
            bgcolor = [(100,100,100),(150,150,150)]
        self.bgcolor = bgcolor
        self.fgcolor = fgcolor
        self.coords = coords
        self.size = size
        self.text = text
        self.game = game
        self.sel = sel
        if font :
            self.font = font
        else :
            self.font = self.game.default_font


    def on_draw(self) :
        pygame.draw.rect(self.game.screen,
                         self.bgcolor[self.sel],
                         (self.coords[0],
                         self.coords[1],
                         self.size[0],
                         self.size[1] )
                         )
        
        if self.text :
            self.rendered_text = self.font.render(
            self.text,
            True,
            self.fgcolor[self.sel])
    
            text_rect = self.rendered_text.get_rect(center=(
            self.coords[0] + self.size[0] // 2,
            self.coords[1] + self.size[1] // 2 ))
            self.game.screen.blit(self.rendered_text,text_rect)


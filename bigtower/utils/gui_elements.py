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
        self.rect = pygame.Rect(self.coords[0],
                         self.coords[1],
                         self.size[0],
                         self.size[1] )
        if font :
            self.font = font
        else :
            self.font = self.game.default_font

    def on_resize(self) :
        self.rect = pygame.Rect(self.coords[0],
                         self.coords[1],
                         self.size[0],
                         self.size[1] )


    def on_draw(self) :
        pygame.draw.rect(self.game.screen,
                         self.bgcolor[self.sel],
                         self.rect
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



class InputBox():
    def __init__(self, game, coords, size,
                 fgcolor=[(150,150,150),(250,250,250)], bgcolor=[(0,0,0),(0,0,0)], 
                 sel=True, font=None,font_size=0) :
        self.coords = coords
        self.game = game
        self.cursorpos = 0 # index of where the cursor is in the string
        self.fgcolor = fgcolor
        if font or font_size:
            self.font_size  = font_size or 32
            self.font = pygame.font.Font(font,self.font_size)
        else : 
            self.font = self.game.default_font
        self.bgcolor = bgcolor
        self.size = size
        self.size[1] = self.font.size("Sample Text")[1]
        self.sel = sel
        self.full_text = ""
        self.padding = 5
        self.display_index = [0, 1]
        self.rect = pygame.Rect(self.coords[0],
                         self.coords[1],
                         self.size[0],
                         self.size[1] )

    def _set_cursor_from_mouse(self,mouse_x) :
        pass


    def default_handle_event(self,event) :
        if event.type == pygame.KEYDOWN :
            if event.key == pygame.K_BACKSPACE :
                if (self.cursorpos >= 0) and (self.cursorpos < len(self.full_text)):
                    self.full_text = self.full_text[0:self.cursorpos] + self.full_text[self.cursorpos+1:len(self.full_text)]
                if self.cursorpos > 0 :
                    self.cursorpos -= 1
                    if self.display_index[1] > 0 :
                        self.display_index[1] -= 1
                    if (self.cursorpos < (self.display_index[0])) and (self.display_index[0] > 0) :
                        self.display_index[0] -= 1
                        self.display_index[1] -= 1

            if event.unicode.isprintable() and (event.unicode != '') :
                self.full_text = self.full_text[:self.cursorpos] + event.unicode + self.full_text[self.cursorpos:]
                if self.cursorpos < len(self.full_text) :
                    self.cursorpos += 1
                    if self.font.size(self.full_text[self.display_index[0]:self.display_index[1]])[0] < self.rect.width :
                        self.display_index[1] += 1
                    elif self.cursorpos > (self.display_index[1] - 1) :
                        self.display_index[0] += 1
                        self.display_index[1] += 1
            print(self.cursorpos,self.display_index,self.full_text,self.font.size(self.full_text[self.display_index[0]:self.display_index[1]])[0])

    def handle_event(self,event) :
        self.default_handle_event(event)

    def on_draw(self) :

        pygame.draw.rect(self.game.screen,
                         self.bgcolor[self.sel],
                         self.rect
                         )


        displayed_text = self.full_text[self.display_index[0]:self.display_index[1]]
        rendered_text = self.font.render(
            displayed_text,
            True,
            self.fgcolor[self.sel])
        self.game.screen.blit(rendered_text, self.rect)

        cursor_x = self.rect.x + self.padding + self.font.size(self.full_text[self.display_index[0]:self.cursorpos])[0]
        if self.sel and ( (pygame.time.get_ticks() % 1500 ) < 1000 ):
            pygame.draw.line(self.game.screen,self.fgcolor[self.sel],
                             ( cursor_x  , self.rect.y + 2),
                             ( cursor_x , self.rect.y + self.size[1] - 2) , 2)
        

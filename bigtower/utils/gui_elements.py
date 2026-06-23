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


'''
Ok so this is my idea for the input InputBox

                            cursor
    ==================[------/--]======================
    |                 |         |                     |
    |                 |-d_index-|                     |
    |                                                 |
    |-------------[full_text]-------------------------|

so the display_index in just a slider that slides through full_text.
the cursor is forced to be inside of d_index
'''

class InputBox():
    def __init__(self, game, coords, size,
                 fgcolor=[(150,150,150),(250,250,250)], bgcolor=[(0,0,0),(0,0,0)], 
                 sel=True, font=None,font_size=0) :
        self.coords = coords
        self.game = game
        self.curpos = 0 # index of where the cursor is in the string
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
        self.text = ""
        self.pad_x = self.font.size(">>")[0] 
        self.pad_y = 2
        self.d_i = [0, 0]
        self.rect = pygame.Rect(self.coords[0],
                         self.coords[1],
                         self.size[0],
                         self.size[1] )
        self.inputrect = pygame.Rect(self.coords[0] + self.pad_x,
                         self.coords[1],
                         self.size[0] - (2*self.pad_x),
                         self.size[1] )


    def _set_cursor_from_mouse(self,mouse_x) :
        pass

    def adjust_input_text_width(self) :
        cfs =  self.font.size(self.text[self.d_i[0]:self.d_i[1]])[0] # Current Font Size
        while cfs > (self.inputrect.width) :
            self.d_i[1] = max(0,self.d_i[1] - 1)
            cfs =  self.font.size(self.text[self.d_i[0]:self.d_i[1]])[0] # Current Font Size
        
        if cfs < (self.inputrect.width):
                self.d_i[1] = min(self.d_i[1]+1 , len(self.text))
                cfs =  self.font.size(self.text[self.d_i[0]:self.d_i[1]])[0] # Current Font Size

        while not (self.curpos in range(self.d_i[0],self.d_i[1]+1)) :
            if self.curpos < self.d_i[0] :
                di0 = self.d_i[0]
                self.d_i[0] = max(0,self.curpos)
                self.d_i[1] = self.d_i[1] - (di0 - self.d_i[0])

            elif self.curpos > self.d_i[1] :
                di1 = self.d_i[1]
                self.d_i[1] = min(self.curpos, len(self.text))
                self.d_i[0] = self.d_i[0] - (di1 - self.d_i[1])




    def default_handle_event(self,event) :
        if event.type == pygame.KEYDOWN :
            if event.unicode.isprintable() and (event.unicode != '') :
                self.text = self.text[:self.curpos] + event.unicode + self.text[self.curpos:]
                self.curpos = min(self.curpos+1,len(self.text))

            elif event.key == pygame.K_LEFT :
                self.curpos = max(0,self.curpos - 1)

            elif event.key == pygame.K_RIGHT :
                self.curpos = min(self.curpos + 1 , len(self.text))

            elif event.key == pygame.K_BACKSPACE :
                self.text = self.text[:max(0,self.curpos - 1)] + self.text[self.curpos:]
                self.curpos = max(self.curpos-1,0)
                if (self.d_i[1] - self.d_i[0]) < 2 :
                    self.d_i[0] = max(0,self.d_i[0] - 1)
            

            self.adjust_input_text_width()
            print(self.text , self.curpos, self.d_i)



    def handle_event(self,event) :
        self.default_handle_event(event)

    def on_draw(self) :

        pygame.draw.rect(self.game.screen,
                         self.bgcolor[self.sel],
                         self.rect
                         )

        # Prompt

        self.game.screen.blit(
                self.font.render(
                "=>",
                True,
                (0,100,0)),

                self.rect)


        if self.text :
            self.rendered_text = self.font.render(
                self.text[self.d_i[0]:self.d_i[1]],
                True,
                self.fgcolor[self.sel])
    
            self.game.screen.blit(self.rendered_text,
                                  self.inputrect)
        cursor_x = self.inputrect.x + self.font.size(self.text[self.d_i[0] : self.curpos])[0]
        if self.sel and ( (pygame.time.get_ticks() % 1500) < 1000 ) :
            pygame.draw.line(
                self.game.screen,
                self.fgcolor[self.sel],
                (cursor_x , self.inputrect.y + self.pad_y),
                (cursor_x , self.inputrect.y + self.inputrect.height - self.pad_y),
                2
                )



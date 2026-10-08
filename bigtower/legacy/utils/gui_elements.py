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
    def __init__ (  self, 
                    game, coords, size, text="" ,
                    fgcolor=[(0,0,0),(0,0,0)],
                    bgcolor=[(100,100,100),(150,150,150)],
                    sel=False , font=None) :

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
                 sel=False, font=None,font_size=0) :
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
        self.scroll_threshold = self.pad_x // 4
        self.rect = pygame.Rect(self.coords[0],
                         self.coords[1],
                         self.size[0],
                         self.size[1] )
        self.inputrect = pygame.Rect(self.coords[0] + self.pad_x,
                         self.coords[1],
                         self.size[0] - (2*self.pad_x),
                         self.size[1] )
        self.prompt = self.font.render(
                "=>",
                True,
                (0,100,0))



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
                self.d_i[1] = max(0,self.d_i[1] - (di0 - self.d_i[0]))

            elif self.curpos > self.d_i[1] :
                di1 = self.d_i[1]
                self.d_i[1] = min(self.curpos, len(self.text))
                self.d_i[0] = max(0,self.d_i[0] - (di1 - self.d_i[1]))


        ccl = self.font.size(self.text[self.d_i[0] : self.curpos])[0] # Current cursor location
        if (self.inputrect.width - ccl) < self.scroll_threshold  :
                    self.d_i[0] = max(0,self.d_i[0] + 1)
                    self.d_i[1] = min(len(self.text),self.d_i[1] + 1)

        if (ccl) < self.scroll_threshold:
                    self.d_i[0] = max(0,self.d_i[0] - 1)
                    #self.d_i[1] = min(len(self.text),self.d_i[1] - 1)






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
            

            self.adjust_input_text_width()
            #print(self.text , self.curpos, self.d_i)



    def handle_event(self,event) :
        self.default_handle_event(event)

    def on_draw(self) :

        pygame.draw.rect(self.game.screen,
                         self.bgcolor[self.sel],
                         self.rect
                         )

        # Border
        pygame.draw.rect(self.game.screen,
                         (200,200,200),
                         self.rect,
                         2
                         )

        # Prompt

        self.game.screen.blit(
                self.prompt,
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



class ListBox() :
    def __init__(self,game,coords,size,
                    itemlist : list,
                    max_len=0,
                    fgcolor=[(0,0,0),(0,0,0)],
                    bgcolor=[(100,100,100),(150,150,150)],
                    sel=False) :
        self.game = game
        self.fgcolor = fgcolor
        self.font = self.game.default_font
        self.bgcolor = bgcolor
        self.coords = coords
        self.size = size
        self.rect = pygame.Rect(self.coords[0],
                         self.coords[1],
                         self.size[0],
                         self.size[1] )
        self.itemlist = itemlist
        self.max_len = max_len
        self.font_height = self.font.size("A")[1]
        if not self.max_len :
            self.max_len = ( self.rect.height // self.font_height) - 2
        self.pad_y = 5
        self.d_i = [0, min(self.max_len,len(self.itemlist))]
        self.curr_sel = 0
        self.sel = sel
        self.draw_list = []
        self.setup_draws()
        self.sel_text = ""

    def setup_draws(self) :
            self.old_draw_list = self.draw_list
            self.draw_list = []
            pad = self.pad_y
            for item in self.itemlist[self.d_i[0]:self.d_i[1]] :
                self.draw_list.append(
                        Button(
                                self.game,
                                (self.rect.x,self.rect.y + pad),
                                (self.size[0] , self.font_height),
                                text=item
                                ))
                pad += self.pad_y + self.font_height
            if len(self.old_draw_list) != len(self.draw_list) :
                self.d_i = [0, min(self.max_len,len(self.itemlist))]
                self.curr_sel = 0

            for draw_item in range(len(self.draw_list)) :
                self.draw_list[draw_item].sel = (draw_item == self.curr_sel)
            self.old_draw_list = []
            self.sel_text = self.itemlist[self.curr_sel]

    def default_handle_event(self,event) :

        if event.type == pygame.MOUSEMOTION :
            for num , item in enumerate(self.draw_list) :
                if item.rect.collidepoint(event.pos) :
                    for item2 in self.draw_list :
                        item2.sel = False
                    item.sel = True
                    self.curr_sel = self.d_i[0] + num
            self.setup_draws()


        if event.type == pygame.KEYDOWN :


            # Keybinds
            if event.key == pygame.K_DOWN :
                self.curr_sel = min(self.curr_sel + 1, len(self.itemlist)-1)
                if self.curr_sel > self.d_i[1] :
                    self.d_i[1] = self.curr_sel
                    if (self.d_i[1] - self.d_i[0]) > self.max_len :
                        self.d_i[0] = self.d_i[1] - self.max_len
            
            if event.key == pygame.K_UP :
                self.curr_sel = max(self.curr_sel -1 , 0)
                if self.curr_sel < self.d_i[0] :
                    self.d_i[0] = self.curr_sel
                    if (self.d_i[1] -  self.d_i[0]) > self.max_len :
                        self.d_i[1] = self.d_i[0] + self.max_len

            # Update if keypress
            self.setup_draws()

            #print([i.sel for i in self.draw_list],self.curr_sel)

    def handle_event(self,event) :
        self.default_handle_event(event)

    def on_draw(self) :
        for draw_item in self.draw_list :
            draw_item.on_draw()

        pygame.draw.rect(
                self.game.screen,
            (0,0,0),
            self.rect,
            5
            )
        # for item in self.itemlist  :
            




## Incomplete
class TextBox() :
    def __init__(self,coords,size,text='',font=None) :
        self.fontname = font
        self.levelsizes = [ 32 ] + [ (64 - (4*i)) for i in range(9) ]
        self.fonts = [ None for level in self.levelsizes ]
        self.coords = coords
        self.size = size
        self.text = text
        self.parse_text()

    def parse_text(self) :
        self.parsed_text = []
        for line in self.text.splitlines() :
            line2 = line.strip()
            # Decide H level
            level = len(line2) - len(line2.lstrip('#')) 
            cleared_line = line2.lstrip('#')
            if not self.fonts[level] :
                self.fonts[level] = pygame.font.Font(self.fontname,self.levelsizes[level])

            # Wrap text
            wrapped_lines = []
            lines_to_wrap = cleared_line
            while (self.fonts[level].size(lines_to_wrap)[0] >= self.size[0] ) :
                wrap_index = ( ( self.size[0] *  len(lines_to_wrap) ) //
                              self.fonts[level].size(lines_to_wrap)[0] ) - 1
                wrapped_lines.append(lines_to_wrap[:wrap_index])
                lines_to_wrap = lines_to_wrap[wrap_index:]

            if lines_to_wrap :
                wrapped_lines.append(lines_to_wrap)
            for line in wrapped_lines :
                self.parsed_text.append(
                            {
                            "text" : line,
                            "level" : level
                                }
                        )

        


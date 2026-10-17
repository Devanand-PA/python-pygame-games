import pygame

class Block :
    def __init__(self , game , parent_scene ) :
        import random
        self.parent_scene = parent_scene
        self.game = game
        self.color = [ random.randint(0,100) for i in range(3) ]
        self.broken  = False
        self.sel_insult = ""
        self.block_text = False
        self.hitbox = False

        if self.game.difficulty_level == "Asian" :
                    coin_toss = random.randint(1,10)
                    if coin_toss > 7:
                        import gui_utils.insults as insults
                        self.sel_insult = random.choice(insults.asian_insults["generic"])
                        self.init_insults()

        elif self.game.difficulty_level == "Indian" :
                    import gui_utils.insults as insults
                    self.sel_insult = random.choice(insults.indian_insults["generic"] + insults.asian_insults["generic"])
                    self.init_insults()



        if not self.hitbox :
            self.dimensions = [ random.randint(30, self.game.screen_size[0] // 10) , random.randint(30, self.game.screen_size[1] // 10) ]
            self.coords = [ random.randint(20, max(21, self.game.screen_size[0] - 20 - self.dimensions[0])) , 
                           random.randint(10,max(11,self.game.screen_size[1] - 10*self.parent_scene.paddle.hitbox.height))  ]
            self.hitbox =  pygame.Rect(
                    self.coords[0], self.coords[1] , self.dimensions[0]  , self.dimensions[1]
                            )

    def update(self) :
        pass


    def init_insults(self) :
                import random
                self.block_text = self.game.title_font.render(
                                self.sel_insult,
                            True,
                            (random.randint(100,150),random.randint(100,150),random.randint(100,150))
                                )
                self.hitbox = self.block_text.get_rect()
                self.dimensions = [ self.hitbox.width , self.hitbox.height ]
                self.coords = [ random.randint(20, self.game.screen_size[0] - self.dimensions[0]) , 
                            random.randint(10,self.game.screen_size[1] - self.dimensions[1] - 100)  ]
                self.hitbox.x = self.coords[0]
                self.hitbox.y = self.coords[1]


    def draw(self) :
        pygame.draw.rect(self.game.screen,
                         self.color,
                         self.hitbox
                         )
        if self.block_text :
            self.game.screen.blit(self.block_text,
                                self.hitbox
            )


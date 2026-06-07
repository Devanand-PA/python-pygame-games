import pygame

class Scene :
    def __init__(self,game) :
        self.game = game
        self.scene_name = "scenes.scene_1"
        from scenes.options_screen import Scene as options_screen
        self.options_screen = options_screen(self,self.game)
        from scenes.difficulty_chooser import Scene as difficulty_chooser_scene
        self.difficulty_chooser = difficulty_chooser_scene(self)

        self.difficulty_chooser.enabled = not bool(self.game.difficulty_level)
        self.options_screen_enabled = False

        from objects.paddle import Paddle
        self.paddle = Paddle(game)
        
        from objects.ball import Ball
        self.balls = []
        self.balls.append( Ball(game,self) )
        self.scene_paused = True
        self.snapshot = pygame.Surface(self.game.screen_size)

        self.initialization_stage = 0
        if self.game.difficulty_level :
                self.initialization_stage = 1

        self.breakable_blocks = []
        from objects.breakable_blocks import Block
        self.breakable_blocks.append(Block(self.game, self))


    def update_breakable_blocks(self) :
        import random
        coin_toss = random.randint(0,10**4)
        if (coin_toss > 9875) and ( len(self.breakable_blocks) < 15 ):
            from objects.breakable_blocks import Block
            self.breakable_blocks.append(Block(self.game, self))
        for block in range(len(self.breakable_blocks) -1 , -1, -1) :
            for ball in self.balls :
                if self.breakable_blocks[block].hitbox.colliderect(ball.hitbox) :
                    self.breakable_blocks[block].broken = True
                if  self.breakable_blocks[block].broken :
                    self.breakable_blocks.pop(block)
                    break


            
    
    def update_game(self) :
                ##============ Game Loop========
                for ball in self.balls :
                    ball.update()
                self.paddle.update()
                self.update_breakable_blocks()
                #=================================

    def update(self) :
        if self.initialization_stage == 1 :
            for ball in self.balls :
                ball.initialize_ball()
                self.initialization_stage = 2

        if (not self.game.difficulty_level) and (not self.difficulty_chooser.enabled) :
            from scenes.welcome_screen import Scene
            self.game.scene = Scene(self.game)
        else :
            if not self.scene_paused :
                self.update_game()


        for ball_no in range(len(self.balls)) :
            if self.balls[ball_no].hitbox.y > ( self.game.screen_size[0] ) :
                self.balls.pop(ball_no)


        if self.paddle.hitbox.x > self.game.screen_size[0] - self.paddle.hitbox.width :
                self.paddle.hitbox.x = self.game.screen_size[0] - self.paddle.hitbox.width
    
        self.paddle.hitbox.y = self.game.screen_size[1] - (1.5*self.paddle.hitbox.height)
        if ( not self.scene_paused ) and (not self.balls) :
            self.options_screen_enabled = True
            self.scene_paused = True
            self.difficulty_chooser.enabled = False



    def default_handle_event(self,event) :
        if event.type == pygame.KEYDOWN :
            if (event.key == pygame.K_ESCAPE) and (not self.scene_paused) :
                self.scene_paused = True
                self.options_screen_enabled = True

            elif (event.key == pygame.K_ESCAPE) and (self.scene_paused) and (self.game.difficulty_level) :
                self.scene_paused = False

            elif (event.key == pygame.K_ESCAPE) and (self.options_screen_enabled) :
                self.options_screen_enabled = False
    
    def handle_event(self,event) :
        
        if self.difficulty_chooser.enabled :
            self.difficulty_chooser.handle_event(event)

        if self.options_screen_enabled :
            self.options_screen.handle_event(event)

        else :
            self.default_handle_event(event)

        

    def handle_keypress(self) :
        if self.difficulty_chooser.enabled :
            self.difficulty_chooser.handle_keypress()

        elif not self.scene_paused :
            self.paddle.handle_keypress()


    def handle_difficulty_chooser(self) :
        if self.difficulty_chooser.enabled :
            self.difficulty_chooser.draw()

    def update_savedata(self) :
        import json
        savedata = {
                "balls" : [
                    { "position" : [ ball.hitbox.x , ball.hitbox.y ] ,
                        "velocity" : ball.vel
                        } for ball in self.balls
                    ] ,

                "paddle" : {
                    "position" : self.paddle.hitbox.x
                    },

                "scene" : self.scene_name,
                "difficulty_level" : self.game.difficulty_level
                }

        with open("saves/test.save",'w') as savefile :
            json.dump(savedata,savefile)

    def load_savedata(self,savedata) :
        self.balls = []
        from objects.ball import Ball
        for i in range(len(savedata["balls"])) :
            self.balls.append(Ball(self.game , self))
            self.balls[i].hitbox.x = savedata["balls"][i]["position"][0]
            self.balls[i].hitbox.y = savedata["balls"][i]["position"][1]
            self.balls[i].vel = savedata["balls"][i]["velocity"]
        self.paddle.hitbox.x = savedata["paddle"]["position"]
        self.game.difficulty_level = savedata["difficulty_level"]
        self.difficulty_chooser.enabled = False
        self.scene_paused = False
        self.options_screen_enabled = False
        if self.game.difficulty_level :
                self.initialization_stage = 1

    def handle_gameloop(self) :
        self.paddle.draw()
        for ball in self.balls :
            ball.draw()

        for block in self.breakable_blocks :
            block.draw()
        self.snapshot = self.game.screen.copy()


    def draw(self) :
        self.game.screen.fill((0,0,0))

        if self.scene_paused and self.options_screen_enabled  :
            self.game.screen.blit(self.snapshot, (0,0))
            self.options_screen.draw()

        elif self.scene_paused and self.difficulty_chooser.enabled :
            self.game.screen.blit(self.snapshot, (0,0))
            self.handle_difficulty_chooser()
        else :
            self.handle_gameloop()


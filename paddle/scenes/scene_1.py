import pygame
import time
import gui_utils.insults as insults

class Scene :
    def __init__(self,game) :
        self.game = game
        self.dt = game.dt
        self.scene_name = "scenes.scene_1"
        self.scene_type = "Game"
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
        self.balls.append( Ball(game,self,self.dt) )
        self.scene_paused = True
        self.snapshot = pygame.Surface(self.game.screen_size)
        self.buffs = []
        self.active_buffs = []

        self.initialization_stage = 0
        if self.game.difficulty_level :
                self.initialization_stage = 1

        self.breakable_blocks = []
        from objects.breakable_blocks import Block
        self.breakable_blocks.append(Block(self.game, self))

    def handle_buffs(self) :
        import random
        coin_toss = random.randint(1,100000)
        if (coin_toss > 99500) and ( len(self.buffs) < 2 ):
            from objects.buffs import Buff
            self.buffs.append(Buff(self.game, self))
            coin_toss = 0

        for buff in range(len(self.buffs)- 1 ,-1 ,-1) :
            if self.buffs[buff].hitbox.colliderect(self.paddle.hitbox) :
                caught_buff = self.buffs.pop(buff)
                if caught_buff.buff == "Extraball" :
                    from objects.ball import Ball
                    self.balls.append( Ball(self.game,self,self.dt) )
                elif caught_buff.buff == "Fireball" :
                    for ball in self.balls :
                        ball.fireball = True
                        ball.fireball_timer = time.perf_counter()
                        ball.color = (250,150,0)

            elif self.buffs[buff].hitbox.y > (self.game.screen_size[1]) :
                self.buffs.pop(buff)



        

    def handle_collisions(self,ball,block) :
                    #============ Block Collision =========================
                    # Reliable reflection: push the ball out of the block
                    # along the axis of least penetration, then flip that
                    # velocity component.
                    block_rect = self.breakable_blocks[block].hitbox
                    overlap_left    = ball.hitbox.right  - block_rect.left
                    overlap_right   = block_rect.right   - ball.hitbox.left
                    overlap_top     = ball.hitbox.bottom - block_rect.top
                    overlap_bottom  = block_rect.bottom  - ball.hitbox.top

                    if min(overlap_left, overlap_right) < min(overlap_top, overlap_bottom) :
                        # Horizontal hit
                        if overlap_left < overlap_right :
                            ball.hitbox.right = block_rect.left
                        else :
                            ball.hitbox.left = block_rect.right
                        if ball.vel[0] :
                            ball.vel[0] = -ball.vel[0]
                    else :
                        # Vertical hit
                        if overlap_top < overlap_bottom :
                            ball.hitbox.bottom = block_rect.top
                        else :
                            ball.hitbox.top = block_rect.bottom
                        if ball.vel[1] :
                            ball.vel[1] = -ball.vel[1]
                    #========================================================


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
                    if not ball.fireball :
                        self.handle_collisions(ball,block)
                    

                if  self.breakable_blocks[block].broken :
                    self.breakable_blocks.pop(block)
                    break


            
    
    def update_game(self) :
                self.dt = self.game.dt
                ##============ Game Loop========
                for ball in self.balls :
                    ball.update(self.dt)
                for buff in self.buffs :
                    buff.update(self.dt)
                self.paddle.update()
                self.update_breakable_blocks()
                self.handle_buffs()
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


        for ball_no in range(len(self.balls ) -1, -1 , -1) :
            if self.balls[ball_no].hitbox.y > ( self.game.screen_size[1] ) :
                self.balls.pop(ball_no)


        if self.paddle.hitbox.x > self.game.screen_size[0] - self.paddle.hitbox.width :
                self.paddle.hitbox.x = self.game.screen_size[0] - self.paddle.hitbox.width
    
        if ( not self.scene_paused ) and (not self.balls) :
            if self.game.difficulty_level == "Asian" :
                from scenes.options_screen import Scene as options_screen
                import random
                self.options_screen = options_screen(self,self.game,welcome_text=random.choice(insults.asian_insults["death"]))
            elif self.game.difficulty_level == "Indian" :
                from scenes.options_screen import Scene as options_screen
                import random
                self.options_screen = options_screen(self,self.game,welcome_text="   "+random.choice(insults.asian_insults["death"] + insults.indian_insults["death"])+"  ")
            else :
                from scenes.options_screen import Scene as options_screen
                self.options_screen = options_screen(self,self.game)

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
            self.paddle.handle_keypress(self.game.dt)


    def handle_difficulty_chooser(self) :
        if self.difficulty_chooser.enabled :
            self.difficulty_chooser.draw()

    def update_savedata(self) :
        import json, os
        os.makedirs("saves", exist_ok=True)

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
            self.balls.append(Ball(self.game , self,self.dt))
            self.balls[i].hitbox.x = savedata["balls"][i]["position"][0]
            self.balls[i].hitbox.y = savedata["balls"][i]["position"][1]
            self.balls[i].vel = savedata["balls"][i]["velocity"]
        self.paddle.hitbox.x = savedata["paddle"]["position"]
        self.game.difficulty_level = savedata["difficulty_level"]
        self.difficulty_chooser.enabled = False
        self.scene_paused = False
        self.options_screen_enabled = False
        # Balls are already initialised (incl. speed/gravity) in Ball.__init__
        # and velocities were restored from the save – don't re-randomise them.
        self.initialization_stage = 2

    def handle_gameloop(self) :
        self.paddle.draw()
        for ball in self.balls :
            ball.draw()

        for block in self.breakable_blocks :
            block.draw()

        for buff in self.buffs :
            buff.draw()
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


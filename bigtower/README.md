# bigtower

A tower defense game

# Notice :
shifting the base to pygame from arcade

# Storing Savedata :
Save data is stored in 
```
$HOME/Documents/Saves/bigtower
```
in Unix like systems and 

```
%USERPROFILE%\Documents\Saves\bigtower
```
in Windows.

# TODO :

## Pending
[ ] Write the engine

[ ] Make a Text Box Class that parses markdown to scrollable text

[ ] Make the layout for the career screen (options on the left, stats on the right)
    [ ] Options are : (graphics, back to main menu)

[ ] Make the campaign screen (campaigns levels on the left, upgrades on the right)
[ ] Make the options menu (add a recursive stack for layered menus)

## Done
[✓] Figure out how to get mouse click to work on the menus
[✓] Make an input field class for the username and other things that you might need

# Plan :

## General Plan ;

- I think I'll make it a tower defense game with randomly generated maps and routes.
- The towers will need to be right clickable(for upgrades and the like), and the ground will also need to be right clickable (for building towers)
- The enemies will walk through the paths, increasing in strength with the duration of the game
- Gold will be required to build and upgrade towers, and killing enemies will yield gold.
- The towers will have different kinds of firepower, which can also be upgraded and deleted if needed.
- Samrik says to add a king to the base who can be ejected in an emergency. Ejecting the king means that the player can no longer build or upgrade the towers until the king goes back to base, but the king can move around and attack targets (controlled by the player)

## The engine :
In general , the engine's job is to get the position of the towers and to run the scripts attached to each tower. It is also responsible for guiding enemies to the player base.

- I will need to make a class of unit, from which all other units are descended from. The engine will affect all units equally. If the unit is able to move, it will move towards the nearest enemy. Also , if it is able to attack, it will attack as soon as it is in range of a valid target.

I still do not know if there is a need for a whole engine for this.
Depending on how much work is relegated to the engine, it will either be too trivial or too complicated, nothing in between.
But I guess I will do it anyways.
also, since we will be dealing with a lot of units, it might be wise to write the engine in C

Ok, for now I am just going to use numpy arrays for the engine instead of C

So the plan is that when the game starts , there will be a new object called game.units which will look like this
self.game.unit_array -> m number of players -> n units per player, each of which is np.array(\[self.coords,self.size,self.speed,self.range,self.cooldown\])
The players will be referenced by name whereas the units will be referenced by numbers
so for attacking units, we will just do something like :
```
deltatime -> number of milliseconds per frame
for player in players :
    for unit in player.units                        # Again , have to optimize this
        player.unit.cooldown -= (deltatime*1000)


for player in players : # in general this runs twice because usually there are 2 players , or maybe upto 4 players, idk
    for unit in player.unit_array :      # I need a way to parallelize this
        for other_player in players :
            for unit2 in other_player.unit_array : # I need to parallelize this too
                if np.linalg.norm(unit[0]-unit2[0] > unit[3]) and  (self.game.units[player][unit].cooldown <= 0) :
                    self.game.units[other_player][unit2].hp -= self.game.units[player][unit].attack
                    self.game.unit_array[player][unit][4] = self.game.units[player][unit].cooldown # 1000 is  1 second  
```

Also, there will be a lot of problems in the engine that can only be tested once the engine is complete, therefore the priorities should be :

a) Document as much of the engine as possible, so that fixes are easier

b) Finish the engine as fast as possible while maintaining sufficient documentation, that way , the engine can be fixed as fast as possible.

c) While debugging the engine, document the changes made as well. Also after the debugging is done, document the whole engine all over again.

d) After you are done testing and debugging the engine, test with actual assets. You will need more debugging after that.



## Directory structure :
- menus/        # This directory will have menus and the welcome screen. Accessing the options menu pauses the game.
- engine/       # This one houses the game mechanics
- maps/         # The game is meant to be reused with different maps, so this is for the maps
- units/        # This is where units (like towers and enemies are stored)
    - units/towers  # Towers
    - units/enemies # Enemies
    - units/base    # Base
- ui_elements/  # These are the game UI elements (accessed by right clicking towers and locations on maps). These are handled separately from menus, and accessing them doesn't pause the game.
- assets/       # images, sounds, etc

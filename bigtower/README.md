# bigtower

A tower defense game

# Plan :

## General Plan ;

-I think I'll make it a tower defense game with randomly generated maps and routes.
- The towers will need to be right clickable(for upgrades and the like), and the ground will also need to be right clickable (for building towers)
- The enemies will walk through the paths, increasing in strength with the duration of the game
- Gold will be required to build and upgrade towers, and killing enemies will yield gold.
- The towers will have different kinds of firepower, which can also be upgraded and deleted if needed.

## The engine :
In general , the engine's job is to get the position of the towers and to run the scripts attached to each tower. It is also responsible for guiding enemies to the player base.




## Directory structure :
- menus/        # This directory will have menus and the welcome screen. Accessing the options menu pauses the game.
- engine/       # This one houses the game mechanics
- maps/         # The game is meant to be reused with different maps, so this is for the maps
- units/        # This is where units (like towers and enemies are stored)
    - units/towers  # Towers
    - units/enemies # Enemies
    - units/base    # Base
- ui_elements   # These are the game UI elements (accessed by right clicking towers and locations on maps). These are handled separately from menus, and accessing them doesn't pause the game.


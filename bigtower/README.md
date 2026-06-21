# bigtower

A tower defense game

# Notice :
shifting the base to pygame from arcade

# TODO :

[ ] Make the layout for the career screen (options on the left, campaigns on the right)
    [ ] Options are : (graphics, back to main menu)

[ ] Make the campaign screen (campaigns levels on the left, upgrades on the right)
[ ] Figure out how to get mouse click to work on the menus
[ ] Make the options menu (add a recursive stack for layered menus)

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

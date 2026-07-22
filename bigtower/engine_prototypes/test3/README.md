# Purpose of Test 2 :
- To do the same thing that test 2 can do, but make it so that the engine is a separate callable library that just takes in units as they are added.

# TO DO
[x] Make the Game separate from the "engine"
[x] Make a separate lib for "units"
[x] Make some "Player" variables and also track units by player and player groups, instead of "mobs" vs "towers"
[x] Make it so that the unit append via clicking is implemented in the "Game" instead of the "engine"
[x] Make multiple "Tower" and "Mob" types
[x] separate "pathing" from "movement"
[?] Parallelize choose_target() and path_to() # This might be premature optimization, I don't know

# Scratchpad

NOTE : Calculate the new positions of each unit in parallel first ( in a way that only reads data or computes from a copy) , and then do a sequential movement update

## For Players


Something like
```

class player(..) :
    player.units = []

player_groups = [ [player1, player2] , [player3, player4]]
for group in range(len(player_groups)) :
    for player in player_group[group] :
        player.group = "group-"+str(group)

....
class Unit(..,player) :
    ...
    self.player = player
    self.player.units.append(self)
```

and then

```
def choose_target(..) :
 ......
 if unit_considered.player not in self.player.group :
                                        if ( curr_dist:=  np.linalg.norm(unit_considered.coords - self.coords)) < target_distance:
                                            target_distance = curr_dist
                                            target = unit_considered
                                            target_found = True

```

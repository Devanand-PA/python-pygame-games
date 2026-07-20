# Purpose of Test 2 :
- To do the same thing that test 2 can do, but make it so that the engine is a separate callable library that just takes in units as they are added.

# TO DO
[ ] Make the Game separate from the "engine"
[ ] Make a separate lib for "units"
[ ] Make some "Player" variables and also track units by player and player groups, instead of "mobs" vs "towers"
[ ] Make it so that the unit append via clicking is implemented in the "Game" instead of the "engine"
[ ] Make multiple "Tower" and "Mob" types

# Scratchpad

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

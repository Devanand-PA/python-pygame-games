# bigtower

A tower defense game

## Running

```sh
# from the repository root (the folder containing main.py)
.venv/bin/python main.py            # windowed
.venv/bin/python main.py --fullscreen
```

The internal resolution is a fixed 1280x720 canvas that is letterboxed into the
window, so the game looks consistent at any window size. `F11` toggles
fullscreen.

Flow: Main menu -> pick/create a player -> Career hub -> Play Campaign ->
choose a race/campaign -> Select Level -> defend the base. Placing towers costs
gold (kill enemies to earn more), right-click cancels the current selection, and
`Space` calls the next wave early for a bonus. Progress is saved per player.

## Content, races and campaigns

The game is data-driven: terrain, units, races (campaigns) and levels all live
as editable JSON under `content/`:

```
content/
    terrain.json           the terrain palette (grid character -> tiles + flags)
    units/<unit_id>.json   every unit, defender *and* attacker, one schema
    races/<race_id>.json   a campaign: defender roster, enemy roster, levels
    levels/<level_id>.json grid, economy, available units, enemy pool, waves
```

A **race** is a campaign (e.g. *Woodlanders*, *The Brood* / aliens, *Iron
Legion* / machines). Each race offers a different set of defender units and
faces a different set of attackers, and owns an ordered list of levels.

A **unit** is fully customisable and uses one schema for both sides. Key fields:

- `side`: `defender` (placed by the player, a "tower") or `attacker` (spawned
  by waves).
- `movement`: `static` (classic turret) | `chase` (a defender, e.g. the
  Scorpion, walks after the nearest enemy) | `route` (attacker follows the map
  path) | `direct` (flies straight at the base) | `hunt` (leaves the path to
  chase a defender).
- `attack`: `none` | `melee` | `projectile` -- attacking units fight back, so
  **enemies damage towers too**.
- `sprite` / `projectile_sprite`: a *sprite spec* (see below), plus an optional
  `tint` that overrides the race tint.

### Sprites and animation

You can point units **and** terrain at your own art, with animation. Dropping a
PNG under `assets/` is enough -- the designer's built-in file browser lists them,
and `terrain.json`/`units/*.json` reference them by relative path. A sprite spec
is one of:

```json
{"kind": "pack",  "tile": 226}
{"kind": "image", "path": "units/foo/bar.png"}
{"kind": "shape", "shape": "circle", "color": [200, 120, 120]}
{"kind": "sheet", "path": "units/foo.png", "frame_w": 32, "frame_h": 32,
 "frames": 6, "fps": 8, "loop": true, "margin": 0, "spacing": 0}
{"kind": "anim",  "fps": 8, "loop": true, "frames": [ <spec>, <spec>, ... ]}
{"kind": "sprites",                                    // animated unit art
 "image": {"kind": "image", "path": "units/foo.png"},  // static fallback
 "animations": {
   "idle":  {"kind": "sheet", "path": "units/foo.png", "frame_w": 32,
             "frame_h": 32, "frames": [0, 1], "fps": 6, "loop": true},
   "walk":  {"kind": "sheet", "path": "units/foo.png", "frame_w": 32,
             "frame_h": 32, "frames": [2, 3, 4], "fps": 10, "loop": true},
   "attack": {"kind": "sheet", "path": "units/foo.png", "frames": [5],
              "frame_w": 32, "frame_h": 32, "fps": 12, "loop": false}
 }}
```

- `sheet` slices a spritesheet left-to-right, then top-to-bottom (optionally
  with `cols`/`rows`/`margin`/`spacing`). Its `frames` is a count **or** an
  explicit list of frame indices.
- `anim` is an explicit list of frames, each any other spec.
- `sprites` is the animated unit sprite: named states (`idle`, `walk`, `attack`,
  `death`) cut from one spritesheet, plus an optional static `image` used for any
  state that has no animation. The game plays the matching state automatically
  (still -> `idle`, moving -> `walk`, firing -> `attack`, killed -> `death`) and
  falls back to `idle` / the `image` when a state is missing.
- Terrain uses the same specs for its `sprite` (ground) and optional
  `overlay_sprite` (rocks, bushes, decals), so animated water/lava/etc. work
  (terrain animates as a single looping `sheet`/`image`).
- Units and animated terrain tiles animate in-game; frames are resolved by
  `engine.art` (`sprite_frames`, `frame_index`, `fps`, `frame_count`, each taking
  an optional animation `name`).

Levels pick a subset of the race's units (`available_units`, the level's shop)
and attackers (`enemy_pool`), then define `waves` (each a list of
`[unit_id, count, spawn_interval]` groups). The spawn `S` and base `B`
characters are reserved; ground routes are found automatically by a breadth-first
search from `S` to `B`, so branching maps work.

## Level designer

`designer.py` is a standalone pygame app for authoring everything above without
touching Python or JSON by hand:

```sh
.venv/bin/python designer.py
```

It has five tabs -- **Terrain**, **Units**, **Races**, **Levels** and **Help**.
The Levels tab lets you paint the map (left-click paints, right-click erases,
and clicking a palette swatch chooses the brush, including the `S` spawn and
`B` base), previews the spawn->base route (warns if there is none), picks the
level's shop and enemy pool, and builds waves.

To set art, **click the sprite preview** on the Units or Terrain tab. You are
asked whether the sprite is a **static image** or an **animation**; either way a
built-in file browser opens so you can navigate `assets/` and pick a PNG (or
spritesheet). For an animation, the animation editor shows the sheet as a grid
of numbered frames -- choose a state (`idle` / `walk` / `attack` / `death`, or a
single looping clip for terrain), set its `fps` and `loop`, then click frames to
assign them (shift-click adds a range). A static image can be kept as the
fallback for states without an animation. Everything saves back to the same
`content/` JSON the game reads.

## Status

The engine (top of the repo: `core/`, `engine/`, `gui/`, `menus/`) is a working
pygame rewrite. All three campaign levels are playable and winnable, progress
and stats persist between runs, and the code is exercised by headless tests:

```sh
SDL_VIDEODRIVER=dummy .venv/bin/python tools/flow_test.py   # logic + persistence
.venv/bin/python tools/screenshots.py                       # visual snapshots
```

## Building a release

`build.sh` bundles the game code, every asset, all maps and all content JSON
*inside* a single `--onefile` executable, then zips it for distribution:

```sh
./build.sh
```

Output:

- `dist/bigtower` — the self-contained game (runs from anywhere)
- `dist/bigtower-<os>-<arch>.zip` — distributable archive

PyInstaller is installed into `.venv` automatically if it is missing. The
underlying cross-platform build lives in `build.py` (used both locally and by
CI).

Every push to `main` runs `.github/workflows/bigtower.yml`, which builds
Linux, Windows and macOS executables and publishes them to the release page
under the rolling
[`bigtower-latest`](https://github.com/Devanand-PA/python-pygame-games/releases/tag/bigtower-latest)
tag.

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
[ ] Make a Text Box Class that parses markdown to scrollable text

[ ] Make the campaign screen richer (campaigns on the left, upgrades on the right)
    [ ] Persistent tower upgrades purchased between levels

## Done
[x] Write the engine (pygame port lives in core/, engine/, gui/, menus/)
[x] Playable career menu, level select with unlock progress and saved stats
[x] 3 playable campaign levels with towers, enemies, waves, win/lose flow
[x] Data-driven content: terrain, units, races and levels authored as JSON
[x] Race-based campaigns (Woodlanders, aliens, machines) with per-race rosters
[x] Fully customisable units (movement, attack, sprite, tint)
[x] Enemies that attack towers (two-way combat); melee chaser defenders
[x] Standalone level/unit designer GUI (designer.py)
[x] Figure out how to get mouse click to work on the menus
[x] Make an input field class for the username and other things that you might need

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

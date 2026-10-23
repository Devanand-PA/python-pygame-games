# Big Tower — Level Designer Tutorial

A complete, option-by-option guide to `designer.py`: the standalone pygame app for
authoring everything the game reads out of `content/`.

This document is written so you can use the designer however you like. Every
control is listed with **what it does**, **what values it accepts**, and **what it
writes to disk**, so you never have to guess or read the Python source.

---

## Table of contents

1. [Quick start](#1-quick-start)
2. [Command-line options](#2-command-line-options)
3. [Window, canvas and scaling](#3-window-canvas-and-scaling)
4. [Shared controls (all editor tabs)](#4-shared-controls-all-editor-tabs)
5. [Keyboard shortcuts](#5-keyboard-shortcuts)
6. [Widget reference](#6-widget-reference)
7. [Terrain tab](#7-terrain-tab)
8. [Units tab](#8-units-tab)
9. [Races tab](#9-races-tab)
10. [Levels tab](#10-levels-tab)
11. [Setting sprite art](#11-setting-sprite-art)
12. [Saving, undo and what lands on disk](#12-saving-undo-and-what-lands-on-disk)
13. [Worked example: a new level](#13-worked-example-a-new-level)
14. [Troubleshooting](#14-troubleshooting)
15. [Where things live in the code](#15-where-things-live-in-the-code)

---

## 1. Quick start

```sh
cd /path/to/bigtower
.venv/bin/python designer.py
```

Or, if your virtualenv is already active:

```sh
python designer.py
```

There is **no install step and no arguments required**. The designer opens a
window titled *"Big Tower - Level Designer"* and shows five tabs across the top:

| Tab | What you edit |
| --- | --- |
| **Terrain** | The grid characters, their art, and their build/walk rules |
| **Units** | Every defender ("tower") and attacker in the game |
| **Races** | A campaign: which units it offers, which enemies it spawns, its hero |
| **Levels** | The map grid, economy, shop, enemy pool and wave list |
| **Help** | A scrollable in-app cheat sheet |

The status line at the **top-right of the tab bar** tells you what just happened
(`Terrain: saved 9 entries`, `ERROR: duplicate ids - not saved`, …). Watch it — it
is the app's only feedback channel.

Nothing is written to disk until you press **Save** (or `Ctrl+S`).

---

## 2. Command-line options

`designer.py` is a small launcher; all argument handling lives in
`level_designer/app.py:254`.

### `--fullscreen`

```sh
.venv/bin/python designer.py --fullscreen
```

**Help text:** Start the designer covering the whole screen at your desktop
resolution instead of in a 1280×720 resizable window. Useful on small laptops
where the editor's fixed canvas would otherwise be scaled down.

This is the **only** command-line option. Its implementation is a plain substring
check:

```python
fullscreen = "--fullscreen" in argv          # level_designer/app.py:256
```

You can toggle the same setting at runtime with **F11** (see below), so the flag
is purely a convenience for what you want on startup.

### Unknown arguments are ignored

There is **no `argparse`**, so there is no `--help`, no `--version`, and no error
for a typo. `designer.py --help` starts the editor normally in windowed mode, and
`designer.py --fulscreen` (misspelled) silently does nothing. If a flag appears
to be ignored, check the spelling against `--fullscreen` exactly.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Normal exit (window closed, `Esc`, or `Ctrl+C`) |
| non-zero | An unhandled Python exception — the traceback prints to the terminal |

Because `Ctrl+C` is caught, you can always quit from the terminal you launched it
from.

---

## 3. Window, canvas and scaling

**Help text:** The designer always draws into a fixed **1280×720** canvas and then
scales that canvas into whatever window size you have. This keeps every tab's
layout pixel-exact no matter your monitor.

* **Resizable window** — drag the window edges freely. The canvas is letterboxed
  (aspect ratio preserved) and centred, with black bars filling the remainder.
  Your mouse position is translated back into canvas coordinates automatically, so
  clicks always land where you see them.
* **Smooth scaling** — when the window is larger or smaller than 1280×720, the
  canvas is scaled with `smoothscale`. On very large windows text gets slightly
  soft; that is the scaling, not a rendering bug.
* **F11** — toggles fullscreen on and off at any time. See
  [Keyboard shortcuts](#5-keyboard-shortcuts).

> **Dummy/headless mode:** if you run with `SDL_VIDEODRIVER=dummy` (for automated
> testing) no `flip()` happens, and the app guards against the resulting
> zero-sized window. Images will not appear, but the app still runs.

---

## 4. Shared controls (all editor tabs)

The **Terrain**, **Units** and **Races** tabs share one layout: a scrollable list
on the left, an edit form on the right. The **Levels** tab has three columns.

### The six standard buttons

These sit in a grid under the list panel on every editor tab.

| Button | Help text |
| --- | --- |
| **New** | Create a new entry with sensible defaults and select it. If the default id is taken, `_2`, `_3`, … is appended, so you never get a duplicate id. |
| **Dup** | Deep-copy the currently selected entry. The id gets a `_copy` suffix and the name gets `" copy"` appended; collisions get numbered. Great for making variants. |
| **Delete** | Remove the selected entry from the list. Also prunes any now-orphaned content files on save. **Undoable.** |
| **Save** | Validate and write every entry in the list to `content/`, then reload from disk. Green button. |
| **Undo** | Step back one action. Disabled (greyed) when there is nothing to undo. |
| **Redo** | Step forward one action. Disabled when there is nothing to redo. |

### The list panel

* **Click a row** to select and edit that entry. Selection is *not* an edit, so it
  never creates an undo step.
* **Mouse wheel** scrolls the list.
* **Double-clicking** a row behaves like a click — there is no inline rename.

### Dirty state and the `*` marker

**Help text:** A `*` next to a tab's title means there are **unsaved changes**. The
list panel also shows either `saved` (green) or `unsaved changes` (red), plus a
line such as `3 undo steps - Ctrl+Z`.

Saving clears the marker. If you switch tabs or close the window with a `*`
showing, your edits are discarded — **Save first.**

### Validation before saving

* **Duplicate `id`s block the save.** You get
  `ERROR: duplicate ids - not saved` for Terrain/Units/Races, or
  `ERROR: duplicate level ids - not saved` on Levels.
* **Terrain has an extra rule:** grid characters must be unique and must not be
  `S`, `B` or a space. Otherwise:
  `ERROR: terrain chars must be unique and not S/B`.
* **`id` is the identity key.** Renaming an entry's `id` and saving creates a new
  file and prunes the old one. Keep ids stable once levels reference them.

---

## 5. Keyboard shortcuts

| Shortcut | Where | Help text |
| --- | --- | --- |
| `Ctrl+S` | Anywhere | Save the **current tab**. |
| `Ctrl+Z` | Anywhere | Undo the last change on the current tab. |
| `Ctrl+Y` **or** `Ctrl+Shift+Z` | Anywhere | Redo. |
| `F11` | Anywhere | Toggle fullscreen. |
| `Esc` | Normal mode | Quit the designer. |
| `Esc` | Modal open | Close the modal (file browser, animation editor, dialog) and return to the editor. |
| `Space` + left-drag | Levels map | Pan the map. |
| `Shift` + click | Animation editor | Select the whole range of frames since your last click. |
| Mouse wheel | Levels map | Zoom in/out about the cursor. |

**Why `Ctrl+Z` works while typing:** the shortcut is handled in the app's hotkey
layer *before* widgets see the key, so a focused text box can't swallow it. `Ctrl+Z`
therefore undoes even mid-typing, as you would expect.

`Esc` is careful not to be destructive: it only quits when **no modal is open**,
so `Esc` inside the file browser closes the browser instead of the app.

---

## 6. Widget reference

Every option in this guide maps to one of these controls. Knowing the types makes
the per-tab tables easier to read.

| Widget | How to use it | Help text |
| --- | --- | --- |
| **Text field** | Click to focus, type. Backspace deletes; arrow keys move the cursor. | Free text (a value with surrounding spaces is trimmed). |
| **Int field** | Same, but only digits and a leading `-` are accepted. | Whole numbers only. Invalid characters are simply ignored as you type. |
| **Float field** | Same, but digits, `.` and `-` are accepted. | Decimal numbers. |
| **Checkbox** | Click to toggle. | On/off boolean. Click the row, not just the box. |
| **Choice field** | Click to cycle to the next option. | A fixed set of allowed strings — click repeatedly to cycle. The current value is shown in the box. |
| **Colour field** | Click to cycle through channels/values. | An RGB colour stored as `[r, g, b]`. |
| **Tile field** | Click to open a picker grid of the built-in Kenney tiles; you can also type a tile number. | The built-in tile pack — no PNG needed. |
| **Image field** | Click to open the built-in file browser and pick a PNG. | A path relative to `assets/`, e.g. `units/foo/bar.png`. |
| **Multi-select** | Click an item to tick/untick it. Wheel scrolls. | A checkbox list; the value is the list of ticked ids, in on-screen order. |
| **Scroll list** | Click a row to select; wheel scrolls. Double-click is the same as one click. | A single-selection list. |

A ticked multi-select entry stores its **id**, so the JSON stays valid even if you
later rename the entry's display name.

---

## 7. Terrain tab

**Help text:** A terrain entry maps **one grid character** to its art plus its
build/walk rules. The Levels tab turns those characters into the paintable palette.

Entries live in `content/terrain.json` (one file holds all of them).

### Fields

| Label | JSON key | Help text |
| --- | --- | --- |
| `id` | `id` | Unique identifier, e.g. `grass`. Do not change it casually — levels reference terrain by **character**, but other entries reference ids. |
| `name` | `name` | Display name shown under the palette swatch in the Levels tab (truncated to 9 characters there). |
| `grid char (1 char)` | `char` | The single character painted into the map grid. Only the first character is stored. Must be **unique** across all terrain, and must not be `S`, `B` or a space. |
| `base kind` | `sprite.kind` or `base` | How the ground art is drawn. One of `pack`, `image`, `sheet`. See [Sprite art](#11-setting-sprite-art). |
| `base tile` | `base` | Kenney tile number for `pack` kind. Shown in the base preview. |
| `base png` | `sprite.path` | PNG path (relative to `assets/`) for `image` / `sheet` kinds. |
| `base frame w` / `base frame h` | `sprite.frame_w` / `frame_h` | Pixel size of one frame in the sheet. Default `32`. |
| `base frames` | `sprite.frames` | Number of frames in the sheet (or the length of the frame list). Default `1`. |
| `base fps` | `sprite.fps` | Animation playback speed. Default `8.0`. Clamped to a minimum of `0.1`. |
| `base loop` | `sprite.loop` | Whether the animation repeats. Default **on**. |
| `overlay kind` | `overlay_sprite.kind` | Decoration drawn **on top** of the base — rocks, bushes, decals. One of `none`, `pack`, `image`, `sheet`. |
| `overlay tile` | `overlay` | Tile number for an overlay of kind `pack`. |
| `overlay png` | `overlay_sprite.path` | PNG path for an overlay of kind `image` / `sheet`. |
| `overlay frame w` / `overlay frame h` | `overlay_sprite.frame_w` / `frame_h` | Frame size for an overlay sheet. Default `32`. |
| `overlay frames` | `overlay_sprite.frames` | Frame count for an overlay sheet. Default `1`. |
| `overlay fps` | `overlay_sprite.fps` | Overlay animation speed. Default `8.0`. |
| `overlay loop` | `overlay_sprite.loop` | Whether the overlay animation repeats. Default **on**. |
| `buildable` | `buildable` | **Players may place defenders on this tile.** Turn off for water, lava, etc. Default **on**. |
| `walkable` | `walkable` | **Ground enemies may path through this tile.** Turn off and the route preview routes around it. Default **on**. |
| `custom tint` | *(enables `tint`)* | Tick to apply a colour tint to this terrain's art. Unticked writes `null`. |
| `tint RGB` | `tint` | The `[r, g, b]` tint. Only saved when `custom tint` is ticked. |
| `description` | `description` | Free-text note for yourself. Not shown in the game. |

### Choosing the right `base kind`

| Value | Use it for | What gets stored |
| --- | --- | --- |
| `pack` | Built-in Kenney tiles — zero asset work. | `base` (tile number); `sprite` is written as `null`. |
| `image` | A single static PNG of your own. | `sprite: {kind, path}`. |
| `sheet` | A spritesheet animated as one looping clip. | `sprite: {kind, path, frame_w, frame_h, frames, fps, loop}`. |

Terrain overlays accept the same three kinds **plus `none`** to remove the overlay
entirely.

### Reserved characters — important

**`S` (spawn) and `B` (base) are reserved** and are always available as palette
swatches on the Levels tab. They are not terrain entries, and the Terrain tab
refuses to save a terrain whose `char` is `S` or `B`. A space is also rejected.

The characters shipped with the game are `g` grass, `.` road, `r` rock, `t` bush,
`s` sand, `o` stone, `w` water, `n` ice and `l` lava.

### Previews

Two preview boxes sit under the form:

* **Base terrain art** — click it to set the ground art.
* **Overlay (rocks / decals)** — click it to set or change the overlay. Shows
  *"none - click to add"* when there is no overlay.

Animated art shows `N frames @ F fps` under the preview, and the preview animates
live.

---

## 8. Units tab

**Help text:** One schema covers **both sides**. `side=defender` units are placed
by the player (towers); `side=attacker` units are spawned by enemy waves. There are
39 fields — this is the deepest tab, so the table is grouped by purpose.

### Identity

| Label | JSON key | Help text |
| --- | --- | --- |
| `id` | `id` | Unique id, e.g. `arrow_tower`. Levels, races and waves reference this. |
| `name` | `name` | Display name shown in the shop and the list (`[def] Arrow Tower`). |
| `side` | `side` | `defender` = player-placed tower. `attacker` = enemy spawned by a wave. Click to cycle. |
| `role` | `role` | Free-text category label (e.g. `anti-air`, `splash`). Purely descriptive. |

### Sprite and art

| Label | JSON key | Help text |
| --- | --- | --- |
| `sprite kind` | `sprite.kind` | `pack`, `image`, `shape`, `sheet`, `anim` or `sprites`. In practice you set this by **clicking the preview**, which writes the whole spec at once. |
| `sprite tile` | `sprite.tile` | Kenney tile number for `pack`. |
| `image / sheet png` | `sprite.path` | PNG path for `image` / `sheet`. |
| `shape` | `sprite.shape` | For `shape` kind: `circle`, `square`, `diamond` or `triangle`. A placeholder you can draw without any asset. |
| `shape colour` | `sprite.color` | RGB for `shape` kind. |
| `frame w` / `frame h` | `sprite.frame_w` / `frame_h` | Frame size inside a sheet. Default `32`. |
| `frame count` | `sprite.frames` | Number of frames. Default `1`. |
| `anim fps` | `sprite.fps` | Animation speed. Default `8.0`, clamped to at least `0.1`. |
| `loop` | `sprite.loop` | Whether the animation repeats. Default **on**. |
| `sprite scale` | `sprite_scale` | Multiplier on the drawn size. `1.0` = natural size. Use >1 for big units, <1 for small ones. |
| `custom tint` | *(enables `tint`)* | Tick to override the race tint — handy for recoloured variants of one sprite. |
| `tint RGB` | `tint` | The `[r, g, b]` override. Written as `null` when unticked. |

### Combat stats

| Label | JSON key | Help text |
| --- | --- | --- |
| `hp` | `hp` | Hit points. |
| `cost (defender)` | `cost` | Gold price in the level's shop. Ignored for attackers. |
| `bounty (attacker)` | `bounty` | Gold the player earns for killing this attacker. Ignored for defenders. |
| `speed (0=static)` | `speed` | Movement speed in px/s. **`0` means the unit never moves** — the normal choice for towers. |
| `movement` | `movement` | How it navigates: `static`, `chase`, `route`, `direct`, `hunt`. |
| `attack` | `attack` | `none`, `melee` or `projectile`. |
| `range` | `range` | Attack reach in pixels. |
| `damage` | `damage` | Damage per hit. |
| `cooldown (s)` | `cooldown` | Seconds between attacks. Lower = faster. |
| `shots / attack` | `projectiles` | **How many projectiles one attack fires.** Always at least `1`. Raise it for a shotgun/multishot effect. |
| `projectile` | `projectile` | Visual/sound style: `dot` or `rocket`. |
| `splash radius` | `splash` | Area-of-effect radius in pixels. `0` = single target. |
| `sound` | `sound` | Attack sound: `gun`, `sting`, `missile`, `sniper`, `laser`, `zap`. |
| `targets` | `targets` | What it can hit: `both`, `ground` or `air`. |
| `targeting` | `targeting` | Target priority: empty (default), `nearest`, `first`, `strongest`, `weakest`. |
| `is flying` | `is_flying` | The unit flies, so ground-only attackers cannot hit it. |
| `dmg to base` | `damage_to_base` | How much the base loses when this attacker reaches it. |
| `stop to attack` | `stop_to_attack` | If on, the unit halts while attacking. Turn off for units that fire on the move. |
| `aggro radius` | `aggro` | How far away it will notice and engage a target. |
| `body radius` | `radius` | Collision radius in pixels — how close it can get and how big a target it is. |
| `attackable` | `can_be_attacked` | Turn off for invulnerable or purely decorative units. |
| `description` | `description` | Flavour text shown in the shop / unit info. |

### Choosing `movement`

| Value | Help text |
| --- | --- |
| `static` | Never moves. Correct for defenders/towers. |
| `chase` | Moves toward the nearest enemy in range (typical defender behaviour if it should reposition). |
| `route` | Follows the level's generated spawn→base route. Typical for ground attackers. |
| `direct` | Heads straight for the target/base, ignoring the route. Typical for flyers. |
| `hunt` | Seeks out player units rather than pushing to the base. |

### Upgrade paths

Below the form is the **Upgrade path editor**. **Help text:** a defender picks
**one branch per level-up** instead of climbing a single linear ladder.

Controls:

| Control | Help text |
| --- | --- |
| Branch list | Click a branch to edit it. The wheel scrolls. |
| `add` | Add a new branch. |
| `del` | Delete the selected branch. |
| `default` | Restore the five shipped branches: **damage / range / rapid / multi / vitality**. |
| `id`, `name` | The branch's identifier and display name. |
| `dmg`, `range`, `rate`, `hp` | Four gain **multipliers**. `1.0` = unchanged, `1.25` = +25%, `0.82` = faster. |
| `+shots` | Additive projectile-count bonus for this branch (e.g. `1` adds one projectile). |

**Help text:** every gain is always written out, so exactly what you type survives
a save and reload. Leaving the path list empty means "use the shipped defaults".

The editor shows a live summary line such as
`dmg x1.25, range x1, rate x1, hp x1, +1 shot` so you can see the branch at a
glance.

### Sprite preview

The large box at the bottom-left is the **live sprite preview**. It animates, and
it is showing exactly what the game will draw with the current settings.

Click it to open the sprite flow — see [Setting sprite art](#11-setting-sprite-art).
The caption beneath reads `Sprite - click to change`, plus either
`states: idle, walk, attack, death` for a full animation or
`N frames @ F fps` / `static pack` for simpler art.

---

## 9. Races tab

**Help text:** A race is a campaign. It decides which defender units are on offer,
which attackers the levels use, and which hero defends the base.

Entries live in `content/races/`. The three shipped races are `aliens`,
`machines` and `woodlanders`.

### Fields

| Label | JSON key | Help text |
| --- | --- | --- |
| `id` | `id` | Unique race id. Levels select a race by this id. |
| `name` | `name` | Display name (`Woodlanders`). |
| `menu order` | `order` | Sort position in the race-selection menu. Lower comes first. |
| `base hero` | `hero` | The defender **summoned when an attacker reaches the base**. A dropdown of every defender unit id, plus `(none)` to clear it. An unknown id is kept visible rather than dropped, so you never silently lose data. |
| `theme colour` | *(enables `color`)* | Tick to use a custom theme colour. It is always on when loaded; unticking falls back to `[120, 200, 140]`. |
| `colour RGB` | `color` | The race's UI theme colour. Default `[120, 200, 140]`. |
| `unit tint` | *(enables `tint`)* | Tick to tint every unit of this race. |
| `tint RGB` | `tint` | The race-wide tint. Default `[200, 240, 200]`; written as `null` when unticked. A unit's own `custom tint` overrides this. |
| `description` | `description` | Flavour text shown in the race menu. |

### Unit rosters

Two tall checkbox lists at the bottom:

| List | JSON key | Help text |
| --- | --- | --- |
| **Available units (defenders)** | `units` | Every defender offered in this race's shop. Unticked defenders are unavailable in its levels. |
| **Enemies** | `enemies` | Every attacker this race's levels may spawn. Wave building on the Levels tab picks from the level's *enemy pool*, which in turn should come from here. |

Both list **ids**, and both are populated from the current `content/` on each
visit, so units you add on the Units tab appear here after saving. An empty
selection means "all in this race", not "none" — see the note on the Levels tab's
shop and enemy pool.

### Levels for this race

The footer line `Levels for this race: ... (edit on the Levels tab)` is
**read-only**. Levels are attached from the **Levels** tab's `race` field, and
saving a level re-syncs each race's level list automatically, ordered by each
level's `order`.

---

## 10. Levels tab

The most powerful tab, with three columns:

```
[ level list ]      [   map canvas   ]      [ form + waves ]
[ New/Dup/... ]     [ zoom + palette ]      [ shop / pool    ]
```

Levels live in `content/levels/`. Nine ship with the game, three per race.

### 10.1 The level form

| Label | JSON key | Help text |
| --- | --- | --- |
| `id` | `id` | Unique level id, e.g. `woodlanders_01`. Keep it stable; saves are keyed by it. |
| `name` | `name` | Display name. The list shows `Name [race]`. |
| `race` | `race` | Which race this level belongs to. A dropdown of every race id. This is what attaches the level to a campaign. |
| `order` | `order` | Play order within the race. Lower comes first; the Levels tab uses it to sort the race's level list. |
| `gold` | `gold` | **Starting gold.** Default `200`. |
| `gold / sec` | `gold_per_sec` | **Passive income in gold per second — the main per-level difficulty knob.** Range `0`–`25`; the default is `1.0`. Clamped automatically and rounded to 4 decimals. Lower it for a harder level. |
| `lives` | `lives` | Leaks the player can afford before losing. Default `20`. |
| `grid W` | *(derived)* | Map width in cells. **Typing here resizes the canvas and is undoable.** It is derived from the grid, so it is not itself stored. |
| `map tint` | *(enables `terrain_tint`)* | Tick to tint the whole map. |
| `tint RGB` | `terrain_tint` | The map-wide tint. Written as `null` when unticked. |
| `grid H` | *(derived)* | Map height in cells. Same behaviour as `grid W`. |
| `description` | `description` | Free-text note. |

### 10.2 The map canvas

**Help text (on screen):** `wheel: zoom   drag: pan   Ctrl+Z: undo`.

The panel is fixed; the **cell size is the zoom**, between **6 and 48 pixels per
cell** (default 28, each zoom step is ×1.25). Only the visible cells are drawn, so
even a 60×40 map stays smooth.

| Input | Help text |
| --- | --- |
| **Left click** | Paint the selected terrain character into that cell. |
| **Left drag** | Paint a continuous stroke. The whole stroke is a **single undo step**. |
| **Right click** (no movement) | Erase the cell back to grass (`g`). |
| **Right drag** | Pan the map. It only becomes a pan after the mouse moves more than **4 px**, so a right-*click* still erases and a pan is never mistaken for a paint stroke. |
| **Middle drag** | Pan the map. |
| **Space + left drag** | Pan the map. |
| **Mouse wheel** | Zoom in/out, **keeping the point under the cursor fixed**. Wheel-up zooms in. |

> **No modifier tools.** There is no `Ctrl`/`Shift` handling on the map canvas — no
> rectangle-fill, no line tool, and no shift-to-pan. The only keyboard state the
> canvas reads is `Space`. `Ctrl+Z`/`Ctrl+Y` still work, because the Levels tab
> handles them *before* the canvas sees the event.

Grid lines are drawn only when zoomed in to **10 px/cell or more**; below that
they are hidden as visual noise.

Painting `S` or `B` is special: the canvas enforces **exactly one of each** by
clearing any previous occurrence before placing the new one. The `S` and `B`
markers are drawn as icons on top of grass.

### 10.3 Palette swatches

Below the map is the terrain palette: one swatch per terrain entry, **plus `S`
and `B`**. **Left- or right-click a swatch** to choose your brush; the status line
confirms with `Brush: 'w'`, `Brush: 'spawn'` or `Brush: 'base'`. The selected
swatch is outlined in blue, and each terrain swatch is labelled with its
character and name.

The palette is live: it reflects the Terrain tab's *unsaved* palette too, so you
can define a new terrain and paint with it before saving.

### 10.4 Map readout and view controls

The line above the map reads:

```
Map 40 x 20 cells   -   path OK
```

or, in **red**, `NO PATH from S to B`. A **yellow line** previews the computed
route from `S` to `B`. **Help text:** if there is no yellow line and the message is
`NO PATH from S to B`, the level is unplayable — ground attackers cannot reach the
base. The panel also gets a red border in that state.

The route is found by a breadth-first search over **walkable** cells (terrain with
`walkable` on, plus `S` and `B`), using 4-way movement, so branching maps work.

Buttons and readouts:

| Control | Help text |
| --- | --- |
| `zoom -` / `zoom +` | Zoom out / in one step about the map centre. For trackpads without a wheel. |
| `fit map` | Zoom and pan so the whole grid is visible again, and reset the scroll to the map origin. |
| `<n> px / cell   -   <a>x<b> of <W>x<H>` | Current zoom and which portion of the map is visible. Green when the whole map fits, blue otherwise. |
| Corner mini-map | When the map is larger than the panel, a small box in the bottom-right corner outlines the whole map and the current viewport in blue. |

> **There is no "New Map", "Resize" or "Clear map" button.** To resize, type into
> `grid W` / `grid H`. To wipe the map, select the grass swatch and repaint, or
> delete the level and create a new one. (The `Clear` button below belongs to the
> **wave** builder, not the map.)
>
> Resizing **preserves** the cells that still fit and fills any new area with
> grass. It is undoable.

### 10.5 Selecting the level's units

Beneath the map:

| List | JSON key | Help text |
| --- | --- | --- |
| **Available units** | `available_units` | The level's **shop** — which defenders the player can buy. Ticked ids only. |
| **Enemy pool** | `enemy_pool` | The level's **attacker roster** — the units waves may spawn. |

Both are checkbox lists of ids, populated from `content/` each time the tab is
shown.

> **Empty means "all", not "none".** Leaving either list empty tells the game to
> use the **whole race roster** (all of the race's units / enemies) rather than no
> units at all:

### 10.6 The wave builder

**Help text:** each wave holds unit **groups**; each group is
`(unit, count, seconds between spawns)`.

**Wave list** — rows read `Wave 1: grunt x5, tank x2` (up to the first three
groups), or `Wave 1: (empty)`.

| Button | Help text |
| --- | --- |
| `Add wave` | Append a new empty wave and select it. |
| `Del wave` | Delete the selected wave. |
| `Dup wave` | Insert a copy of the selected wave directly after it. |
| `Clear` | Empty the selected wave but keep it in the list. |

**Units in selected wave** — rows read `grunt x5 @1s`.

| Button | Help text |
| --- | --- |
| `Add unit` | Add a group to the selected wave. Defaults to the first attacker in the pool, `count` 5, `gap` 1.0 s. If there are no waves at all, one is created for you. |
| `Del unit` | Remove the selected group from the wave. |

> **There is no reorder control.** Waves and groups play in **insertion order**;
> there are no up/down or drag-to-move buttons. To restructure, use `Dup wave`
> then delete the original, or rebuild the order with **Add**/**Del**. Note also
> that `Add unit` does nothing if waves exist but none is selected — select a wave
> first.

**Group fields:**

| Label | JSON key | Help text |
| --- | --- | --- |
| `unit` | group `[0]` | Which attacker to spawn. A dropdown of attacker unit ids. |
| `count` | group `[1]` | How many to spawn. Clamped to a minimum of `1`. |
| `gap` | group `[2]` | Seconds between individual spawns in this group. Clamped to a minimum of `0.0`. |

Editing any of the three fields rewrites the group immediately.

**Stored shape** — each wave is a list of 3-element lists:

```json
"waves": [
  [["grunt", 5, 1.0], ["tank", 2, 3.0]],
  [["brute", 10, 0.5]]
]
```

A reminder sits under the group fields:
`space+drag / middle / right drag pans`.

---

## 11. Setting sprite art

The art flow is identical on the **Units** and **Terrain** tabs.

### Step 1 — click the preview

Click the sprite preview box (Units: *"Sprite - click to change"*; Terrain:
*"click the icon: static image or animation"*).

### Step 2 — choose static or animation

A dialog asks **"What kind of sprite is this?"** with the subtitle
*"Static: one PNG. Animation: a spritesheet you split into states."*

| Choice | Help text |
| --- | --- |
| **Static image** *(subtitle "image")* | One PNG, drawn as-is. Falls back to being used for states that have no animation. |
| **Animation** *(subtitle "spritesheet")* | A spritesheet you slice into named states. |

Cancel or click outside to abort.

### Step 3 — pick the file

The **built-in file browser** opens, rooted at `assets/`:

* Rows list sub-directories and image files (`.png`, `.jpg`, `.jpeg`, `.bmp`,
  `.gif`).
* Click a directory to enter it; click the `..` entry to go up.
* Mouse wheel scrolls.
* Click a file to choose it.
* `Esc` or a click outside closes the browser without choosing.

Everything is stored as a path **relative to `assets/`**, e.g.
`units/woodlanders/archer.png`.

### Step 4 (animation only) — assign frames to states

The **Animation editor** opens, titled
*"Animation editor - click frames to assign them to the selected state"*.

* The sheet is shown as a grid of **numbered frames**.
* **Choose a state** — for units: `idle`, `walk`, `attack`, `death`. For terrain:
  a single looping clip called `anim` (terrain has no named states).
* **Set the frame size** (`frame_w`, `frame_h`), plus `margin` and `spacing` if
  your sheet has padding, so the grid slices correctly.
* **Click a frame** to add it to the active state; click it again to remove it.
* **Shift-click** selects the whole range since your last click — the fast way to
  grab an 8-frame walk cycle.
* **Set `fps`** (frames per second) and **`loop`** (repeat the clip or play once).
* **Change sheet** re-opens the file browser to swap the source image.

**Help text:** the engine plays the matching animation automatically — `idle` when
still, `walk` when moving, `attack` when firing, `death` when killed. A state you
leave empty **falls back to the static image, then to `idle`, then to the first
animation**, so you only need to author the states you care about.

The result is saved as a `sprites` spec holding both the static image and the
per-state animations, and the status line reports which states you defined.

### Sprite spec reference

Sprite specs are shared by units and terrain, and are one of:

```json
{"kind": "pack",  "tile": 226}
{"kind": "image", "path": "units/foo/bar.png"}
{"kind": "shape", "shape": "circle", "color": [200, 120, 120]}
{"kind": "sheet", "path": "units/foo.png", "frame_w": 32, "frame_h": 32,
 "frames": 6, "fps": 8, "loop": true, "margin": 0, "spacing": 0}
{"kind": "anim",  "fps": 8, "loop": true, "frames": [<spec>, <spec>, ...]}
```

You can hand-edit any of these in JSON; the designer reads them back losslessly.

---

## 12. Saving, undo and what lands on disk

### What Save does

1. **Syncs** the current form (and, on Levels, the wave fields and the map grid)
   into the in-memory document.
2. **Validates** — duplicate ids block the save.
3. **Writes** every entry through `ContentDB`.
4. **Prunes orphans** — files for entries you deleted are removed.
5. **Reloads** from disk, clears art caches, and clears the dirty marker.
6. Reports e.g. `Terrain: saved 9 entries`.

On **Levels**, saving additionally **re-syncs every race's level list** with the
levels that name it, sorted by each level's `order`, so `race.levels` never drifts
out of date.

### Where content lives

```
content/
  terrain.json        # every terrain entry
  units/              # one JSON per unit
  races/              # one JSON per race
  levels/             # one JSON per level
```

**The game reads these exact files**, so designer changes are live in the game on
the next launch.

### Undo in detail

**Help text:** every mutating action — paint stroke, field edit, wave edit, resize,
new/delete — stores the whole document as it was **before** the change, up to
**50 steps**. Undo puts it back into the list, the widgets *and* the map.

* A paint **stroke** is one undo step, not one per cell.
* A click on an already-correct cell records nothing, so it does not waste a step.
* **Zoom, pan and picking a different list row are not edits** and never create a
  step.
* Undo is **per tab** — the Terrain history does not undo a Levels change.

### Editing `content/` by hand

Nothing stops you. The designer is a front-end for plain JSON; keep ids unique and
terrain characters valid (`S`, `B` and space reserved) and it will load cleanly.
If a key is missing, the designer supplies a sensible default on load — and does
*not* flag the file as dirty, so merely opening an old file never marks it
unsaved.

---

## 13. Worked example: a new level

1. **Save your units first.** On the **Units** tab, create or adjust any defenders
   and attackers you need, then **Save**.
2. **Add a race** (or reuse one) on the **Races** tab: tick the defenders under
   *Available units* and the attackers under *Enemies*, pick a *base hero*, then
   **Save**.
3. **Define terrain** on the **Terrain** tab if you need new tile types. Give each
   a unique `char`, decide `buildable` / `walkable`, then **Save**.
4. Go to the **Levels** tab and click **New**. A 20×10 grid appears with `S` at the
   left of the middle row and `B` at the right.
5. Set `id`, `name` and `race` on the form.
6. Set `grid W` / `grid H` to the size you want. This resizes the canvas
   (undoably).
7. **Paint the map** — click a terrain swatch, then left-click/drag on the canvas.
   Click the `S` swatch and paint the spawn, then the `B` swatch and paint the
   base.
8. **Check the route.** The readout must say **`path OK`** and a yellow line must
   connect `S` to `B`. If it says `NO PATH from S to B`, either your `walkable`
   flags are too restrictive or the base is walled off. Use `Ctrl+Z` to undo and
   fix it.
9. **Pick the shop** — tick defenders under *Available units*.
10. **Pick the roster** — tick attackers under *Enemy pool*.
11. **Build waves** — click **Add wave**, then **Add unit**, and set `unit`,
    `count` and `gap` for each group. Add more waves for later in the level.
12. Tune `gold`, `gold / sec` and `lives` for difficulty.
13. Press **Save** (or `Ctrl+S`). The status line should read
    `Levels: saved N entries`.
14. Launch the game and pick the race — your level is in its list, ordered by
    `order`.

---

## 14. Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `ERROR: duplicate ids - not saved` | Two entries share an `id`. Rename one, then save again. |
| `ERROR: duplicate level ids - not saved` | Same, on the Levels tab. |
| `ERROR: terrain chars must be unique and not S/B` | Two terrains share a `char`, or one uses `S`, `B` or a space. These are reserved. |
| `NO PATH from S to B` (red) | No walkable route between spawn and base. Check `walkable` flags and that both `S` and `B` are actually painted. |
| A tab shows `*` but I did not change anything | The dirty marker compares against the last save. Save (or `Ctrl+Z`) to clear it. |
| My edits vanished after switching tabs | You never pressed **Save**. Content is only written on Save. |
| `--fullscreen` did nothing | You may have misspelled it, or you were already in fullscreen. Unknown flags are silently ignored — press **F11** instead. |
| Text looks soft | The fixed 1280×720 canvas is being scaled to your window. Resize closer to the canvas aspect, or use fullscreen. |
| A sprite shows as a blank/placeholder box | The PNG path is wrong, or it is outside `assets/`. Re-pick it by clicking the preview. |
| My animation only plays one state | Only that state has frames. Empty states fall back to the static image / `idle` / first animation. |
| Undo says "Nothing left to undo" | The history is per tab and capped at 50 steps, or the action (zoom/pan/selection) was never an edit. |
| `Esc` closed the whole app | `Esc` quits only when no modal is open. Close the browser/editor first, or use the window's close button. |

---

## 15. Where things live in the code

Useful if you want to extend the designer:

| File | Contents |
| --- | --- |
| `designer.py` | The entry point. Adds the repo root to `sys.path` and calls `level_designer.app.main`. |
| `level_designer/app.py` | `Designer` (window, tab bar, main loop), the `--fullscreen` flag, and every global hotkey. |
| `level_designer/tabs.py` | All five tabs: `TerrainTab`, `UnitsTab`, `RacesTab`, `MapCanvas`, `LevelsTab`, `HelpTab`, plus the shared `FormTab` / `UndoMixin`. |
| `level_designer/widgets.py` | The widget toolkit: fields, lists, `MultiSelect`, `UpgradePathEditor`, `FileBrowser`, `AnimationEditor` and the sprite flows. |
| `level_designer/layout.py` | Every rectangle on the 1280×720 canvas, so no widget can drift out of place. |
| `level_designer/history.py` | The snapshot undo/redo stacks (50 steps). |
| `core/content.py` | `ContentDB` — loading, saving and orphan pruning for `content/`. |

**Adding an option** usually means three small edits: declare the field in the
tab's `build_fields()` (or `_build_fields()` for Levels), add it to the `order` /
`place` list so it gets a rectangle, and include it in `collect()` (plus
`load_entry()` if it needs custom coercion). Terrain, Units and Levels all follow
that pattern, and the Levels group fields in `_apply_group_fields()` show the
in-place update style.

---

## See also

* [`README.md`](README.md) — project overview and the JSON content format.
* [`designer.py`](designer.py) — the launcher itself.
* The **Help** tab inside the app — a condensed, scrollable version of this guide
  (`HelpTab` in `level_designer/tabs.py:2082`).

"""Global constants and tuning knobs for bigtower."""

# --- Window / canvas -------------------------------------------------------
CANVAS_W = 1280            # internal render resolution (game logic space)
CANVAS_H = 720
FPS = 60
WINDOW_TITLE = "Big Tower"

# --- Map / tiles -----------------------------------------------------------
TILE = 64
MAP_COLS = 20              # map area: CANVAS_W x MAP_ROWS*TILE  (1280 x 640)
MAP_ROWS = 10
HUD_H = CANVAS_H - MAP_ROWS * TILE   # 80px command bar at the bottom

# --- Camera ----------------------------------------------------------------
# The map viewport is the strip of canvas above the HUD.  Levels may be far
# larger than it; the camera scrolls a map-space window over that strip.
VIEW_W = CANVAS_W
VIEW_H = CANVAS_H - HUD_H          # 640px of world visible at once
CAMERA_SPEED = 1100.0              # keyboard panning, px/second
CAMERA_EASE = 14.0                 # higher = snappier catch-up to the target
CAMERA_EDGE = 24                   # edge-scroll band, px
CAMERA_EDGE_SPEED = 900.0          # edge-scroll speed, px/second
CAMERA_DRAG_THRESHOLD = 6          # px before a left-drag counts as a map drag
MINIMAP_W = 208
MINIMAP_H = 132
MINIMAP_MARGIN = 10

# --- Colors ----------------------------------------------------------------
GRASS_GREEN = (111, 193, 82)
DIRT_BROWN = (196, 132, 66)
HUD_BG = (34, 32, 52)
HUD_LINE = (70, 66, 90)
TEXT_LIGHT = (238, 238, 238)
TEXT_DARK = (20, 20, 20)
GOLD_COLOR = (255, 205, 66)
LIFE_COLOR = (255, 92, 92)
GOOD_GREEN = (120, 220, 120)
BAD_RED = (230, 80, 80)
PANEL_BG = (24, 22, 38)
PANEL_EDGE = (120, 116, 150)

# --- Economy ---------------------------------------------------------------
START_GOLD_DEFAULT = 220
START_LIVES_DEFAULT = 20
WAVE_COUNTDOWN = 20.0      # seconds between waves (auto start)
EARLY_CALL_BONUS = 2       # gold per second remaining when calling a wave early
SELL_RATIO = 0.7           # refund fraction of total invested

# --- Unit upgrades ---------------------------------------------------------
# Defenders (player units) can be upgraded in place; these are the per-level
# multipliers applied to their base stats.  Attackers scale per wave instead.
UNIT_MAX_LEVEL = 3
UNIT_DAMAGE_GAIN = 1.6
UNIT_RANGE_GAIN = 1.12
UNIT_RATE_GAIN = 0.82
UNIT_HP_GAIN = 1.25

"""Shared geometry for the designer, in canvas pixels.

Every tab is laid out from the numbers here so nothing can drift off the
1280x720 canvas or into a neighbouring column.  The vertical bands are::

    y   0.. 32   the tab bar (owned by app.py)
    y  36.. 58   a section title per tab
    y  62..712   tab content

The three columns used by the Levels tab are the left list, the map canvas in
the middle and the level form + waves on the right; the form tabs (Terrain /
Units / Races) use just the left list and a wider form area.
"""
import pygame

# --- canvas -----------------------------------------------------------------
CANVAS_W = 1280
CANVAS_H = 720
TAB_H = 32                     # kept in sync with app.py

TITLE_Y = 36                   # section title baseline box
TOP = 62                       # first content row
BOTTOM = 712                   # last usable row (8px margin)
RIGHT_MARGIN = 16

ROW_H = 30                     # vertical pitch of a form row
FIELD_H = 26                   # drawn height of one field
COL_GAP = 16

# --- left column (lists + New / Dup / Delete / Save / Undo / Redo) ----------
LIST_X = 10
LIST_W = 296
LIST_RECT = pygame.Rect(LIST_X, TOP, LIST_W, 504)      # bottom 566
BTN_H = 28
BTN_GAP = 5
BTN_W = (LIST_W - 8) // 2                              # 144
BTN_ROWS = (566 + 8, 566 + 8 + BTN_H + BTN_GAP,
            566 + 8 + 2 * (BTN_H + BTN_GAP))           # 574 / 607 / 640
LIST_HINT_Y = 674

# --- form area (Terrain / Units / Races) -----------------------------------
FORM_X = 330
FORM_W = CANVAS_W - FORM_X - RIGHT_MARGIN              # 934


def columns(count, x, width, gap=COL_GAP):
    """``count`` evenly spaced column x positions inside ``[x, x + width]``."""
    col_w = (width - gap * (count - 1)) // count
    return col_w, [x + i * (col_w + gap) for i in range(count)]


def row_rect(row, x, width, top=TOP, pitch=ROW_H, height=FIELD_H):
    """The rect of form ``row`` in a column of the given width."""
    return pygame.Rect(x, top + row * pitch, width, height)


# --- Levels tab -------------------------------------------------------------
LEVEL_FORM_X = 848                                   # kept: right column start
LEVEL_FORM_W = CANVAS_W - LEVEL_FORM_X - RIGHT_MARGIN  # 416
LEVEL_COL_W, LEVEL_COLS = columns(2, LEVEL_FORM_X, LEVEL_FORM_W)

LEVELS_LIST_W = 250
LEVELS_LIST_RECT = pygame.Rect(LIST_X, TOP, LEVELS_LIST_W, 504)
LEVEL_BTN_W = (LEVELS_LIST_W - 8) // 2                # 121

MAP_X = 272
MAP_TOP = 84
MAP_W = 564                                          # 272 .. 836
MAP_MAX_H = 386                                      # grows/shrinks with palette

PAL_COLS = 11                                        # 11 * 48px pitch = 528px
PAL_SWATCH = 44
PAL_PITCH = 48
PAL_ROW_H = 64                                       # swatch + name label
PAL_BOTTOM = 524                                     # bottom of the swatch rows
PAL_LABEL_H = 18                                     # swatch name drawn below

ZOOM_Y = PAL_BOTTOM + PAL_LABEL_H + 6                # 548, clear of the labels
ZOOM_BTN_H = 26
ZOOM_BTN_GAP = 6
ZOOM_BTN_W = 100

SEL_LABEL_Y = ZOOM_Y + ZOOM_BTN_H + 6               # 580
SEL_TOP = SEL_LABEL_Y + 20                          # 600
SEL_H = BOTTOM - SEL_TOP                             # 112
SEL_W = (MAP_W - 12) // 2                            # 276

# right column, below the form
WAVE_LABEL_Y = 248
WAVE_LIST_RECT = pygame.Rect(LEVEL_FORM_X, 264, LEVEL_FORM_W, 124)
WAVE_BTN_Y = 394
GROUP_LABEL_Y = 426
GROUP_LIST_RECT = pygame.Rect(LEVEL_FORM_X, 442, LEVEL_FORM_W, 118)
GROUP_BTN_Y = 566
GROUP_FIELD_Y = 598
GROUP_FIELD_H = 26

# --- Units tab: upgrade-branch editor --------------------------------------
UNITS_UPGRADE_RECT = pygame.Rect(FORM_X, 460, 700, BOTTOM - 460)   # 330..1030
UNITS_PREVIEW_RECT = pygame.Rect(FORM_X + 712, 460, 222, 190)     # 1042..1264
UNITS_PREVIEW_HINT_Y = 658
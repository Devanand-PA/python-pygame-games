"""One-off diagnostic: verify the designer's sheet-tile picking is honest.

Drives the real SpriteKindDialog -> SheetTilePicker -> UnitsTab/TerrainTab
chain with synthetic mouse clicks on the actual Kenney tilesheet, then checks
that

  * the frame index reported by the picker is the cell actually under the
    cursor (the picker used to measure from ``preview.topleft`` while
    ``draw`` blits the scaled sheet *centred*, so every click landed one whole
    tile to the right);
  * the frame size the Units tab ends up saving is the sheet's own, not the
    form's untouched 32x32 default;
  * the pixels the designer shows are the tiles the user clicked.

Run it with::

    .venv/bin/python tools/sheet_pick_check.py

Not part of a test suite; a behavioural regression check for issue #64.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from core.content import ContentDB
from engine import art
from level_designer import tabs as T
from level_designer.app import Designer

KENNEY = "packs/kenney_tower-defense-top-down/Tilesheet/towerDefense_tilesheet.png"


def pixel_key(surf, size=40):
    return hash(pygame.image.tobytes(art.sprite(surf, size), "RGBA"))


def click_at_modal(pos):
    d.ctx.modal.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                                {"button": 1, "pos": pos}))


def run_flow(tab, opener, apply, col, row):
    """Dialog -> 'Sheet tile' -> click cell (col,row) -> applied spec."""
    chosen = []
    opener()
    dialog = d.ctx.modal
    button = [b for b in dialog.buttons if b[2] == "sheet"][0]
    click_at_modal(button[0].center)

    picker = d.ctx.modal
    previous = picker.on_result
    picker.on_result = lambda spec: (chosen.append(spec), previous(spec),
                                     apply(spec))
    click_at_modal(picker._cell_rect(col, row).center)
    return chosen[-1] if chosen else None


def terrain_spec_of(tab):
    return tab._sprite_spec(tab.fields["base_kind"].value,
                            tab.fields["base_tile"].value,
                            tab.fields["base_path"].value,
                            tab.fields["base_fw"].value,
                            tab.fields["base_fh"].value,
                            tab._base_frames,
                            tab.fields["base_fps"].value,
                            tab.fields["base_loop"].value,
                            tab._base_margin, tab._base_spacing)


def main():
    global d
    d = Designer()

    failures = []

    # --- 1. the picker's grid must line up with the artwork it draws -------
    picker = T.W.SheetTilePicker(d.ctx, d.sheets_tab.items, lambda s: None)
    sheet = next(s for s in d.sheets_tab.items if s.get("path") == KENNEY)
    surf = art.image(sheet["path"])
    grid = picker._grid(sheet, surf)
    fw, fh, spacing, margin, cols, rows, scale = grid
    ox, oy = picker._shown_origin(surf, scale)
    for col, row in ((0, 0), (1, 0), (2, 0), (5, 3), (10, 6), (22, 12)):
        want = row * cols + col
        x = ox + (margin + col * (fw + spacing)) * scale + fw * scale / 2
        y = oy + (margin + row * (fh + spacing)) * scale + fh * scale / 2
        got = picker._cell_at((x, y))
        if got is None or got[2] != want:
            failures.append("picker cell ({},{}): got {}, want {}".format(
                col, row, None if got is None else got[2], want))

    # --- 2. a real click through both flows -------------------------------
    def check(name, tab, opener, apply, build, col, row, cell_index):
        spec = run_flow(tab, opener, apply, col, row)
        if spec is None:
            failures.append("{}: picker returned no spec".format(name))
            return
        saved = build()
        if spec["frames"] != [cell_index]:
            failures.append("{}: picked frames {}, want [{}]".format(
                name, spec["frames"], cell_index))
        if saved.get("frame_w") != 64 or saved.get("frame_h") != 64:
            failures.append("{}: saved frame {}x{}, want 64x64".format(
                name, saved.get("frame_w"), saved.get("frame_h")))
        if pixel_key(saved) != pixel_key(spec):
            failures.append("{}: saved art differs from the clicked tile".format(
                name))

    terrain = d.terrain_tab
    terrain.list.index = 0
    terrain._on_select(0)
    check("terrain", terrain, lambda: terrain._open_flow("base"),
          lambda s: terrain._apply_spec("base", s),
          lambda: terrain_spec_of(terrain), 5, 3, 74)

    units = d.units_tab
    units.list.index = 0
    units._on_select(0)
    check("units", units, lambda: units._open_sprite_flow(),
          lambda s: units._apply_sprite_spec(s),
          lambda: units.collect()["sprite"], 5, 3, 74)

    # --- 3. adjacent cells must not collapse onto the same sprite ---------
    terrain.list.index = 0
    terrain._on_select(0)
    seen = set()
    for col in range(4):
        spec = run_flow(terrain, lambda: terrain._open_flow("base"),
                        lambda s: terrain._apply_spec("base", s), col, 0)
        if spec is None:
            failures.append("terrain row 0: click {} gave no spec".format(col))
            continue
        seen.add(pixel_key(spec))
    if len(seen) != 4:
        failures.append("terrain: {} distinct sprites for 4 adjacent "
                        "clicks".format(len(seen)))

    units.list.index = 0
    units._on_select(0)
    seen = set()
    for col in range(4):
        spec = run_flow(units, lambda: units._open_sprite_flow(),
                        lambda s: units._apply_sprite_spec(s), col, 0)
        if spec is None:
            failures.append("units row 0: click {} gave no spec".format(col))
            continue
        seen.add(pixel_key(spec))
    if len(seen) != 4:
        failures.append("units: {} distinct sprites for 4 adjacent "
                        "clicks".format(len(seen)))

    # --- 4. the sprite cache must not serve a recycled surface ------------
    art.clear_caches()
    frames = []
    for index in (0, 1, 2):
        frames.append(art.sprite({"kind": "sheet", "path": KENNEY,
                                  "frame_w": 64, "frame_h": 64,
                                  "frames": [index]}, 40))
    if len({hash(pygame.image.tobytes(f, "RGBA")) for f in frames}) != 3:
        failures.append("art.scaled reused a surface across frames "
                        "(id() cache collision)")

    d.running = False

    if failures:
        print("FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print("sheet pick check: all good")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""One-off diagnostic: detect all overlapping UI regions in every designer tab.

Monkeypatches the tabs module's text helpers and every field's draw to record
the exact rectangles painted during a real draw pass, then reports every pair
of regions that intersect.  Not part of the test suite; a layout fixing tool.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pygame

import level_designer.tabs as T
from level_designer import layout as L

RECORD = []


def _record(rect, what):
    RECORD.append((pygame.Rect(rect), what))


def build_detector():
    # patch the text helpers
    orig_text = T._text
    orig_right = T._right_text

    def text(ctx, s, pos, color=T.W.TEXT, key="small"):
        surf = ctx.fonts[key].render(str(s), True, color)
        _record((pos[0], pos[1], surf.get_width(), surf.get_height()),
                "text:" + str(s)[:34])
        orig_text(ctx, s, pos, color, key)

    def right(ctx, s, right_x, y, color=T.W.TEXT, key="small"):
        surf = ctx.fonts[key].render(str(s), True, color)
        _record((right_x - surf.get_width(), y, surf.get_width(),
                 surf.get_height()), "rtext:" + str(s)[:34])
        orig_right(ctx, s, right_x, y, color, key)

    T._text = text
    T._right_text = right

    # patch every Field subclass draw to record its rect
    for name in dir(T.W):
        cls = getattr(T.W, name)
        if isinstance(cls, type) and issubclass(cls, T.W.Field):
            orig_draw = cls.draw

            def make(orig, cname):
                def draw(self, canvas):
                    _record(self.rect, "field:" + cname + "/" + str(self.label))
                    orig(self, canvas)
                return draw
            cls.draw = make(orig_draw, name)


def collect_static(tab):
    """Buttons / lists / known composite regions of a tab."""
    out = []
    for attr in ("buttons", "list_buttons", "zoom_buttons", "path_buttons",
                 "wave_buttons", "group_buttons", "item_buttons",
                 "section_buttons", "line_buttons"):
        for b in getattr(tab, attr, []) or []:
            if attr == "line_buttons" and getattr(tab, "section", None) != 3:
                continue
            out.append((b.rect, "btn:" + b.text))
    for attr in ("list", "item_list", "line_list", "wave_list", "group_list"):
        w = getattr(tab, attr, None)
        if w is None:
            continue
        # the Script tab's line editor only exists in the checkpoint section
        if attr in ("line_list",) and getattr(tab, "section", None) not in (3,):
            continue
        out.append((w.rect, "list:" + attr))
    for attr in ("units_sel", "enemies_sel", "avail_sel", "enemy_sel"):
        w = getattr(tab, attr, None)
        if w is not None:
            out.append((w.rect, "multisel:" + attr))
    for attr in ("upgrade_editor", "map"):
        w = getattr(tab, attr, None)
        if w is not None and hasattr(w, "rect"):
            out.append((w.rect, "panel:" + attr))
    # singletons: the Sheets tab's detect button and preview panel
    btn = getattr(tab, "detect_btn", None)
    if btn is not None:
        out.append((btn.rect, "btn:detect tile size"))
    prev = getattr(tab, "preview_rect", None)
    if prev is not None:
        out.append((prev, "panel:sheet preview"))
    if hasattr(tab, "_base_preview_rect"):
        out.append((tab._base_preview_rect(), "preview:base"))
        out.append((tab._overlay_preview_rect(), "preview:overlay"))
    return out


def scan(d, index, name, tab, extra_draw=None):
    RECORD.clear()
    for rect, what in collect_static(tab):
        _record(rect, what)
    tab.draw()
    if extra_draw is not None:
        extra_draw()
    report = []
    for i in range(len(RECORD)):
        for j in range(i + 1, len(RECORD)):
            a, b = RECORD[i], RECORD[j]
            if not a[0].width or not b[0].width:
                continue
            # composite fields (ImageField / TileField / ColorField) draw
            # their inner widgets inside their own rect - contained is fine
            if a[0].contains(b[0]) or b[0].contains(a[0]):
                continue
            if a[1].startswith("panel:") or b[1].startswith("panel:"):
                continue
            clip = a[0].clip(b[0])
            if clip.width <= 2 or clip.height <= 2:
                continue
            report.append((clip.width * clip.height, a, b))
    print("=" * 70)
    print("TAB", name, "-", len(RECORD), "regions,", len(report), "overlaps")
    for area, a, b in sorted(report, reverse=True)[:40]:
        print("  {:>6}px2  {!r} {}  <->  {!r} {}".format(
            area, a[1], tuple(a[0]), b[1], tuple(b[0])))


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    from level_designer.app import Designer
    build_detector()
    d = Designer()
    names = [n for n, _ in d.tabs]

    for index, name in enumerate(names):
        d.set_tab(index)
        tab = d.tabs[index][1]
        if name == "Script":
            # sweep the slide section and the checkpoint section
            tab._switch_section(0)()
            scan(d, index, name + " (slides)", tab)
            tab._switch_section(3)()
            tab.add_item()          # a checkpoint on screen exercises lines
            scan(d, index, name + " (checkpoints)", tab)
        else:
            scan(d, index, name, tab)


if __name__ == "__main__":
    main()

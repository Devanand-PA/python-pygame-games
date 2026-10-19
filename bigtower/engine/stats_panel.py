"""Stat read-outs for units.

The pause/game HUD used to only explain a unit *after* it was on the field,
which made choosing what to deploy guesswork.  These helpers render the same
numbers straight from a :class:`core.content.UnitType`, so the shop can show a
full preview -- including what an upgrade would buy -- before any gold is
spent.

Level scaling mirrors :class:`engine.units.Unit` exactly (the same
``S.UNIT_*_GAIN`` multipliers), so a preview and the real unit never disagree.
"""
import pygame

from core import settings as S
from engine import art

LABEL_COLOR = (168, 168, 190)
VALUE_COLOR = (226, 226, 238)
PREVIEW_COLOR = (126, 196, 126)
DIM_COLOR = (128, 128, 148)
ACCENT = (120, 150, 210)

ROW_H = 17
PAD = 10
HEADER_H = 46


def scaled_stats(utype, paths=()):
    """Stats for ``utype`` after taking the given upgrade branches.

    ``paths`` is a sequence of normalised branch dicts (``{"gains": {...}}``).
    Mirrors :class:`engine.units.Unit` so a preview never disagrees with the
    unit the player actually gets.
    """
    paths = list(paths or [])
    mult = {"damage": 1.0, "range": 1.0, "rate": 1.0, "hp": 1.0}
    shots = utype.projectiles
    for path in paths:
        gains = path.get("gains", {})
        for key in mult:
            mult[key] *= gains.get(key, 1.0)
        shots += gains.get("projectiles", 0)
    cooldown = max(0.01, utype.cooldown * mult["rate"])
    damage = utype.damage * mult["damage"]
    return {
        "hp": max(1, int(round(utype.hp * mult["hp"]))),
        "damage": damage,
        "range": utype.range * mult["range"],
        "rate": 1.0 / cooldown,
        "dps": damage / cooldown,
        "shots": max(1, int(shots)),
    }


def describe_gains(gains):
    """A short human summary of what one upgrade branch does."""
    bits = []
    for key, label in (("damage", "damage"), ("hp", "hp")):
        if key in gains:
            bits.append("+{:.0f}% {}".format((gains[key] - 1) * 100, label))
    if "range" in gains:
        bits.append("+{:.0f}% range".format((gains["range"] - 1) * 100))
    if "rate" in gains:
        bits.append("+{:.0f}% rate".format((1.0 / gains["rate"] - 1) * 100))
    if gains.get("projectiles"):
        n = int(gains["projectiles"])
        bits.append("+{} shot{}".format(n, "" if n == 1 else "s"))
    return ", ".join(bits)


def _fmt(value):
    if isinstance(value, float):
        return "{:.1f}".format(value)
    return str(value)


def stat_rows(utype, show_upgrades=True):
    """``(label, value, preview)`` rows for a unit type.

    There is no single "next level" any more -- the player picks a branch --
    so the preview column is dropped and the branches are listed separately by
    :func:`path_rows`.
    """
    base = scaled_stats(utype)
    rows = [
        ("HP", _fmt(base["hp"]), ""),
        ("Damage", _fmt(base["damage"]), ""),
        ("Range", _fmt(base["range"]), ""),
        ("Rate", "{}/s".format(_fmt(base["rate"])), ""),
        ("DPS", _fmt(base["dps"]), ""),
    ]
    if base["shots"] > 1:
        rows.append(("Shots", str(base["shots"]), ""))
    if utype.splash > 0:
        rows.append(("Splash", _fmt(utype.splash), ""))
    return rows


def path_rows(utype):
    """``(branch name, what it does)`` for every upgrade branch."""
    return [(p["name"], describe_gains(p["gains"]))
            for p in utype.upgrade_paths]


def behaviour_text(utype):
    """The one-line movement/targeting summary shown under the stat grid."""
    if utype.movement == "chase":
        move = "hunts enemies"
    elif utype.movement == "static":
        move = "holds position"
    elif utype.movement == "route":
        move = "follows the path"
    elif utype.movement == "direct":
        move = "flies straight at the base"
    elif utype.movement == "hunt":
        move = "leaves the path to attack"
    else:
        move = utype.movement
    bits = [move]
    if utype.attack != "none":
        bits.append("{} ({})".format(utype.attack, utype.targets))
    else:
        bits.append("no attack")
    if utype.is_flying:
        bits.insert(0, "flying")
    if utype.speed > 0 and utype.movement not in ("static",):
        bits.append("{:.0f} px/s".format(utype.speed))
    return "  ".join(bits)


def panel_height(utype, show_upgrades=True):
    rows = stat_rows(utype, show_upgrades)
    height = (HEADER_H + PAD + len(rows) * ROW_H + PAD + 20
              + (34 if utype.description else 0))
    if show_upgrades and utype.is_defender:
        height += 10 + ROW_H * (1 + len(path_rows(utype)))
    return height


def draw_tooltip(canvas, rect, utype, fonts, *, race_tint=None,
                 affordable=True, show_upgrades=True, hotkey=None):
    """Render a pre-deployment stat card for ``utype`` into ``rect``."""
    pygame.draw.rect(canvas, (16, 16, 26), rect, border_radius=8)
    pygame.draw.rect(canvas, ACCENT if affordable else S.BAD_RED, rect, 2,
                     border_radius=8)

    inner_x = rect.x + PAD
    inner_w = rect.width - PAD * 2
    title_font = fonts["default"]
    small = fonts["small"]

    # --- header: sprite + name + cost ---------------------------------------
    name = title_font.render(utype.name, True, S.TEXT_LIGHT)
    canvas.blit(name, (inner_x + 42, rect.y + 8))
    cost_color = S.GOLD_COLOR if affordable else S.BAD_RED
    cost = title_font.render("${}".format(utype.cost), True, cost_color)
    canvas.blit(cost, (rect.right - PAD - cost.get_width(), rect.y + 8))
    if utype.role:
        role = small.render(utype.role.upper(), True, DIM_COLOR)
        canvas.blit(role, (inner_x + 42, rect.y + 30))

    try:
        sprite = art.sprite(utype.sprite, 34, race_tint)
    except Exception:                      # a broken sprite must not kill the HUD
        sprite = None
    if sprite is not None:
        canvas.blit(sprite, sprite.get_rect(topleft=(inner_x, rect.y + 8)))

    if hotkey:
        key = small.render("[{}]".format(hotkey), True, DIM_COLOR)
        canvas.blit(key, (rect.right - PAD - key.get_width(), rect.y + 30))

    y = rect.y + HEADER_H
    pygame.draw.line(canvas, (58, 58, 80), (inner_x, y), (inner_x + inner_w, y))
    y += PAD - 2

    value_x = inner_x + inner_w - 96
    preview_x = inner_x + inner_w
    for label, value, preview in stat_rows(utype, show_upgrades):
        canvas.blit(small.render(label, True, LABEL_COLOR), (inner_x, y))
        canvas.blit(small.render(value, True, VALUE_COLOR), (value_x, y))
        if preview:
            hint = small.render("->{}".format(preview), True, PREVIEW_COLOR)
            canvas.blit(hint, (preview_x - hint.get_width(), y))
        y += ROW_H

    y += 2
    behaviour = small.render(behaviour_text(utype), True, DIM_COLOR)
    canvas.blit(behaviour, (inner_x, y))
    y += ROW_H + 4

    if utype.description:
        desc = small.render(_ellipsis(utype.description, small, inner_w),
                            True, (150, 150, 172))
        canvas.blit(desc, (inner_x, y))
        y += ROW_H

    if show_upgrades and utype.is_defender:
        y += 4
        pygame.draw.line(canvas, (58, 58, 80), (inner_x, y), (inner_x + inner_w, y))
        y += 6
        head = "Upgrade paths ({} steps to Lv{})".format(
            max(0, S.UNIT_MAX_LEVEL - 1), S.UNIT_MAX_LEVEL)
        canvas.blit(small.render(head, True, ACCENT), (inner_x, y))
        y += ROW_H
        for name, effect in path_rows(utype):
            canvas.blit(small.render(name, True, VALUE_COLOR), (inner_x, y))
            canvas.blit(small.render(_ellipsis(effect, small, inner_w - 104),
                                     True, PREVIEW_COLOR),
                        (inner_x + 104, y))
            y += ROW_H
    return rect


def _ellipsis(text, font, max_w):
    if font.size(text)[0] <= max_w:
        return text
    while text and font.size(text + "...")[0] > max_w:
        text = text[:-1]
    return text + "..."
"""The designer's tabs: Terrain, Units, Races, Levels and Help.

Each tab owns a working list of plain dicts (mirroring the JSON on disk), a
list panel to pick one, and a form of widgets to edit it.  Saving writes every
entry back through :class:`core.content.ContentDB` and removes orphaned files.
"""
from collections import deque

import pygame

from engine import art
from level_designer import widgets as W

FORM_X = 330
FORM_TOP = 64
ROW_H = 34
COL_GAP = 24
LIST = pygame.Rect(10, 54, 300, 700)


def _text(ctx, s, pos, color=W.TEXT, key="small"):
    surf = ctx.fonts[key].render(str(s), True, color)
    ctx.canvas.blit(surf, pos)


class FormTab:
    """List of entries on the left, an editable form on the right."""

    title = "Form"
    folder = "units"
    save_fn = "save_unit"

    def __init__(self, app):
        self.app = app
        self.ctx = app.ctx
        self.items = list(self.load_items())
        self.current = None
        self.fields = {}
        self.extras = {}
        self._col_w = (app.canvas.get_width() - FORM_X - 24 - COL_GAP) // 2
        self.list = W.ScrollList(self.ctx, LIST, [], on_select=self._on_select)
        bw = (LIST.width - 16) // 2
        self.buttons = [
            W.Btn(self.ctx, (LIST.x, LIST.bottom + 8, bw, 30), "New", self.new),
            W.Btn(self.ctx, (LIST.x + bw + 8, LIST.bottom + 8, bw, 30), "Dup", self.duplicate),
            W.Btn(self.ctx, (LIST.x, LIST.bottom + 44, bw, 30), "Delete", self.delete, color=(90, 54, 54)),
            W.Btn(self.ctx, (LIST.x + bw + 8, LIST.bottom + 44, bw, 30), "Save", self.save, color=(64, 92, 70)),
        ]
        self.build_fields()
        self.refresh()

    # -- to be provided by subclasses --------------------------------------
    def load_items(self):
        raise NotImplementedError

    def entry_label(self, item):
        return str(item.get("id", "?"))

    def default_entry(self):
        return {"id": "new"}

    def build_fields(self):
        raise NotImplementedError

    def load_entry(self, item):
        for name, field in self.fields.items():
            if name in item:
                field.set_value(item[name])

    def collect(self):
        return {name: field.value for name, field in self.fields.items()}

    def persist(self, item):
        getattr(self.app.content, self.save_fn)(item)

    @staticmethod
    def item_id(item):
        return item.get("id")

    # -- layout -------------------------------------------------------------
    def place(self, name, col, row, span=1, label_w=None):
        width = self._col_w * span + COL_GAP * (span - 1)
        rect = pygame.Rect(FORM_X + col * (self._col_w + COL_GAP),
                           FORM_TOP + row * ROW_H, width, ROW_H - 4)
        field = self.fields[name]
        field.set_rect(rect)
        if label_w is not None:
            field.label_w = label_w
        return field

    # -- list ops -----------------------------------------------------------
    def refresh(self, select=None):
        self.list.set_items([self.entry_label(i) for i in self.items], keep=False)
        if select is not None and select in self.items:
            self.list.index = self.items.index(select)
            self.list._clamp()
        elif self.items:
            self.list.index = min(self.list.index if self.list.index >= 0 else 0,
                                  len(self.items) - 1)
        self.current = self._item_at(self.list.index)
        if self.current is not None:
            self.load_entry(self.current)

    def _item_at(self, index):
        if self.items and 0 <= index < len(self.items):
            return self.items[index]
        return None

    def _on_select(self, label):
        self.apply_current()
        if 0 <= self.list.index < len(self.items):
            self.current = self.items[self.list.index]
            self.load_entry(self.current)

    def apply_current(self):
        if self.current is None or self.current not in self.items:
            return
        data = dict(self.current)
        data.update(self.collect())
        idx = self.items.index(self.current)
        self.items[idx] = data
        self.current = data

    # -- buttons ------------------------------------------------------------
    def new(self):
        self.apply_current()
        data = self.default_entry()
        ids = {self.item_id(i) for i in self.items}
        base = data["id"]
        n = 2
        while data["id"] in ids:
            data["id"] = f"{base}_{n}"
            n += 1
        self.items.append(data)
        self.refresh(select=data)
        self.app.set_status("{}: created '{}'".format(self.title, data["id"]))

    def duplicate(self):
        if self.current is None:
            return
        self.apply_current()
        data = dict(self.current)
        ids = {self.item_id(i) for i in self.items}
        base = str(data["id"]) + "_copy"
        new_id = base
        n = 2
        while new_id in ids:
            new_id = f"{base}_{n}"
            n += 1
        data["id"] = new_id
        data["name"] = str(data.get("name", new_id)) + " copy"
        self.items.append(data)
        self.refresh(select=data)
        self.app.set_status("{}: duplicated".format(self.title))

    def delete(self):
        if self.current is None:
            return
        item = self.current
        self.items.remove(item)
        self.current = None
        self.refresh()
        self.app.content.delete_orphans(self.folder, {self.item_id(i) for i in self.items})
        self.app.set_status("{}: deleted '{}'".format(self.title, self.item_id(item)))

    def save(self):
        self.apply_current()
        if not self.validate():
            return
        for item in self.items:
            self.persist(item)
        self.app.content.delete_orphans(self.folder, {self.item_id(i) for i in self.items})
        self.app.content.reload()
        art.clear_caches()
        self.app.set_status("{}: saved {} entries".format(self.title, len(self.items)))

    def validate(self):
        ids = [self.item_id(i) for i in self.items]
        if len(ids) != len(set(ids)):
            self.app.set_status("ERROR: duplicate ids - not saved", W.BAD)
            return False
        return True

    # -- events / draw ------------------------------------------------------
    def handle_event(self, event):
        if self.list.handle_event(event):
            return True
        for b in self.buttons:
            if b.handle_event(event):
                return True
        for field in self.fields.values():
            if field.handle_event(event):
                return True
        return False

    def draw(self):
        self.ctx.canvas.fill((0, 0, 0))
        _text(self.ctx, self.title, (FORM_X, FORM_TOP - 30), W.TEXT, "big")
        _text(self.ctx, "{} entries".format(len(self.items)),
              (FORM_X + 200, FORM_TOP - 24), W.DIM)
        self.list.draw(self.ctx.canvas)
        for b in self.buttons:
            b.draw(self.ctx.canvas)
        for field in self.fields.values():
            field.draw(self.ctx.canvas)


# ===========================================================================
# terrain
# ===========================================================================
TERRAIN_BASE_KINDS = ("pack", "image", "sheet")
TERRAIN_OVERLAY_KINDS = ("none", "pack", "image", "sheet")


class TerrainTab(FormTab):
    title = "Terrain"
    folder = "terrain"
    save_fn = "save_terrain_entry"

    def load_items(self):
        return [t.to_dict() for t in self.app.content.terrains]

    def entry_label(self, item):
        return "{} [{}] {}".format(item.get("id"), item.get("char"),
                                   item.get("name", ""))

    def default_entry(self):
        return {"id": "new_terrain", "name": "New Terrain", "char": "?",
                "base": 157, "overlay": None, "sprite": None,
                "overlay_sprite": None, "buildable": True,
                "walkable": True, "tint": None, "description": ""}

    def build_fields(self):
        f = self.fields
        self._loaded_sprite = None
        self._loaded_overlay = None
        self._base_frames = None
        self._overlay_frames = None
        f["id"] = W.TextField(self.ctx, (0, 0, 0, 0), "id")
        f["name"] = W.TextField(self.ctx, (0, 0, 0, 0), "name")
        f["char"] = W.TextField(self.ctx, (0, 0, 0, 0), "grid char (1 char)")
        # -- base ground art --
        f["base_kind"] = W.ChoiceField(self.ctx, (0, 0, 0, 0), "base kind",
                                       TERRAIN_BASE_KINDS)
        f["base_tile"] = W.TileField(self.ctx, (0, 0, 0, 0), "base tile")
        f["base_path"] = W.ImageField(self.ctx, (0, 0, 0, 0), "base png")
        f["base_fw"] = W.IntField(self.ctx, (0, 0, 0, 0), "base frame w", 32)
        f["base_fh"] = W.IntField(self.ctx, (0, 0, 0, 0), "base frame h", 32)
        f["base_frames"] = W.IntField(self.ctx, (0, 0, 0, 0), "base frames", 1)
        f["base_fps"] = W.FloatField(self.ctx, (0, 0, 0, 0), "base fps", 8.0)
        f["base_loop"] = W.CheckField(self.ctx, (0, 0, 0, 0), "base loop", True)
        # -- overlay (rocks, bushes, decals) --
        f["overlay_kind"] = W.ChoiceField(self.ctx, (0, 0, 0, 0), "overlay kind",
                                          TERRAIN_OVERLAY_KINDS)
        f["overlay_tile"] = W.TileField(self.ctx, (0, 0, 0, 0), "overlay tile",
                                        optional=True)
        f["overlay_path"] = W.ImageField(self.ctx, (0, 0, 0, 0), "overlay png")
        f["ov_fw"] = W.IntField(self.ctx, (0, 0, 0, 0), "overlay frame w", 32)
        f["ov_fh"] = W.IntField(self.ctx, (0, 0, 0, 0), "overlay frame h", 32)
        f["ov_frames"] = W.IntField(self.ctx, (0, 0, 0, 0), "overlay frames", 1)
        f["ov_fps"] = W.FloatField(self.ctx, (0, 0, 0, 0), "overlay fps", 8.0)
        f["ov_loop"] = W.CheckField(self.ctx, (0, 0, 0, 0), "overlay loop", True)
        # -- rules --
        f["buildable"] = W.CheckField(self.ctx, (0, 0, 0, 0), "buildable")
        f["walkable"] = W.CheckField(self.ctx, (0, 0, 0, 0), "walkable")
        f["tint_enabled"] = W.CheckField(self.ctx, (0, 0, 0, 0), "custom tint")
        f["tint"] = W.ColorField(self.ctx, (0, 0, 0, 0), "tint RGB")
        f["description"] = W.TextField(self.ctx, (0, 0, 0, 0), "description")
        order = ["id", "name", "char", "base_kind", "base_tile", "base_path",
                 "base_fw", "base_fh", "base_frames", "base_fps", "base_loop",
                 "overlay_kind", "overlay_tile", "overlay_path", "ov_fw", "ov_fh",
                 "ov_frames", "ov_fps", "ov_loop", "buildable", "walkable",
                 "tint_enabled", "tint", "description"]
        for idx, name in enumerate(order):
            self.place(name, idx % 2, idx // 2)

    @staticmethod
    def _sprite_spec(kind, tile, path, fw, fh, frames, fps, loop):
        if kind == "image":
            return {"kind": "image", "path": path}
        if kind == "sheet":
            value = frames if isinstance(frames, (list, tuple)) else max(1, frames)
            return {"kind": "sheet", "path": path,
                    "frame_w": max(1, fw), "frame_h": max(1, fh),
                    "frames": value, "fps": max(0.1, fps),
                    "loop": bool(loop)}
        return {"kind": "pack", "tile": tile}

    def load_entry(self, item):
        super().load_entry(item)
        spec = item.get("sprite") or {"kind": "pack", "tile": item.get("base", 157)}
        self._loaded_sprite = spec
        kind = spec.get("kind", "pack")
        self._base_frames = (list(spec.get("frames")) if isinstance(spec.get("frames"), list)
                             else None)
        self.fields["base_kind"].set_value(kind if kind in TERRAIN_BASE_KINDS else "pack")
        self.fields["base_tile"].set_value(spec.get("tile", item.get("base", 157)))
        self.fields["base_path"].set_value(spec.get("path", ""))
        self.fields["base_fw"].set_value(spec.get("frame_w", 32))
        self.fields["base_fh"].set_value(spec.get("frame_h", 32))
        self.fields["base_frames"].set_value(spec.get("frames", 1))
        self.fields["base_fps"].set_value(spec.get("fps", 8.0))
        self.fields["base_loop"].set_value(spec.get("loop", True))

        overlay = item.get("overlay_sprite")
        if overlay is None and item.get("overlay") is not None:
            overlay = {"kind": "pack", "tile": item["overlay"]}
        self._loaded_overlay = overlay
        self._overlay_frames = (list(overlay.get("frames"))
                                if isinstance(overlay, dict)
                                and isinstance(overlay.get("frames"), list) else None)
        if overlay is None:
            self.fields["overlay_kind"].set_value("none")
            self.fields["overlay_tile"].set_value(-1)
            self.fields["overlay_path"].set_value("")
            self.fields["ov_fw"].set_value(32)
            self.fields["ov_fh"].set_value(32)
            self.fields["ov_frames"].set_value(1)
            self.fields["ov_fps"].set_value(8.0)
            self.fields["ov_loop"].set_value(True)
        else:
            okind = overlay.get("kind", "pack")
            self.fields["overlay_kind"].set_value(
                okind if okind in TERRAIN_OVERLAY_KINDS else "pack")
            self.fields["overlay_tile"].set_value(
                overlay.get("tile", item.get("overlay") or -1))
            self.fields["overlay_path"].set_value(overlay.get("path", ""))
            self.fields["ov_fw"].set_value(overlay.get("frame_w", 32))
            self.fields["ov_fh"].set_value(overlay.get("frame_h", 32))
            self.fields["ov_frames"].set_value(overlay.get("frames", 1))
            self.fields["ov_fps"].set_value(overlay.get("fps", 8.0))
            self.fields["ov_loop"].set_value(overlay.get("loop", True))

        self.fields["buildable"].set_value(item.get("buildable", True))
        self.fields["walkable"].set_value(item.get("walkable", True))
        self.fields["tint_enabled"].set_value(item.get("tint") is not None)
        self.fields["tint"].set_value(item.get("tint") or [128, 200, 128])

    def collect(self):
        f = self.fields
        base_kind = f["base_kind"].value
        base_tile = f["base_tile"].value
        base_frames = (self._base_frames if isinstance(self._base_frames, list)
                       else f["base_frames"].value)
        data = {
            "id": f["id"].value,
            "name": f["name"].value,
            "char": (f["char"].value or "?")[:1],
            "base": base_tile,
            "sprite": (self._sprite_spec(base_kind, base_tile, f["base_path"].value,
                                         f["base_fw"].value, f["base_fh"].value,
                                         base_frames, f["base_fps"].value,
                                         f["base_loop"].value)
                       if base_kind != "pack" else None),
            "buildable": f["buildable"].value,
            "walkable": f["walkable"].value,
            "tint": f["tint"].value if f["tint_enabled"].value else None,
            "description": f["description"].value,
        }
        okind = f["overlay_kind"].value
        otile = f["overlay_tile"].value
        ov_frames = (self._overlay_frames if isinstance(self._overlay_frames, list)
                     else f["ov_frames"].value)
        if okind == "none":
            data["overlay"] = None
            data["overlay_sprite"] = None
        else:
            data["overlay"] = otile
            data["overlay_sprite"] = (self._sprite_spec(okind, otile, f["overlay_path"].value,
                                                        f["ov_fw"].value, f["ov_fh"].value,
                                                        ov_frames, f["ov_fps"].value,
                                                        f["ov_loop"].value)
                                      if okind != "pack" else None)
        return data

    def save(self):
        self.apply_current()
        chars = [i.get("char") for i in self.items]
        if len(set(chars)) != len(chars) or any(c in ("S", "B", " ") for c in chars):
            self.app.set_status("ERROR: terrain chars must be unique and not S/B", W.BAD)
            return
        self.app.content.save_terrain(self.items)
        self.app.content.reload()
        art.clear_caches()
        self.app.set_status("Terrain: saved {} entries".format(len(self.items)))

    def _base_preview_rect(self):
        return pygame.Rect(FORM_X, FORM_TOP + 12 * ROW_H + 10, 130, 130)

    def _overlay_preview_rect(self):
        return pygame.Rect(FORM_X, FORM_TOP + 12 * ROW_H + 156, 130, 96)

    def handle_event(self, event):
        if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.current is not None):
            if self._base_preview_rect().collidepoint(event.pos):
                self._open_flow("base")
                return True
            if self._overlay_preview_rect().collidepoint(event.pos):
                self._open_flow("overlay")
                return True
        return super().handle_event(event)

    def _open_flow(self, which):
        if which == "base":
            current = self._sprite_spec(
                self.fields["base_kind"].value, self.fields["base_tile"].value,
                self.fields["base_path"].value, self.fields["base_fw"].value,
                self.fields["base_fh"].value, self._base_frames
                if isinstance(self._base_frames, list)
                else self.fields["base_frames"].value,
                self.fields["base_fps"].value, self.fields["base_loop"].value)
            W.open_terrain_sprite_flow(self.ctx, current,
                                       lambda spec: self._apply_spec("base", spec))
        else:
            current = self._sprite_spec(
                self.fields["overlay_kind"].value, self.fields["overlay_tile"].value,
                self.fields["overlay_path"].value, self.fields["ov_fw"].value,
                self.fields["ov_fh"].value, self._overlay_frames
                if isinstance(self._overlay_frames, list)
                else self.fields["ov_frames"].value,
                self.fields["ov_fps"].value, self.fields["ov_loop"].value)
            W.open_terrain_sprite_flow(self.ctx, current,
                                       lambda spec: self._apply_spec("overlay", spec))

    def _apply_spec(self, which, spec):
        f = self.fields
        kind = spec.get("kind", "pack")
        frames = spec.get("frames")
        frame_list = frames if isinstance(frames, list) else None
        count = len(frame_list) if frame_list else (
            frames if isinstance(frames, int) else max(1, int(frames or 1)))
        if which == "base":
            f["base_kind"].set_value(kind if kind in TERRAIN_BASE_KINDS else "pack")
            f["base_path"].set_value(spec.get("path", ""))
            if kind == "pack":
                f["base_tile"].set_value(spec.get("tile", 157))
            f["base_fw"].set_value(spec.get("frame_w", 32))
            f["base_fh"].set_value(spec.get("frame_h", 32))
            f["base_frames"].set_value(count)
            f["base_fps"].set_value(spec.get("fps", 8.0))
            f["base_loop"].set_value(spec.get("loop", True))
            self._base_frames = frame_list
            if kind == "image":
                self._base_frames = None
        else:
            f["overlay_kind"].set_value(kind if kind in TERRAIN_OVERLAY_KINDS else "pack")
            f["overlay_path"].set_value(spec.get("path", ""))
            if kind == "pack":
                f["overlay_tile"].set_value(spec.get("tile", 1))
            f["ov_fw"].set_value(spec.get("frame_w", 32))
            f["ov_fh"].set_value(spec.get("frame_h", 32))
            f["ov_frames"].set_value(count)
            f["ov_fps"].set_value(spec.get("fps", 8.0))
            f["ov_loop"].set_value(spec.get("loop", True))
            self._overlay_frames = frame_list
        self.app.set_status("{} sprite: {}".format(which, kind))

    def draw(self):
        super().draw()
        if self.current is None:
            return
        data = self.collect()
        tint = data.get("tint")
        t = pygame.time.get_ticks() / 1000.0

        base = data.get("sprite") or {"kind": "pack", "tile": data.get("base", 157)}
        preview = self._base_preview_rect()
        pygame.draw.rect(self.ctx.canvas, W.PANEL, preview, border_radius=6)
        pygame.draw.rect(self.ctx.canvas, W.ACCENT, preview, 2, border_radius=6)
        try:
            img = art.sprite(base, 138, tint, frame=art.frame_index(base, t))
            self.ctx.canvas.blit(img, img.get_rect(center=preview.center))
        except Exception:      # noqa: BLE001
            pass
        _text(self.ctx, "Base terrain art", (preview.right + 14, preview.y + 8),
              W.TEXT)
        _text(self.ctx, "click the icon: static image or animation",
              (preview.right + 14, preview.y + 30), W.ACCENT)
        if art.frame_count(base) > 1:
            _text(self.ctx, "{} frames @ {:g} fps".format(
                art.frame_count(base), art.fps(base)),
                (preview.right + 14, preview.y + 52), W.OK)

        overlay = data.get("overlay_sprite")
        if overlay is None and data.get("overlay") is not None:
            overlay = {"kind": "pack", "tile": data["overlay"]}
        oprev = self._overlay_preview_rect()
        pygame.draw.rect(self.ctx.canvas, W.PANEL, oprev, border_radius=6)
        pygame.draw.rect(self.ctx.canvas, W.ACCENT, oprev, 2, border_radius=6)
        pygame.draw.rect(self.ctx.canvas, W.BG, oprev.inflate(-8, -8), border_radius=4)
        try:
            img = art.sprite(overlay or {"kind": "pack", "tile": data.get("base", 157)},
                             72, tint, frame=art.frame_index(
                                 overlay or base, t))
            self.ctx.canvas.blit(img, img.get_rect(center=oprev.center))
        except Exception:      # noqa: BLE001
            pass
        _text(self.ctx, "Overlay (rocks / decals)", (oprev.right + 14, oprev.y + 8),
              W.TEXT)
        if overlay is None:
            _text(self.ctx, "none - click to add", (oprev.right + 14, oprev.y + 30),
                  W.DIM)
        else:
            _text(self.ctx, "click to change", (oprev.right + 14, oprev.y + 30),
                  W.ACCENT)
            if art.frame_count(overlay) > 1:
                _text(self.ctx, "{} frames @ {:g} fps".format(
                    art.frame_count(overlay), art.fps(overlay)),
                    (oprev.right + 14, oprev.y + 52), W.OK)


# ===========================================================================
# units
# ===========================================================================
SPRITE_KINDS = ("pack", "image", "shape", "sheet", "anim", "sprites")
SHAPES = ("circle", "square", "diamond", "triangle")
MOVEMENTS = ("static", "chase", "route", "direct", "hunt")
ATTACKS = ("none", "melee", "projectile")
TARGETS = ("both", "ground", "air")
TARGETING = ("", "nearest", "first", "strongest", "weakest")
SIDES = ("defender", "attacker")
PROJECTILES = ("dot", "rocket")
SOUNDS = ("gun", "sting", "missile", "sniper", "laser", "zap")


class UnitsTab(FormTab):
    title = "Units"
    folder = "units"
    save_fn = "save_unit"

    def load_items(self):
        return [u.to_dict() for u in self.app.content.units.values()]

    def entry_label(self, item):
        return "[{}] {}".format(item.get("side", "?")[:3], item.get("name", item.get("id")))

    def default_entry(self):
        return {"id": "new_unit", "name": "New Unit", "side": "defender",
                "role": "", "sprite": {"kind": "pack", "tile": 226},
                "projectile_sprite": None, "sprite_scale": 1.0, "tint": None,
                "hp": 100, "cost": 50, "bounty": 0, "speed": 0.0,
                "movement": "static", "attack": "none", "range": 120.0,
                "damage": 5.0, "cooldown": 0.5, "projectile": "dot", "splash": 0.0,
                "sound": "gun", "targets": "both", "targeting": "",
                "is_flying": False, "damage_to_base": 1, "stop_to_attack": True,
                "aggro": 160.0, "radius": 16.0, "can_be_attacked": True,
                "description": ""}

    def build_fields(self):
        f = self.fields
        self._loaded_spec = None
        self._sprite_full = None
        f["id"] = W.TextField(self.ctx, (0, 0, 0, 0), "id")
        f["name"] = W.TextField(self.ctx, (0, 0, 0, 0), "name")
        f["side"] = W.ChoiceField(self.ctx, (0, 0, 0, 0), "side", SIDES)
        f["role"] = W.TextField(self.ctx, (0, 0, 0, 0), "role")
        f["sprite_kind"] = W.ChoiceField(self.ctx, (0, 0, 0, 0), "sprite kind", SPRITE_KINDS)
        f["sprite_tile"] = W.TileField(self.ctx, (0, 0, 0, 0), "sprite tile")
        f["sprite_path"] = W.ImageField(self.ctx, (0, 0, 0, 0), "image / sheet png")
        f["sprite_shape"] = W.ChoiceField(self.ctx, (0, 0, 0, 0), "shape", SHAPES)
        f["sprite_color"] = W.ColorField(self.ctx, (0, 0, 0, 0), "shape colour")
        f["frame_w"] = W.IntField(self.ctx, (0, 0, 0, 0), "frame w", 32)
        f["frame_h"] = W.IntField(self.ctx, (0, 0, 0, 0), "frame h", 32)
        f["sprite_frames"] = W.IntField(self.ctx, (0, 0, 0, 0), "frame count", 1)
        f["sprite_fps"] = W.FloatField(self.ctx, (0, 0, 0, 0), "anim fps", 8.0)
        f["sprite_loop"] = W.CheckField(self.ctx, (0, 0, 0, 0), "loop", True)
        f["sprite_scale"] = W.FloatField(self.ctx, (0, 0, 0, 0), "sprite scale")
        f["tint_enabled"] = W.CheckField(self.ctx, (0, 0, 0, 0), "custom tint")
        f["tint"] = W.ColorField(self.ctx, (0, 0, 0, 0), "tint RGB")
        f["hp"] = W.IntField(self.ctx, (0, 0, 0, 0), "hp")
        f["cost"] = W.IntField(self.ctx, (0, 0, 0, 0), "cost (defender)")
        f["bounty"] = W.IntField(self.ctx, (0, 0, 0, 0), "bounty (attacker)")
        f["speed"] = W.FloatField(self.ctx, (0, 0, 0, 0), "speed (0=static)")
        f["movement"] = W.ChoiceField(self.ctx, (0, 0, 0, 0), "movement", MOVEMENTS)
        f["attack"] = W.ChoiceField(self.ctx, (0, 0, 0, 0), "attack", ATTACKS)
        f["range"] = W.FloatField(self.ctx, (0, 0, 0, 0), "range")
        f["damage"] = W.FloatField(self.ctx, (0, 0, 0, 0), "damage")
        f["cooldown"] = W.FloatField(self.ctx, (0, 0, 0, 0), "cooldown (s)")
        f["projectile"] = W.ChoiceField(self.ctx, (0, 0, 0, 0), "projectile", PROJECTILES)
        f["splash"] = W.FloatField(self.ctx, (0, 0, 0, 0), "splash radius")
        f["sound"] = W.ChoiceField(self.ctx, (0, 0, 0, 0), "sound", SOUNDS)
        f["targets"] = W.ChoiceField(self.ctx, (0, 0, 0, 0), "targets", TARGETS)
        f["targeting"] = W.ChoiceField(self.ctx, (0, 0, 0, 0), "targeting", TARGETING)
        f["is_flying"] = W.CheckField(self.ctx, (0, 0, 0, 0), "is flying")
        f["damage_to_base"] = W.IntField(self.ctx, (0, 0, 0, 0), "dmg to base")
        f["stop_to_attack"] = W.CheckField(self.ctx, (0, 0, 0, 0), "stop to attack")
        f["aggro"] = W.FloatField(self.ctx, (0, 0, 0, 0), "aggro radius")
        f["radius"] = W.FloatField(self.ctx, (0, 0, 0, 0), "body radius")
        f["can_be_attacked"] = W.CheckField(self.ctx, (0, 0, 0, 0), "attackable")
        f["description"] = W.TextField(self.ctx, (0, 0, 0, 0), "description")

        order = ["id", "name", "side", "role",
                 "sprite_kind", "sprite_tile", "sprite_path", "sprite_shape",
                 "sprite_color", "frame_w", "frame_h", "sprite_frames",
                 "sprite_fps", "sprite_loop", "sprite_scale", "tint_enabled",
                 "tint", "hp", "cost", "bounty", "speed", "movement", "attack",
                 "range", "damage", "cooldown", "projectile", "splash", "sound",
                 "targets", "targeting", "is_flying", "damage_to_base",
                 "stop_to_attack", "aggro", "radius", "can_be_attacked",
                 "description"]
        for idx, name in enumerate(order):
            self.place(name, idx % 2, idx // 2)

    def _spec_from_fields(self):
        """Build a sprite spec from the current form values (for live preview)."""
        f = self.fields
        kind = f["sprite_kind"].value
        tile = f["sprite_tile"].value
        path = f["sprite_path"].value
        shape = f["sprite_shape"].value
        color = f["sprite_color"].value
        fps = max(0.1, f["sprite_fps"].value)
        loop = bool(f["sprite_loop"].value)
        if kind == "sprites":
            return self._sprite_full or {"kind": "sprites", "image": None,
                                         "animations": {}}
        if kind == "image":
            return {"kind": "image", "path": path}
        if kind == "shape":
            return {"kind": "shape", "shape": shape, "color": color}
        if kind == "sheet":
            return {"kind": "sheet", "path": path,
                    "frame_w": max(1, f["frame_w"].value),
                    "frame_h": max(1, f["frame_h"].value),
                    "frames": max(1, f["sprite_frames"].value),
                    "fps": fps, "loop": loop}
        if kind == "anim":
            frames = (self._loaded_spec or {}).get("frames") \
                if isinstance(self._loaded_spec, dict) else None
            return {"kind": "anim", "fps": fps, "loop": loop,
                    "frames": frames or [{"kind": "pack", "tile": tile}]}
        return {"kind": "pack", "tile": tile}

    def load_entry(self, item):
        for name in ("id", "name", "side", "role", "sprite_scale", "hp", "cost",
                     "bounty", "speed", "movement", "attack", "range", "damage",
                     "cooldown", "projectile", "splash", "sound", "targets",
                     "targeting", "is_flying", "damage_to_base", "stop_to_attack",
                     "aggro", "radius", "can_be_attacked", "description"):
            self.fields[name].set_value(item.get(name))
        spec = item.get("sprite") or {"kind": "pack", "tile": 226}
        self._loaded_spec = spec
        kind = spec.get("kind", "pack")
        self._sprite_full = spec if kind == "sprites" else None
        self.fields["sprite_kind"].set_value(kind if kind in SPRITE_KINDS else "pack")
        self.fields["sprite_tile"].set_value(spec.get("tile", 226))
        self.fields["sprite_path"].set_value(spec.get("path", ""))
        self.fields["sprite_shape"].set_value(spec.get("shape", "circle"))
        self.fields["sprite_color"].set_value(spec.get("color") or [200, 200, 200])
        self.fields["frame_w"].set_value(spec.get("frame_w", 32))
        self.fields["frame_h"].set_value(spec.get("frame_h", 32))
        frames = spec.get("frames")
        count = len(frames) if kind == "anim" and isinstance(frames, list) else spec.get("frames", 1)
        self.fields["sprite_frames"].set_value(count if isinstance(count, int) else 1)
        self.fields["sprite_fps"].set_value(spec.get("fps", 8.0))
        self.fields["sprite_loop"].set_value(spec.get("loop", True))
        self.fields["tint_enabled"].set_value(item.get("tint") is not None)
        self.fields["tint"].set_value(item.get("tint") or [255, 255, 255])

    def collect(self):
        data = {name: field.value for name, field in self.fields.items()}
        for helper in ("sprite_kind", "sprite_tile", "sprite_path", "sprite_shape",
                       "sprite_color", "frame_w", "frame_h", "sprite_frames",
                       "sprite_fps", "sprite_loop"):
            data.pop(helper, None)
        data["sprite"] = self._spec_from_fields()
        data["tint"] = data.pop("tint") if data.pop("tint_enabled") else None
        return data

    def _preview_rect(self):
        return pygame.Rect(FORM_X, FORM_TOP + 19 * ROW_H + 6, 130, 130)

    def handle_event(self, event):
        if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.current is not None
                and self._preview_rect().collidepoint(event.pos)):
            self._open_sprite_flow()
            return True
        return super().handle_event(event)

    def _open_sprite_flow(self):
        W.open_unit_sprite_flow(self.ctx, self._spec_from_fields(),
                                self._apply_sprite_spec)

    def _apply_sprite_spec(self, spec):
        kind = spec.get("kind", "pack")
        self.fields["sprite_kind"].set_value(kind if kind in SPRITE_KINDS else "pack")
        self._sprite_full = spec if kind == "sprites" else None
        if kind == "sprites":
            self.fields["sprite_path"].set_value(
                (spec.get("image") or {}).get("path", ""))
            self.fields["sprite_tile"].set_value(
                (spec.get("image") or {}).get("tile", 226))
            states = ", ".join(art.animation_names(spec)) or "none"
            self.app.set_status("Sprite: animations ({})".format(states))
        else:
            self.fields["sprite_path"].set_value(spec.get("path", ""))
            self.fields["sprite_tile"].set_value(spec.get("tile", 226))
            self.app.set_status("Sprite: {}".format(kind))
        if self.current is not None:
            self.current["sprite"] = spec

    def draw(self):
        super().draw()
        # live sprite preview, top-right of the form (click it to set the art)
        if self.current is None:
            return
        spec = self._spec_from_fields()
        tint = (self.fields["tint"].value
                if self.fields["tint_enabled"].value else None)
        preview = self._preview_rect()
        pygame.draw.rect(self.ctx.canvas, W.PANEL, preview, border_radius=6)
        pygame.draw.rect(self.ctx.canvas, W.ACCENT, preview, 2, border_radius=6)
        try:
            t = pygame.time.get_ticks() / 1000.0
            img = art.sprite(spec, 110, tint, frame=art.frame_index(spec, t))
            self.ctx.canvas.blit(img, img.get_rect(center=preview.center))
        except Exception:      # noqa: BLE001
            pass
        hint_x = preview.right + 14
        _text(self.ctx, "Sprite (click to change)", (hint_x, preview.y + 8), W.TEXT)
        _text(self.ctx, "click the icon: static image or animation",
              (hint_x, preview.y + 30), W.ACCENT)
        states = art.animation_names(spec)
        if states:
            _text(self.ctx, "animation states: " + ", ".join(states),
                  (hint_x, preview.y + 54), W.OK)
        else:
            n = art.frame_count(spec)
            extra = "{} frames @ {:g} fps".format(n, art.fps(spec)) if n > 1 else \
                "static {}".format(spec.get("kind", "pack"))
            _text(self.ctx, extra, (hint_x, preview.y + 54), W.DIM)


# ===========================================================================
# races
# ===========================================================================
class RacesTab(FormTab):
    title = "Races"
    folder = "races"
    save_fn = "save_race"

    def load_items(self):
        return [dict(r) for r in self.app.content.races.values()]

    def entry_label(self, item):
        return item.get("name", item.get("id"))

    def default_entry(self):
        return {"id": "new_race", "name": "New Race", "description": "",
                "color": [120, 200, 140], "tint": None, "order": 99,
                "units": [], "enemies": [], "levels": []}

    def build_fields(self):
        f = self.fields
        f["id"] = W.TextField(self.ctx, (0, 0, 0, 0), "id")
        f["name"] = W.TextField(self.ctx, (0, 0, 0, 0), "name")
        f["order"] = W.IntField(self.ctx, (0, 0, 0, 0), "menu order")
        f["color_enabled"] = W.CheckField(self.ctx, (0, 0, 0, 0), "theme colour")
        f["color"] = W.ColorField(self.ctx, (0, 0, 0, 0), "colour RGB")
        f["tint_enabled"] = W.CheckField(self.ctx, (0, 0, 0, 0), "unit tint")
        f["tint"] = W.ColorField(self.ctx, (0, 0, 0, 0), "tint RGB")
        f["description"] = W.TextField(self.ctx, (0, 0, 0, 0), "description")
        self.place("id", 0, 0)
        self.place("name", 1, 0)
        self.place("order", 0, 1)
        self.place("description", 1, 1, label_w=110)
        self.place("color_enabled", 0, 2)
        self.place("color", 1, 2)
        self.place("tint_enabled", 0, 3)
        self.place("tint", 1, 3)

        self.units_sel = W.MultiSelect(
            self.ctx, (FORM_X, FORM_TOP + 4 * ROW_H + 30, self._col_w, 220))
        self.enemies_sel = W.MultiSelect(
            self.ctx, (FORM_X + self._col_w + COL_GAP, FORM_TOP + 4 * ROW_H + 30,
                       self._col_w, 220))

    def load_entry(self, item):
        super().load_entry(item)
        self.fields["color_enabled"].set_value(True)
        self.fields["color"].set_value(item.get("color") or [120, 200, 140])
        self.fields["tint_enabled"].set_value(item.get("tint") is not None)
        self.fields["tint"].set_value(item.get("tint") or [200, 240, 200])
        defenders = [(u.id, u.name) for u in self.app.content.sorted_units("defender")]
        attackers = [(u.id, u.name) for u in self.app.content.sorted_units("attacker")]
        self.units_sel.set_options(defenders, item.get("units") or [])
        self.enemies_sel.set_options(attackers, item.get("enemies") or [])

    def collect(self):
        data = {name: field.value for name, field in self.fields.items()}
        data["color"] = data.pop("color") if data.pop("color_enabled") else [120, 200, 140]
        data["tint"] = data.pop("tint") if data.pop("tint_enabled") else None
        data["units"] = self.units_sel.value
        data["enemies"] = self.enemies_sel.value
        return data

    def handle_event(self, event):
        if self.units_sel.handle_event(event) or self.enemies_sel.handle_event(event):
            return True
        return super().handle_event(event)

    def draw(self):
        super().draw()
        _text(self.ctx, "Available units (defenders)",
              (FORM_X, FORM_TOP + 4 * ROW_H + 10))
        _text(self.ctx, "Enemies",
              (FORM_X + self._col_w + COL_GAP, FORM_TOP + 4 * ROW_H + 10))
        self.units_sel.draw(self.ctx.canvas)
        self.enemies_sel.draw(self.ctx.canvas)
        # levels belonging to this race (managed from the Levels tab)
        if self.current is not None:
            y = FORM_TOP + 4 * ROW_H + 260
            levels = [l["id"] for l in self.app.content.levels.values()
                      if l.get("race") == self.current.get("id")]
            _text(self.ctx, "Levels for this race: {} (edit on the Levels tab)"
                  .format(", ".join(sorted(levels)) or "none"), (FORM_X, y), W.DIM)


# ===========================================================================
# levels
# ===========================================================================
CELL = 28
MAX_CELL = 28              # never draw the map larger than this
MIN_CELL = 4               # below this the map is too small to read
MAP_RECT = pygame.Rect(264, 64, 20 * CELL, 10 * CELL)
PALETTE_Y = MAP_RECT.bottom + 10
AVAIL_RECT = pygame.Rect(264, PALETTE_Y + 92, 272, 200)
ENEMY_RECT = pygame.Rect(264 + 288, PALETTE_Y + 92, 272, 200)
LEVEL_FORM_X = 848
LEVEL_COL = (1280 - LEVEL_FORM_X - 16 - 12) // 2


class MapCanvas:
    def __init__(self, ctx, app, rect):
        self.ctx = ctx
        self.app = app
        self.rect = pygame.Rect(rect)
        self.cell = CELL
        self.width = rect.width // CELL
        self.height = rect.height // CELL
        self.grid = [["g"] * self.width for _ in range(self.height)]
        self.selected = "g"
        self.painting = False
        self._tile_cache = {}
        self.path = []
        self.path_ok = False
        self.fits = True
        self._dirty = True
        self._fit_cell()

    def set_grid(self, rows):
        rows = list(rows or [])
        if rows:                       # adopt the level's real dimensions
            self.width = max(1, max(len(r) for r in rows))
            self.height = max(1, len(rows))
        self.grid = []
        for y in range(self.height):
            row = list(rows[y]) if y < len(rows) else []
            self.grid.append((row + ["g"] * self.width)[:self.width])
        self._fit_cell()
        self._dirty = True

    def rows(self):
        return ["".join(r) for r in self.grid]

    def _fit_cell(self):
        """Scale the tile size so the whole grid stays inside the view rect.

        Levels can be far larger than the designer's fixed map panel, so the
        cells shrink instead of the panel growing over the unit lists.
        """
        cell = min(self.rect.width // max(1, self.width),
                   self.rect.height // max(1, self.height))
        cell = max(MIN_CELL, min(MAX_CELL, cell))
        if cell != self.cell:
            self.cell = cell
            self._tile_cache = {}       # tiles are rasterised at cell size
        self.fits = (self.width * self.cell <= self.rect.width
                     and self.height * self.cell <= self.rect.height)

    def resize(self, width, height):
        width, height = max(1, int(width)), max(1, int(height))
        new = [["g"] * width for _ in range(height)]
        for y in range(min(height, self.height)):
            for x in range(min(width, self.width)):
                new[y][x] = self.grid[y][x]
        self.grid = new
        self.width, self.height = width, height
        self._fit_cell()
        self._dirty = True

    def _cell_at(self, pos):
        if not self.rect.collidepoint(pos):
            return None
        return ((pos[0] - self.rect.x) // self.cell,
                (pos[1] - self.rect.y) // self.cell)

    def paint(self, cell, char):
        if cell is None:
            return
        x, y = cell
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        if char in ("S", "B"):
            for j in range(self.height):
                for i in range(self.width):
                    if self.grid[j][i] == char:
                        self.grid[j][i] = "g"
        self.grid[y][x] = char
        self._dirty = True

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos):
            self.painting = True
            self.paint(self._cell_at(event.pos),
                       "g" if event.button == 3 else self.selected)
            return True
        if event.type == pygame.MOUSEBUTTONUP:
            self.painting = False
        if event.type == pygame.MOUSEMOTION and self.painting:
            self.paint(self._cell_at(event.pos), self.selected)
            return True
        return False

    def terrain_at(self, ch):
        return self.app.terrain_lookup().get(ch)

    def recompute_path(self):
        lookup = self.app.terrain_lookup()
        spawn = base = None
        for y in range(self.height):
            for x in range(self.width):
                ch = self.grid[y][x]
                if ch == "S":
                    spawn = (x, y)
                elif ch == "B":
                    base = (x, y)

        def walkable(x, y):
            ch = self.grid[y][x]
            if ch in ("S", "B"):
                return True
            terr = lookup.get(ch)
            return bool(terr and terr.get("walkable", True))

        self.path, self.path_ok = [], False
        if spawn and base:
            prev = {spawn: None}
            q = deque([spawn])
            while q:
                cur = q.popleft()
                if cur == base:
                    break
                cx, cy = cur
                for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
                    n = (cx + dx, cy + dy)
                    if n in prev or not (0 <= n[0] < self.width and 0 <= n[1] < self.height):
                        continue
                    if not walkable(*n):
                        continue
                    prev[n] = cur
                    q.append(n)
            if base in prev:
                order = []
                node = base
                while node is not None:
                    order.append(node)
                    node = prev[node]
                self.path = order
                self.path_ok = True
        self._dirty = False

    def invalidate(self):
        self._tile_cache.clear()
        self._dirty = True

    def _tile(self, ch):
        if ch in self._tile_cache:
            return self._tile_cache[ch]
        lookup = self.app.terrain_lookup()
        terr = lookup.get(ch) or lookup.get("g") or {}
        spec = terr.get("sprite") or {"kind": "pack", "tile": terr.get("base", 157)}
        self._tile_cache[ch] = art.sprite(spec, self.cell, terr.get("tint"))
        return self._tile_cache[ch]

    def draw(self):
        if self._dirty:
            self.recompute_path()
        canvas = self.ctx.canvas
        pygame.draw.rect(canvas, (10, 10, 14), self.rect)
        for y in range(self.height):
            for x in range(self.width):
                ch = self.grid[y][x]
                px = self.rect.x + x * self.cell
                py = self.rect.y + y * self.cell
                if ch in ("S", "B"):
                    canvas.blit(self._tile("g"), (px, py))
                    pad = art.scaled(art.tile(133 if ch == "S" else 180),
                                     (self.cell, self.cell))
                    canvas.blit(pad, (px, py))
                else:
                    canvas.blit(self._tile(ch), (px, py))
        # path preview
        if len(self.path) > 1:
            pts = [(self.rect.x + (x + 0.5) * self.cell,
                    self.rect.y + (y + 0.5) * self.cell) for x, y in self.path]
            pygame.draw.lines(canvas, (255, 240, 120), False, pts, 2)
        else:
            pygame.draw.rect(canvas, (200, 60, 60), self.rect, 2)
        for x in range(self.width + 1):
            pygame.draw.line(canvas, (255, 255, 255, 30),
                             (self.rect.x + x * self.cell, self.rect.y),
                             (self.rect.x + x * self.cell, self.rect.bottom), 1)


class LevelsTab:
    """Full level editor: paint the map, pick units, build waves."""

    title = "Levels"
    folder = "levels"
    save_fn = "save_level"

    def __init__(self, app):
        self.app = app
        self.ctx = app.ctx
        self.items = [dict(l) for l in app.content.levels.values()]
        self.current = None
        self.list = W.ScrollList(self.ctx, LIST, [], on_select=self._on_select)
        bw = (LIST.width - 16) // 2
        self.list_buttons = [
            W.Btn(self.ctx, (LIST.x, LIST.bottom + 8, bw, 30), "New", self.new),
            W.Btn(self.ctx, (LIST.x + bw + 8, LIST.bottom + 8, bw, 30), "Dup", self.duplicate),
            W.Btn(self.ctx, (LIST.x, LIST.bottom + 44, bw, 30), "Delete", self.delete, color=(90, 54, 54)),
            W.Btn(self.ctx, (LIST.x + bw + 8, LIST.bottom + 44, bw, 30), "Save", self.save, color=(64, 92, 70)),
        ]
        self.map = MapCanvas(self.ctx, app, MAP_RECT)
        self.fields = {}
        self._build_fields()
        self.avail_sel = W.MultiSelect(self.ctx, AVAIL_RECT)
        self.enemy_sel = W.MultiSelect(self.ctx, ENEMY_RECT)
        self.wave_list = W.ScrollList(self.ctx, (LEVEL_FORM_X, 258, 400, 132),
                                      [], on_select=self._on_wave)
        self.group_list = W.ScrollList(self.ctx, (LEVEL_FORM_X, 452, 400, 120),
                                       [], on_select=self._on_group)
        self.wave_buttons = [
            W.Btn(self.ctx, (LEVEL_FORM_X, 396, 96, 26), "Add wave", self.add_wave),
            W.Btn(self.ctx, (LEVEL_FORM_X + 104, 396, 96, 26), "Del wave", self.del_wave),
            W.Btn(self.ctx, (LEVEL_FORM_X + 208, 396, 96, 26), "Dup wave", self.dup_wave),
            W.Btn(self.ctx, (LEVEL_FORM_X + 312, 396, 88, 26), "Clear", self.clear_wave),
        ]
        self.group_buttons = [
            W.Btn(self.ctx, (LEVEL_FORM_X, 578, 96, 26), "Add unit", self.add_group),
            W.Btn(self.ctx, (LEVEL_FORM_X + 104, 578, 96, 26), "Del unit", self.del_group),
        ]
        self.g_unit = W.ChoiceField(self.ctx, (LEVEL_FORM_X, 610, 190, 30), "unit", [], label_w=40)
        self.g_count = W.IntField(self.ctx, (LEVEL_FORM_X + 200, 610, 100, 30), "count", 1, label_w=52)
        self.g_interval = W.FloatField(self.ctx, (LEVEL_FORM_X + 305, 610, 95, 30), "gap", 1.0,
                                       label_w=32)
        self.refresh()
        self._refresh_waves()

    # -- fields -------------------------------------------------------------
    def on_show(self):
        """Re-read terrain + unit/race lists when the tab becomes visible."""
        self.map.invalidate()
        self.fields["race"].options = [r["id"] for r in self.app.content.sorted_races()]

    def _build_fields(self):
        f = self.fields
        f["id"] = W.TextField(self.ctx, (0, 0, 0, 0), "id", label_w=70)
        f["name"] = W.TextField(self.ctx, (0, 0, 0, 0), "name", label_w=70)
        f["race"] = W.ChoiceField(self.ctx, (0, 0, 0, 0), "race", [], label_w=70)
        f["gold"] = W.IntField(self.ctx, (0, 0, 0, 0), "gold", label_w=70)
        f["lives"] = W.IntField(self.ctx, (0, 0, 0, 0), "lives", label_w=70)
        f["order"] = W.IntField(self.ctx, (0, 0, 0, 0), "order", label_w=70)
        f["terrain_tint_enabled"] = W.CheckField(self.ctx, (0, 0, 0, 0), "map tint", label_w=70)
        f["terrain_tint"] = W.ColorField(self.ctx, (0, 0, 0, 0), "tint RGB", label_w=70)
        f["width"] = W.IntField(self.ctx, (0, 0, 0, 0), "grid W", label_w=70)
        f["height"] = W.IntField(self.ctx, (0, 0, 0, 0), "grid H", label_w=70)
        rows = [("id", 0, 0), ("name", 1, 0), ("race", 0, 1), ("order", 1, 1),
                ("gold", 0, 2), ("lives", 1, 2), ("terrain_tint_enabled", 0, 3),
                ("terrain_tint", 1, 3), ("width", 0, 4), ("height", 1, 4)]
        for name, col, row in rows:
            rect = pygame.Rect(LEVEL_FORM_X + col * (LEVEL_COL + 12),
                               64 + row * ROW_H, LEVEL_COL, ROW_H - 4)
            f[name].set_rect(rect)

    def load_items(self):
        return [dict(l) for l in self.app.content.levels.values()]

    def entry_label(self, item):
        return "{} [{}]".format(item.get("name", item.get("id")), item.get("race", "?"))

    def default_entry(self):
        grid = [["g"] * 20 for _ in range(10)]
        grid[5][0] = "S"
        grid[5][19] = "B"
        race = self.app.content.sorted_races()
        return {"id": "new_level", "race": race[0]["id"] if race else "",
                "name": "New Level", "description": "", "gold": 200, "lives": 20,
                "order": 99, "grid": ["".join(r) for r in grid],
                "terrain_tint": None, "available_units": [], "enemy_pool": [],
                "waves": []}

    # -- helpers ------------------------------------------------------------
    def refresh(self, select=None):
        self.list.set_items([self.entry_label(i) for i in self.items], keep=False)
        if select is not None and select in self.items:
            self.list.index = self.items.index(select)
        elif self.items:
            self.list.index = max(0, min(self.list.index, len(self.items) - 1))
        self.current = self.items[self.list.index] if (
            self.items and 0 <= self.list.index < len(self.items)) else None
        if self.current is not None:
            self._load_entry(self.current)

    def _on_select(self, _label):
        self.apply_current()
        if 0 <= self.list.index < len(self.items):
            self.current = self.items[self.list.index]
            self._load_entry(self.current)

    def _load_entry(self, item):
        f = self.fields
        f["id"].set_value(item.get("id"))
        f["name"].set_value(item.get("name"))
        f["gold"].set_value(item.get("gold", 200))
        f["lives"].set_value(item.get("lives", 20))
        f["order"].set_value(item.get("order", 0))
        f["terrain_tint_enabled"].set_value(item.get("terrain_tint") is not None)
        f["terrain_tint"].set_value(item.get("terrain_tint") or [255, 255, 255])
        f["race"].options = [r["id"] for r in self.app.content.sorted_races()]
        f["race"].set_value(item.get("race"))
        self.map.resize(len(item.get("grid", ["g" * 20])[0]) if item.get("grid") else 20,
                        len(item.get("grid")) if item.get("grid") else 10)
        self.map.set_grid(item.get("grid") or [])
        f["width"].set_value(self.map.width)
        f["height"].set_value(self.map.height)
        self.avail_sel.set_options(
            [(u.id, u.name) for u in self.app.content.sorted_units("defender")],
            item.get("available_units") or [])
        self.enemy_sel.set_options(
            [(u.id, u.name) for u in self.app.content.sorted_units("attacker")],
            item.get("enemy_pool") or [])
        self.wave_index = 0
        self.group_index = 0
        self._refresh_waves()

    def apply_current(self):
        if self.current is None or self.current not in self.items:
            return
        data = dict(self.current)
        data["id"] = self.fields["id"].value
        data["name"] = self.fields["name"].value
        data["gold"] = self.fields["gold"].value
        data["lives"] = self.fields["lives"].value
        data["order"] = self.fields["order"].value
        data["race"] = self.fields["race"].value
        data["terrain_tint"] = (self.fields["terrain_tint"].value
                                if self.fields["terrain_tint_enabled"].value else None)
        data["grid"] = self.map.rows()
        data["available_units"] = self.avail_sel.value
        data["enemy_pool"] = self.enemy_sel.value
        idx = self.items.index(self.current)
        self.items[idx] = data
        self.current = data

    # -- waves --------------------------------------------------------------
    def _waves(self):
        return self.current.setdefault("waves", []) if self.current else []

    def _refresh_waves(self, keep_wave=True, keep_group=True):
        waves = self._waves()
        labels = []
        for i, groups in enumerate(waves):
            desc = ", ".join("{}x{}".format(g[0], g[1]) for g in groups[:3])
            labels.append("Wave {}: {}".format(i + 1, desc or "(empty)"))
        self.wave_list.set_items(labels, keep=False)
        if waves:
            self.wave_list.index = max(0, min(getattr(self, "wave_index", 0), len(waves) - 1))
        else:
            self.wave_list.index = -1
        self._on_wave(None)

    def _on_wave(self, _label):
        waves = self._waves()
        idx = self.wave_list.index
        self.wave_index = max(0, idx)
        groups = waves[idx] if 0 <= idx < len(waves) else []
        labels = ["{} x{} @{}s".format(g[0], g[1], g[2]) for g in groups]
        self.group_list.set_items(labels, keep=False)
        if groups:
            self.group_list.index = min(getattr(self, "group_index", 0), len(groups) - 1)
        else:
            self.group_list.index = -1
        self._on_group(None)

    def _on_group(self, _label):
        waves = self._waves()
        idx = self.wave_list.index
        groups = waves[idx] if 0 <= idx < len(waves) else []
        gidx = self.group_list.index
        self.group_index = max(0, gidx)
        self.g_unit.options = [u.id for u in self.app.content.sorted_units("attacker")]
        if 0 <= gidx < len(groups):
            uid, count, interval = groups[gidx]
            self.g_unit.set_value(uid)
            self.g_count.set_value(count)
            self.g_interval.set_value(interval)

    def _apply_group_fields(self):
        waves = self._waves()
        idx = self.wave_list.index
        if not (0 <= idx < len(waves)):
            return
        gidx = self.group_list.index
        if not (0 <= gidx < len(waves[idx])):
            return
        waves[idx][gidx] = [self.g_unit.value, max(1, self.g_count.value),
                            max(0.0, self.g_interval.value)]
        self._refresh_waves()

    def add_wave(self):
        self._waves().append([])
        self.wave_index = len(self._waves()) - 1
        self.group_index = 0
        self._refresh_waves()

    def del_wave(self):
        waves = self._waves()
        if 0 <= self.wave_list.index < len(waves):
            waves.pop(self.wave_list.index)
        self._refresh_waves()

    def dup_wave(self):
        waves = self._waves()
        if 0 <= self.wave_list.index < len(waves):
            waves.insert(self.wave_list.index + 1,
                         [list(g) for g in waves[self.wave_list.index]])
        self._refresh_waves()

    def clear_wave(self):
        waves = self._waves()
        if 0 <= self.wave_list.index < len(waves):
            waves[self.wave_list.index] = []
        self._refresh_waves()

    def add_group(self):
        waves = self._waves()
        idx = self.wave_list.index
        if not (0 <= idx < len(waves)):
            if not waves:
                waves.append([])
                idx = 0
            else:
                return
        options = [u.id for u in self.app.content.sorted_units("attacker")]
        waves[idx].append([options[0] if options else "grunt", 5, 1.0])
        self.group_index = len(waves[idx]) - 1
        self._refresh_waves()

    def del_group(self):
        waves = self._waves()
        idx = self.wave_list.index
        if 0 <= idx < len(waves) and 0 <= self.group_list.index < len(waves[idx]):
            waves[idx].pop(self.group_list.index)
        self._refresh_waves()

    # -- list buttons -------------------------------------------------------
    def new(self):
        self.apply_current()
        data = self.default_entry()
        ids = {i.get("id") for i in self.items}
        n = 2
        while data["id"] in ids:
            data["id"] = "new_level_{}".format(n)
            n += 1
        self.items.append(data)
        self.refresh(select=data)
        self.app.set_status("Levels: created '{}'".format(data["id"]))

    def duplicate(self):
        if self.current is None:
            return
        self.apply_current()
        data = dict(self.current)
        data["waves"] = [[list(g) for g in w] for w in (data.get("waves") or [])]
        data["grid"] = list(data.get("grid") or [])
        base = str(data["id"]) + "_copy"
        ids = {i.get("id") for i in self.items}
        new_id, n = base, 2
        while new_id in ids:
            new_id = "{}_{}".format(base, n)
            n += 1
        data["id"] = new_id
        data["name"] = str(data.get("name", new_id)) + " copy"
        self.items.append(data)
        self.refresh(select=data)

    def delete(self):
        if self.current is None:
            return
        item = self.current
        self.items.remove(item)
        self.current = None
        self.refresh()
        self.app.content.delete_orphans(self.folder, {i.get("id") for i in self.items})
        self.app.set_status("Levels: deleted '{}'".format(item.get("id")))

    def save(self):
        self.apply_current()
        self._apply_group_fields()
        ids = [i.get("id") for i in self.items]
        if len(ids) != len(set(ids)):
            self.app.set_status("ERROR: duplicate level ids - not saved", W.BAD)
            return
        for item in self.items:
            self.app.content.save_level(item)
        self.app.content.delete_orphans(self.folder, set(ids))
        # keep each race's level list in sync with the levels that name it
        for race in self.app.content.races.values():
            linked = sorted((i["id"] for i in self.items if i.get("race") == race["id"]),
                            key=lambda lid: ([i.get("order", 0) for i in self.items
                                              if i.get("id") == lid] + [0])[0])
            race = dict(race)
            race["levels"] = linked
            self.app.content.save_race(race)
        self.app.content.reload()
        art.clear_caches()
        self.app.set_status("Levels: saved {} entries".format(len(self.items)))

    # -- events / draw ------------------------------------------------------
    def handle_event(self, event):
        for w in (self.list, self.wave_list, self.group_list):
            if w.handle_event(event):
                return True
        for b in self.list_buttons + self.wave_buttons + self.group_buttons:
            if b.handle_event(event):
                return True
        for field in self.fields.values():
            if field.handle_event(event):
                return True
        for field in (self.g_unit, self.g_count, self.g_interval):
            if field.handle_event(event):
                return True
        if self.avail_sel.handle_event(event) or self.enemy_sel.handle_event(event):
            return True
        if self._palette_click(event):
            return True
        if self.map.handle_event(event):
            self.fields["width"].set_value(self.map.width)
            self.fields["height"].set_value(self.map.height)
            return True
        return False

    def draw(self):
        self.ctx.canvas.fill((0, 0, 0))
        _text(self.ctx, "Levels", (LEVEL_FORM_X, FORM_TOP - 30), W.TEXT, "big")
        self.list.draw(self.ctx.canvas)
        for b in self.list_buttons:
            b.draw(self.ctx.canvas)

        self.map.draw()
        status = "path OK" if self.map.path_ok else "NO PATH from S to B"
        _text(self.ctx, "Map ({})  -  {}".format(
            "{}x{}".format(self.map.width, self.map.height), status),
            (MAP_RECT.x, MAP_RECT.y - 22), W.OK if self.map.path_ok else W.BAD)
        self._draw_palette()

        _text(self.ctx, "Available units", (AVAIL_RECT.x, AVAIL_RECT.y - 20))
        _text(self.ctx, "Enemy pool", (ENEMY_RECT.x, ENEMY_RECT.y - 20))
        self.avail_sel.draw(self.ctx.canvas)
        self.enemy_sel.draw(self.ctx.canvas)

        for field in self.fields.values():
            field.draw(self.ctx.canvas)
        _text(self.ctx, "Waves", (LEVEL_FORM_X, 236))
        self.wave_list.draw(self.ctx.canvas)
        for b in self.wave_buttons:
            b.draw(self.ctx.canvas)
        _text(self.ctx, "Units in selected wave", (LEVEL_FORM_X, 430))
        self.group_list.draw(self.ctx.canvas)
        for b in self.group_buttons:
            b.draw(self.ctx.canvas)
        for field in (self.g_unit, self.g_count, self.g_interval):
            field.draw(self.ctx.canvas)

    def palette_rects(self):
        """``[(rect, grid_char), ...]`` for every swatch, in draw order."""
        entries = [(t.get("char", "?")) for t in self.app.terrain_tab.items]
        entries = entries + ["S", "B"]
        rects = []
        for i, ch in enumerate(entries):
            rect = pygame.Rect(MAP_RECT.x + i * 48, PALETTE_Y, 44, 44)
            rects.append((rect, ch))
        return rects

    def _palette_click(self, event):
        if event.type != pygame.MOUSEBUTTONDOWN or event.button not in (1, 3):
            return False
        for rect, ch in self.palette_rects():
            if rect.collidepoint(event.pos):
                self.map.selected = ch
                self.app.set_status("Brush: '{}'".format(
                    "spawn" if ch == "S" else "base" if ch == "B" else ch))
                return True
        return False

    def _draw_palette(self):
        lookup = self.app.terrain_lookup()
        for rect, ch in self.palette_rects():
            if ch in ("S", "B"):
                img = art.scaled(art.tile(133 if ch == "S" else 180), (44, 44))
                name = "spawn" if ch == "S" else "base"
            else:
                terr = lookup.get(ch)
                if terr is None:
                    continue
                img = art.sprite(terr.get("sprite") or
                                 {"kind": "pack", "tile": terr.get("base", 157)},
                                 44, terr.get("tint"))
                name = terr.get("name", ch)
            self.ctx.canvas.blit(img, rect)
            sel = self.map.selected == ch
            pygame.draw.rect(self.ctx.canvas, W.ACCENT if sel else W.EDGE,
                             rect, 3 if sel else 1)
            _text(self.ctx, ch, (rect.x + 2, rect.y + 1), (255, 255, 255))
            if ch not in ("S", "B"):
                _text(self.ctx, name, (rect.x, rect.bottom + 1), W.DIM)


# ===========================================================================
# help
# ===========================================================================
class HelpTab:
    title = "Help"

    def __init__(self, app):
        self.app = app
        self.ctx = app.ctx
        self.lines = [
            "Big Tower - Level Designer",
            "",
            "Tabs (top bar): Terrain | Units | Races | Levels | Help",
            "",
            "Lists are on the left; click a row to edit it.  New / Dup / Delete /",
            "Save act on the current list.  Save writes JSON to content/ and also",
            "keeps files tidy by removing deleted entries.",
            "",
            "Terrain:  a grid character maps to a base tile + optional overlay.",
            "  buildable = players may place defenders there.",
            "  walkable  = ground enemies may path through it.",
            "  The spawn 'S' and base 'B' characters are reserved.",
            "",
            "Units:  one schema for both sides.",
            "  side=defender -> placed by the player (a 'tower'); side=attacker ->",
            "    spawned by enemy waves.",
            "  movement: static | chase | route | direct | hunt",
            "     static  = classic turret",
            "     chase   = defender walks after the nearest enemy (e.g. Scorpion)",
            "     route   = attacker follows the map path",
            "     direct  = attacker flies straight at the base",
            "     hunt    = attacker leaves the path to chase a defender",
            "  attack: none | melee | projectile   (enemies with an attack hurt",
            "     towers, so both sides fight)",
            "  sprite: CLICK THE PREVIEW ICON to set art.  The designer asks:",
            "     - Static image: pick one PNG (a single picture).",
            "     - Animation: pick a spritesheet, then highlight its frames per",
            "       state (idle / walk / attack / death) in the animation editor.",
            "     Click a frame to add/remove it, shift-click to add a range; set",
            "     each state's fps and loop.  A static image is kept as the",
            "     fallback for any state you leave empty.",
            "  the game auto-plays the matching state (still/moving/firing/killed).",
            "  You can still hand-edit the sprite kind (pack/image/shape/sheet/anim).",
            "  tint: overrides the race tint (handy for recoloured variants).",
            "",
            "Terrain:  base + optional overlay can each be a Kenney tile or your",
            "  own art.  Click the base or overlay preview to pick a static image",
            "  or a looping animation - so you can drop in custom ground tiles,",
            "  animated water/lava, decals, and so on.",
            "",
            "Races:  a campaign.  Pick which defender units are on offer and which",
            "  attackers the levels use.  Levels are attached from the Levels tab.",
            "",
            "Levels:  paint the map (left-click paints the selected terrain, right-",
            "  click erases to grass).  Click a palette swatch to choose the brush",
            "  (the spawn 'S' and base 'B' are in the palette).  A yellow line",
            "  previews the route; if it says NO PATH the level cannot be played.",
            "  'Available units' are the level's shop; 'Enemy pool' its attacker",
            "  roster.  Build waves below: each wave holds unit groups (unit, count,",
            "  spawn gap seconds).",
            "",
            "Everything saves to content/ - the game reads the same files.",
        ]
        self.scroll = 0
        self._heights = [34 if l == "Big Tower - Level Designer" else 24
                         for l in self.lines]

    def _max_scroll(self):
        total = sum(self._heights)
        return max(0, 64 + total - self.ctx.canvas.get_height() + 12)

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, min(self._max_scroll(), self.scroll - event.y * 40))
            return True
        return False

    def draw(self):
        self.ctx.canvas.fill((0, 0, 0))
        y = 64 - self.scroll
        for line, h in zip(self.lines, self._heights):
            if y + h >= 64 and y <= self.ctx.canvas.get_height():
                key = "big" if h == 34 else "default"
                color = W.TEXT if not line.startswith("  ") else W.DIM
                _text(self.ctx, line, (40, y), color, key)
            y += h
        if self._max_scroll() > 0:
            _text(self.ctx, "scroll with the mouse wheel", (40, 40), W.ACCENT)

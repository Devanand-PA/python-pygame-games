"""The designer's tabs: Terrain, Units, Races, Levels and Help.

Each tab owns a working list of plain dicts (mirroring the JSON on disk), a
list panel to pick one, and a form of widgets to edit it.  Saving writes every
entry back through :class:`core.content.ContentDB` and removes orphaned files.

Every tab also owns a :class:`~level_designer.history.History`: the undo stack
holds a snapshot of the item list taken *before* each mutating action, and undo
puts that snapshot back into the items, the widgets and the map canvas.  Camera
zoom / pan and list selection never record, because neither changes content.

Geometry comes from :mod:`level_designer.layout` so no widget can drift off the
1280x720 canvas or into the neighbouring column.
"""
import json
from collections import deque
from copy import deepcopy

import pygame

from core import settings as S
from engine import art
from level_designer import layout as L
from level_designer import widgets as W
from level_designer.history import History

TITLE_KEY = "default"            # section titles use the 30pt face, not the 48pt one
HERO_NONE = "(none)"


def _text(ctx, s, pos, color=W.TEXT, key="small"):
    surf = ctx.fonts[key].render(str(s), True, color)
    ctx.canvas.blit(surf, pos)


def _right_text(ctx, s, right_x, y, color=W.TEXT, key="small"):
    surf = ctx.fonts[key].render(str(s), True, color)
    ctx.canvas.blit(surf, (right_x - surf.get_width(), y))


class UndoMixin:
    """Snapshot undo/redo + a dirty flag shared by every editor tab."""

    def setup_history(self):
        self.history = History(self._snapshot, self._restore,
                               on_change=self._history_changed)
        self._restoring = False
        self._recorded = False
        self._touched = False
        self._saved_key = self._doc_key()

    # -- to be provided by the editor tabs ---------------------------------
    def _snapshot(self):
        raise NotImplementedError

    def _restore(self, state):
        raise NotImplementedError

    # -- plumbing -----------------------------------------------------------
    def _doc_key(self):
        try:
            return json.dumps(self.items, sort_keys=True, default=str)
        except (TypeError, ValueError):
            return repr(self.items)

    @property
    def dirty(self):
        return self._doc_key() != self._saved_key

    def mark_saved(self):
        self._saved_key = self._doc_key()

    def rebase(self):
        """Re-baseline the dirty flag after a load the user did not ask for.

        ``apply_current`` fills in keys the file simply did not carry yet (a
        level with no ``gold_per_sec``, say).  Until the designer has actually
        done something that is still "what is on disk", so it must not show up
        as an unsaved change.
        """
        if not self._touched:
            self.mark_saved()

    def record(self, label=""):
        """Call *before* mutating the item list (fields excepted)."""
        self._touched = True
        self.history.record(label)
        self._recorded = True

    def record_state(self, state, label=""):
        """Undo step from a snapshot taken earlier (e.g. at stroke start)."""
        self._touched = True
        self.history.record_state(state, label)
        self._recorded = True

    def _history_changed(self, _history=None):
        if self._restoring:
            return
        self.sync_history_buttons()

    def sync_history_buttons(self):
        undo_btn = getattr(self, "undo_btn", None)
        redo_btn = getattr(self, "redo_btn", None)
        if undo_btn is not None:
            undo_btn.enabled = self.history.can_undo
        if redo_btn is not None:
            redo_btn.enabled = self.history.can_redo

    def undo(self):
        if not self.history.undo():
            self.app.set_status("Nothing left to undo", W.DIM)
            return False
        self.app.set_status("Undo: " + self.history.status(), W.OK)
        return True

    def redo(self):
        if not self.history.redo():
            self.app.set_status("Nothing left to redo", W.DIM)
            return False
        self.app.set_status("Redo: " + self.history.status(), W.OK)
        return True

    def undo_key(self, event):
        """Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z, but only outside a text box."""
        if event.type != pygame.KEYDOWN or self.ctx.modal is not None:
            return None
        if not (event.mod & pygame.KMOD_CTRL):
            return None
        if event.key == pygame.K_z:
            return "redo" if (event.mod & pygame.KMOD_SHIFT) else "undo"
        if event.key == pygame.K_y:
            return "redo"
        return None

    # -- status line --------------------------------------------------------
    def _draw_history_status(self, x, y, width):
        state = "unsaved changes" if self.dirty else "saved"
        _text(self.ctx, state, (x, y), W.BAD if self.dirty else W.OK)
        _text(self.ctx, self.history.status(), (x, y + 18), W.DIM)
        self.sync_history_buttons()

    def _draw_title(self, extra=""):
        mark = " *" if self.dirty else ""
        _text(self.ctx, "{}{}{}".format(self.title, mark, extra),
              (L.LIST_X, L.TITLE_Y), W.TEXT, TITLE_KEY)


# ===========================================================================
# form tabs (Terrain / Units / Races)
# ===========================================================================
class FormTab(UndoMixin):
    """List of entries on the left, an editable form on the right."""

    title = "Form"
    folder = "units"
    save_fn = "save_unit"
    cols = 2

    def __init__(self, app):
        self.app = app
        self.ctx = app.ctx
        self.items = list(self.load_items())
        self.current = None
        self.fields = {}
        self.extras = {}
        self.col_w, self.col_x = L.columns(self.cols, L.FORM_X, L.FORM_W)
        self.list = W.ScrollList(self.ctx, L.LIST_RECT, [], on_select=self._on_select)
        self.undo_btn = self._button(2, 0, "Undo", self.undo)
        self.redo_btn = self._button(2, 1, "Redo", self.redo)
        self.buttons = [
            self._button(0, 0, "New", self.new),
            self._button(0, 1, "Dup", self.duplicate),
            self._button(1, 0, "Delete", self.delete, color=(90, 54, 54)),
            self._button(1, 1, "Save", self.save, color=(64, 92, 70)),
            self.undo_btn, self.redo_btn,
        ]
        self.setup_history()
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
    def _button(self, row, col, text, fn, color=W.PANEL2):
        rect = (L.LIST_X + col * (L.BTN_W + 8), L.BTN_ROWS[row], L.BTN_W, L.BTN_H)
        return W.Btn(self.ctx, rect, text, fn, color=color)

    def place(self, name, col, row, span=1, label_w=None):
        width = self.col_w * span + L.COL_GAP * (span - 1)
        rect = L.row_rect(row, self.col_x[col], width)
        field = self.fields[name]
        field.set_rect(rect)
        if label_w is not None:
            field.label_w = label_w
        return field

    def rows_used(self):
        return (len(self.fields) + self.cols - 1) // self.cols

    def below_form(self):
        """Y of the first free row under the form grid."""
        return L.TOP + self.rows_used() * L.ROW_H + 8

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
        self.rebase()

    # -- undo ---------------------------------------------------------------
    def _snapshot(self):
        return {"items": deepcopy(self.items),
                "selected": self.item_id(self.current) if self.current else None}

    def _restore(self, state):
        self._restoring = True
        try:
            self.items[:] = deepcopy(state["items"])
            selected = None
            for item in self.items:
                if self.item_id(item) == state["selected"]:
                    selected = item
            self.refresh(select=selected if selected is not None
                         else (self.items[0] if self.items else None))
        finally:
            self._restoring = False

    def _signature(self):
        try:
            return json.dumps(self.collect(), sort_keys=True, default=str)
        except (TypeError, ValueError):
            return repr(self.collect())

    # -- buttons ------------------------------------------------------------
    def new(self):
        self.apply_current()
        self.record("new")
        data = self.default_entry()
        ids = {self.item_id(i) for i in self.items}
        base = data["id"]
        n = 2
        while data["id"] in ids:
            data["id"] = "{}_{}".format(base, n)
            n += 1
        self.items.append(data)
        self.refresh(select=data)
        self.app.set_status("{}: created '{}'".format(self.title, data["id"]))

    def duplicate(self):
        if self.current is None:
            return
        self.apply_current()
        self.record("duplicate")
        data = deepcopy(self.current)
        ids = {self.item_id(i) for i in self.items}
        base = str(data["id"]) + "_copy"
        new_id = base
        n = 2
        while new_id in ids:
            new_id = "{}_{}".format(base, n)
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
        self.record("delete")
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
        self.mark_saved()
        self.app.set_status("{}: saved {} entries".format(self.title, len(self.items)))

    def validate(self):
        ids = [self.item_id(i) for i in self.items]
        if len(ids) != len(set(ids)):
            self.app.set_status("ERROR: duplicate ids - not saved", W.BAD)
            return False
        return True

    # -- events / draw ------------------------------------------------------
    def _handle_widgets(self, event):
        """Buttons and fields; subclasses add their own widgets around this."""
        for b in self.buttons:
            if b.handle_event(event):
                return True
        for field in self.fields.values():
            if field.handle_event(event):
                return True
        return False

    def handle_event(self, event):
        if self.list.handle_event(event):        # selection is never undoable
            return True
        self._recorded = False
        before = self._signature()
        if not self._handle_widgets(event):
            return False
        if not self._recorded and not self._restoring \
                and before != self._signature():
            self.record("edit")
            self.app.set_status("{}: change recorded ({})".format(
                self.title, self.history.status()), W.DIM)
        # keep items in lock-step with the widgets, so the dirty flag, the undo
        # snapshots and save() all read the same, up-to-date, document
        if not self._restoring:
            self.apply_current()
        return True

    def draw(self):
        self.ctx.canvas.fill((0, 0, 0))
        self._draw_title()
        self.list.draw(self.ctx.canvas)
        for b in self.buttons:
            b.draw(self.ctx.canvas)
        for field in self.fields.values():
            field.draw(self.ctx.canvas)
        self._draw_history_status(L.LIST_X, L.LIST_HINT_Y, L.LIST_W)


# ===========================================================================
# terrain
# ===========================================================================
TERRAIN_BASE_KINDS = ("pack", "image", "sheet")
TERRAIN_OVERLAY_KINDS = ("none", "pack", "image", "sheet")


class TerrainTab(FormTab):
    title = "Terrain"
    folder = "terrain"
    save_fn = "save_terrain_entry"
    cols = 2

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
            self.place(name, idx % self.cols, idx // self.cols)

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
        self.mark_saved()
        self.app.set_status("Terrain: saved {} entries".format(len(self.items)))

    # -- previews -----------------------------------------------------------
    def _base_preview_rect(self):
        return pygame.Rect(L.FORM_X, self.below_form(), 130, 130)

    def _overlay_preview_rect(self):
        base = self._base_preview_rect()
        return pygame.Rect(base.x, base.bottom + 10, 130, 96)

    def _handle_widgets(self, event):
        if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.current is not None):
            if self._base_preview_rect().collidepoint(event.pos):
                self._open_flow("base")
                return True
            if self._overlay_preview_rect().collidepoint(event.pos):
                self._open_flow("overlay")
                return True
        return super()._handle_widgets(event)

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
    cols = 3

    def load_items(self):
        # UnitType.to_dict() drops the two newest keys, so read them back off
        # the UnitType itself - otherwise projectiles / upgrade_paths would
        # silently reset to the defaults every time the designer opens.
        out = []
        for unit in self.app.content.units.values():
            data = unit.to_dict()
            data["projectiles"] = unit.projectiles
            data["upgrade_paths"] = [dict(p, gains=dict(p["gains"]))
                                     for p in unit.upgrade_paths]
            out.append(data)
        return out

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
                "description": "", "projectiles": 1, "upgrade_paths": []}

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
        f["projectiles"] = W.IntField(self.ctx, (0, 0, 0, 0), "shots / attack", 1)
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
                 "range", "damage", "cooldown", "projectiles", "projectile",
                 "splash", "sound", "targets", "targeting", "is_flying",
                 "damage_to_base", "stop_to_attack", "aggro", "radius",
                 "can_be_attacked", "description"]
        for idx, name in enumerate(order):
            self.place(name, idx % self.cols, idx // self.cols)
        self.upgrade_editor = W.UpgradePathEditor(self.ctx, L.UNITS_UPGRADE_RECT)

    # -- sprite spec --------------------------------------------------------
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
        self.fields["projectiles"].set_value(max(1, int(item.get("projectiles") or 1)))
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
        self.upgrade_editor.set_paths(item.get("upgrade_paths"))

    def collect(self):
        data = {name: field.value for name, field in self.fields.items()}
        for helper in ("sprite_kind", "sprite_tile", "sprite_path", "sprite_shape",
                       "sprite_color", "frame_w", "frame_h", "sprite_frames",
                       "sprite_fps", "sprite_loop"):
            data.pop(helper, None)
        data["sprite"] = self._spec_from_fields()
        data["tint"] = data.pop("tint") if data.pop("tint_enabled") else None
        data["projectiles"] = max(1, int(data.get("projectiles") or 1))
        data["upgrade_paths"] = self.upgrade_editor.value
        return data

    def _handle_widgets(self, event):
        if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.current is not None
                and self._preview_rect().collidepoint(event.pos)):
            self._open_sprite_flow()
            return True
        if self.upgrade_editor.handle_event(event):
            return True
        return super()._handle_widgets(event)

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

    def _preview_rect(self):
        return L.UNITS_PREVIEW_RECT

    def draw(self):
        super().draw()
        self.upgrade_editor.draw(self.ctx.canvas)
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
            img = art.sprite(spec, min(preview.height, preview.width) - 12, tint,
                             frame=art.frame_index(spec, t))
            self.ctx.canvas.blit(img, img.get_rect(center=preview.center))
        except Exception:      # noqa: BLE001
            pass
        _text(self.ctx, "Sprite - click to change",
              (preview.x, L.UNITS_PREVIEW_HINT_Y), W.ACCENT)
        states = art.animation_names(spec)
        if states:
            summary = "states: " + ", ".join(states)[:30]
        else:
            n = art.frame_count(spec)
            summary = "{} frames @ {:g} fps".format(n, art.fps(spec)) if n > 1 \
                else "static {}".format(spec.get("kind", "pack"))
        _text(self.ctx, summary[:34], (preview.x, L.UNITS_PREVIEW_HINT_Y + 18), W.DIM)


# ===========================================================================
# races
# ===========================================================================
class RacesTab(FormTab):
    title = "Races"
    folder = "races"
    save_fn = "save_race"
    cols = 2

    def load_items(self):
        return [dict(r) for r in self.app.content.races.values()]

    def entry_label(self, item):
        return item.get("name", item.get("id"))

    def default_entry(self):
        return {"id": "new_race", "name": "New Race", "description": "",
                "color": [120, 200, 140], "tint": None, "order": 99,
                "units": [], "enemies": [], "levels": [], "hero": None}

    def build_fields(self):
        f = self.fields
        f["id"] = W.TextField(self.ctx, (0, 0, 0, 0), "id")
        f["name"] = W.TextField(self.ctx, (0, 0, 0, 0), "name")
        f["order"] = W.IntField(self.ctx, (0, 0, 0, 0), "menu order")
        f["hero"] = W.ChoiceField(self.ctx, (0, 0, 0, 0), "base hero",
                                  (HERO_NONE,))
        f["color_enabled"] = W.CheckField(self.ctx, (0, 0, 0, 0), "theme colour")
        f["color"] = W.ColorField(self.ctx, (0, 0, 0, 0), "colour RGB")
        f["tint_enabled"] = W.CheckField(self.ctx, (0, 0, 0, 0), "unit tint")
        f["tint"] = W.ColorField(self.ctx, (0, 0, 0, 0), "tint RGB")
        f["description"] = W.TextField(self.ctx, (0, 0, 0, 0), "description")
        self.place("id", 0, 0)
        self.place("name", 1, 0)
        self.place("order", 0, 1)
        self.place("hero", 1, 1, label_w=110)
        self.place("color_enabled", 0, 2)
        self.place("color", 1, 2)
        self.place("tint_enabled", 0, 3)
        self.place("tint", 1, 3)
        self.place("description", 0, 4, span=2, label_w=110)

        sel_top = self.below_form() + 28
        self.units_sel = W.MultiSelect(
            self.ctx, (self.col_x[0], sel_top, self.col_w,
                       L.BOTTOM - sel_top))
        self.enemies_sel = W.MultiSelect(
            self.ctx, (self.col_x[1], sel_top, self.col_w,
                       L.BOTTOM - sel_top))
        self.units_label_y = sel_top - 20
        self.race_note_y = L.BOTTOM - 60

    def _hero_options(self, hero=None):
        options = [HERO_NONE] + [u.id for u in self.app.content.sorted_units("defender")]
        if hero and hero not in options:
            options.append(hero)          # keep an unknown id visible instead of dropping it
        return options

    def load_entry(self, item):
        super().load_entry(item)
        self.fields["color_enabled"].set_value(True)
        self.fields["color"].set_value(item.get("color") or [120, 200, 140])
        self.fields["tint_enabled"].set_value(item.get("tint") is not None)
        self.fields["tint"].set_value(item.get("tint") or [200, 240, 200])
        self.fields["hero"].options = self._hero_options(item.get("hero"))
        self.fields["hero"].set_value(item.get("hero") or HERO_NONE)
        defenders = [(u.id, u.name) for u in self.app.content.sorted_units("defender")]
        attackers = [(u.id, u.name) for u in self.app.content.sorted_units("attacker")]
        self.units_sel.set_options(defenders, item.get("units") or [])
        self.enemies_sel.set_options(attackers, item.get("enemies") or [])

    def collect(self):
        data = {name: field.value for name, field in self.fields.items()}
        data["color"] = data.pop("color") if data.pop("color_enabled") else [120, 200, 140]
        data["tint"] = data.pop("tint") if data.pop("tint_enabled") else None
        hero = data.pop("hero")
        data["hero"] = None if hero in (None, HERO_NONE) else hero
        data["units"] = self.units_sel.value
        data["enemies"] = self.enemies_sel.value
        return data

    def _handle_widgets(self, event):
        if self.units_sel.handle_event(event) or self.enemies_sel.handle_event(event):
            return True
        return super()._handle_widgets(event)

    def draw(self):
        super().draw()
        _text(self.ctx, "Available units (defenders)",
              (self.units_sel.rect.x, self.units_label_y))
        _text(self.ctx, "Enemies", (self.enemies_sel.rect.x, self.units_label_y))
        _text(self.ctx, "base hero is summoned when an attacker reaches the base",
              (self.units_sel.rect.x, self.units_label_y - 20), W.DIM)
        self.units_sel.draw(self.ctx.canvas)
        self.enemies_sel.draw(self.ctx.canvas)
        # levels belonging to this race (managed from the Levels tab)
        if self.current is not None:
            levels = [l["id"] for l in self.app.content.levels.values()
                      if l.get("race") == self.current.get("id")]
            _text(self.ctx, "Levels for this race: {} (edit on the Levels tab)"
                  .format(", ".join(sorted(levels)) or "none"),
                  (self.col_x[0], self.race_note_y), W.DIM)


# ===========================================================================
# map canvas: a zoomable, pannable viewport onto the level grid
# ===========================================================================
CELL = 28              # starting zoom, in canvas pixels per grid cell
MAX_CELL = 48           # zoom in limit
MIN_CELL = 6            # zoom out limit


class MapCanvas:
    """A viewport onto a level grid that may be much larger than the panel.

    The panel is fixed; the *cell size* is what changes.  ``cell`` is the zoom
    level in canvas pixels and ``scroll_x`` / ``scroll_y`` are the pan offset,
    so grid cell ``(x, y)`` always lands at::

        panel.x + x * cell - scroll_x,  panel.y + y * cell - scroll_y

    Painting and the path preview both go through that one mapping, which is
    what keeps clicks correct at any zoom.  Zoom and pan never touch ``grid``,
    so they can never corrupt a level and never need an undo entry.
    """

    ZOOM_STEP = 1.25
    DRAG_THRESHOLD = 4      # px of movement before a right-drag becomes a pan

    def __init__(self, ctx, app, rect):
        self.ctx = ctx
        self.app = app
        self.rect = pygame.Rect(rect)
        self.cell = CELL
        self.width = max(1, rect.width // CELL)
        self.height = max(1, rect.height // CELL)
        self.grid = [["g"] * self.width for _ in range(self.height)]
        self.selected = "g"
        self.painting = False
        self._tile_cache = {}
        self._marker_cache = {}
        self.path = []
        self.path_ok = False
        self._dirty = True
        self.scroll_x = 0.0
        self.scroll_y = 0.0
        self.space_down = False
        self._pan = None            # (origin_pos, scroll_x, scroll_y)
        self._press = None          # (pos, button) for a pending click
        self.on_stroke_begin = None     # tab hooks, called before the first edit
        self.on_stroke_end = None
        self._fit_cell()

    # -- geometry -----------------------------------------------------------
    def set_rect(self, rect):
        """Resize the panel (the zoom and pan are kept, then re-clamped)."""
        self.rect = pygame.Rect(rect)
        self._clamp_scroll()

    @property
    def fits(self):
        """True when the whole grid fits in the panel at the current zoom."""
        return (self.width * self.cell <= self.rect.width
                and self.height * self.cell <= self.rect.height)

    @property
    def map_rect(self):
        """Where the whole grid sits in canvas coordinates (may overhang)."""
        return pygame.Rect(int(self.rect.x - self.scroll_x),
                           int(self.rect.y - self.scroll_y),
                           self.width * self.cell, self.height * self.cell)

    def set_cell(self, cell):
        cell = max(MIN_CELL, min(MAX_CELL, int(round(cell))))
        if cell != self.cell:
            self.cell = cell
            self._tile_cache.clear()      # tiles are rasterised at cell size
            self._marker_cache.clear()
        return self.cell

    def _fit_cell(self):
        """Scale the tile size so the whole grid lands inside the view rect."""
        cell = min(self.rect.width // max(1, self.width),
                   self.rect.height // max(1, self.height))
        self.set_cell(cell)
        self.scroll_x = 0.0
        self.scroll_y = 0.0
        self._clamp_scroll()

    def fit_view(self):
        """Zoom + pan so the whole map is visible again."""
        self._fit_cell()

    def _clamp_scroll(self):
        """Keep the grid inside the panel, centring it when it is smaller."""
        max_x = self.width * self.cell - self.rect.width
        max_y = self.height * self.cell - self.rect.height
        self.scroll_x = min(max(self.scroll_x, min(0.0, max_x)), max(0.0, max_x))
        self.scroll_y = min(max(self.scroll_y, min(0.0, max_y)), max(0.0, max_y))

    def zoom_at(self, pos, notches):
        """Zoom by ``notches`` steps, keeping the point under ``pos`` fixed."""
        if not notches:
            return
        anchor_x = pos[0] - self.rect.x + self.scroll_x
        anchor_y = pos[1] - self.rect.y + self.scroll_y
        cell_x = anchor_x / self.cell
        cell_y = anchor_y / self.cell
        target = self.cell * (self.ZOOM_STEP ** notches)
        new_cell = max(MIN_CELL, min(MAX_CELL, int(round(target))))
        if new_cell == self.cell:
            return
        self.set_cell(new_cell)
        self.scroll_x = cell_x * self.cell - (pos[0] - self.rect.x)
        self.scroll_y = cell_y * self.cell - (pos[1] - self.rect.y)
        self._clamp_scroll()

    def cell_screen_rect(self, x, y):
        return pygame.Rect(self.rect.x + x * self.cell - self.scroll_x,
                           self.rect.y + y * self.cell - self.scroll_y,
                           self.cell, self.cell)

    def cell_center(self, x, y):
        r = self.cell_screen_rect(x, y)
        return (r.centerx, r.centery)

    def _cell_at(self, pos):
        if not self.rect.collidepoint(pos):
            return None
        return (int((pos[0] - self.rect.x + self.scroll_x) // self.cell),
                int((pos[1] - self.rect.y + self.scroll_y) // self.cell))

    def visible_range(self):
        """Inclusive ``(x0, y0, x1, y1)`` cell range covering the panel."""
        x0 = max(0, int(self.scroll_x) // self.cell)
        y0 = max(0, int(self.scroll_y) // self.cell)
        x1 = min(self.width - 1, int((self.scroll_x + self.rect.width) - 1) // self.cell)
        y1 = min(self.height - 1, int((self.scroll_y + self.rect.height) - 1) // self.cell)
        return x0, y0, x1, y1

    # -- content ------------------------------------------------------------
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

    def paint(self, cell, char):
        if cell is None:
            return False
        x, y = cell
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        if char in ("S", "B"):
            for j in range(self.height):
                for i in range(self.width):
                    if self.grid[j][i] == char:
                        self.grid[j][i] = "g"
        if self.grid[y][x] == char:
            return False
        self.grid[y][x] = char
        self._dirty = True
        return True

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
        self._marker_cache.clear()
        self._dirty = True

    # -- events -------------------------------------------------------------
    def _begin_stroke(self):
        if self.on_stroke_begin is not None:
            self.on_stroke_begin()

    def _end_stroke(self, changed):
        if self.on_stroke_end is not None:
            self.on_stroke_end(changed)

    def _pan_from(self, origin, start_scroll):
        self._pan = (origin, start_scroll[0], start_scroll[1])

    def _end_drag(self):
        """Drop any half-finished drag so a stray button never wedges it."""
        was_painting = self.painting
        self.painting = False
        self._pan = None
        self._press = None
        if was_painting:
            self._end_stroke(False)

    def _panning_possible(self):
        return bool(pygame.key.get_pressed()[pygame.K_SPACE]) or self.space_down

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            self.space_down = True
        elif event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
            self.space_down = False

        if event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(event.pos):
            # pygame reports wheel-up as y > 0, which is the "zoom in" notch
            self.zoom_at(event.pos, event.y)
            return True

        if event.type == pygame.MOUSEBUTTONDOWN:
            return self._button_down(event)
        if event.type == pygame.MOUSEMOTION:
            return self._motion(event)
        if event.type == pygame.MOUSEBUTTONUP:
            return self._button_up(event)
        return False

    def _button_down(self, event):
        if not self.rect.collidepoint(event.pos):
            return False
        self._end_drag()
        if event.button == 2 or (event.button == 1 and self._panning_possible()):
            self._pan_from(event.pos, (self.scroll_x, self.scroll_y))
            return True
        if event.button in (1, 3):
            self._press = (event.pos, event.button)
            if event.button == 1:
                self.painting = True
                self._begin_stroke()
                self._end_stroke(self.paint(self._cell_at(event.pos), self.selected))
            return True
        return False

    def _motion(self, event):
        if self._pan is not None:
            origin, sx, sy = self._pan
            self.scroll_x = sx - (event.pos[0] - origin[0])
            self.scroll_y = sy - (event.pos[1] - origin[1])
            self._clamp_scroll()
            return True
        if self.painting:
            self._end_stroke(self.paint(self._cell_at(event.pos), self.selected))
            return True
        if self._press is not None and self._press[1] == 3:
            moved = max(abs(event.pos[0] - self._press[0][0]),
                        abs(event.pos[1] - self._press[0][1]))
            if moved > self.DRAG_THRESHOLD:
                # a right-*drag* pans; a right-*click* still erases to grass
                self._pan_from(self._press[0], (self.scroll_x, self.scroll_y))
                return True
        return False

    def _button_up(self, event):
        pan, press, painting = self._pan, self._press, self.painting
        self._pan = None
        self._press = None
        self.painting = False
        if pan is not None:
            return True
        if painting:
            self._end_stroke(False)
            return True
        if press is not None:
            pos, button = press
            if button == 3 and pos == event.pos:      # a plain click: erase
                self._begin_stroke()
                self._end_stroke(self.paint(self._cell_at(pos), "g"))
            return True
        return False

    # -- drawing ------------------------------------------------------------
    def _tile(self, ch):
        if ch in self._tile_cache:
            return self._tile_cache[ch]
        lookup = self.app.terrain_lookup()
        terr = lookup.get(ch) or lookup.get("g") or {}
        spec = terr.get("sprite") or {"kind": "pack", "tile": terr.get("base", 157)}
        self._tile_cache[ch] = art.sprite(spec, self.cell, terr.get("tint"))
        return self._tile_cache[ch]

    def _marker(self, ch):
        if ch not in self._marker_cache:
            self._marker_cache[ch] = art.scaled(
                art.tile(133 if ch == "S" else 180), (self.cell, self.cell))
        return self._marker_cache[ch]

    def draw(self):
        if self._dirty:
            self.recompute_path()
        canvas = self.ctx.canvas
        pygame.draw.rect(canvas, (10, 10, 14), self.rect)
        canvas.set_clip(self.rect)
        x0, y0, x1, y1 = self.visible_range()
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                ch = self.grid[y][x]
                pos = (int(self.rect.x + x * self.cell - self.scroll_x),
                       int(self.rect.y + y * self.cell - self.scroll_y))
                if ch in ("S", "B"):
                    canvas.blit(self._tile("g"), pos)
                    canvas.blit(self._marker(ch), pos)
                else:
                    canvas.blit(self._tile(ch), pos)
        # path preview
        if len(self.path) > 1:
            pts = [self.cell_center(x, y) for x, y in self.path]
            pygame.draw.lines(canvas, (255, 240, 120), False, pts, 2)
        if self.cell >= 10:                     # grid lines are noise when tiny
            for x in range(x0, x1 + 2):
                gx = int(self.rect.x + x * self.cell - self.scroll_x)
                pygame.draw.line(canvas, (255, 255, 255, 30), (gx, self.rect.y),
                                 (gx, self.rect.bottom), 1)
            for y in range(y0, y1 + 2):
                gy = int(self.rect.y + y * self.cell - self.scroll_y)
                pygame.draw.line(canvas, (255, 255, 255, 30), (self.rect.x, gy),
                                 (self.rect.right, gy), 1)
        pygame.draw.rect(canvas, (70, 70, 100), self.map_rect, 1)
        if not self.path_ok:
            pygame.draw.rect(canvas, (200, 60, 60), self.rect, 2)
        canvas.set_clip(None)
        pygame.draw.rect(canvas, W.EDGE, self.rect, 1)
        if not self.fits:
            self._draw_minimap(canvas)

    def _draw_minimap(self, canvas):
        """A corner outline of where the panel sits inside the whole map."""
        box = pygame.Rect(self.rect.right - 96, self.rect.bottom - 66, 88, 56)
        pygame.draw.rect(canvas, (10, 10, 14), box, border_radius=4)
        pygame.draw.rect(canvas, W.EDGE, box, 1, border_radius=4)
        span_x = max(1, self.width * self.cell)
        span_y = max(1, self.height * self.cell)
        inner = pygame.Rect(box.x + 2, box.y + 2, box.width - 4, box.height - 4)
        scale = min(inner.width / span_x, inner.height / span_y)
        origin = (inner.centerx - span_x * scale / 2, inner.centery - span_y * scale / 2)
        size = (max(2, int(span_x * scale)), max(2, int(span_y * scale)))
        pygame.draw.rect(canvas, (80, 110, 90), pygame.Rect(origin, size), 1)
        view_w = max(3, int(self.rect.width * scale))
        view_h = max(3, int(self.rect.height * scale))
        vx = origin[0] + (self.scroll_x * scale)
        vy = origin[1] + (self.scroll_y * scale)
        pygame.draw.rect(canvas, W.ACCENT, pygame.Rect(int(vx), int(vy),
                                                       view_w, view_h), 1)


# ===========================================================================
# levels
# ===========================================================================
class LevelsTab(UndoMixin):
    """Full level editor: paint the map, pick units, build waves.

    Three columns: the level list on the left, the zoomable map canvas in the
    middle, the level form + wave builder on the right (from
    ``layout.LEVEL_FORM_X``).  Every rect below is derived from live values --
    the map panel shrinks if the terrain palette needs more than one row of
    swatches -- so nothing can overlap or leave the canvas.
    """

    title = "Levels"
    folder = "levels"
    save_fn = "save_level"

    def __init__(self, app):
        self.app = app
        self.ctx = app.ctx
        self.items = [dict(l) for l in app.content.levels.values()]
        self.current = None
        self.wave_index = 0
        self.group_index = 0
        self.palette_top = L.PAL_BOTTOM - L.PAL_SWATCH
        self.list = W.ScrollList(self.ctx, L.LEVELS_LIST_RECT, [],
                                 on_select=self._on_select)
        self.undo_btn = self._button(2, 0, "Undo", self.undo)
        self.redo_btn = self._button(2, 1, "Redo", self.redo)
        self.list_buttons = [
            self._button(0, 0, "New", self.new),
            self._button(0, 1, "Dup", self.duplicate),
            self._button(1, 0, "Delete", self.delete, color=(90, 54, 54)),
            self._button(1, 1, "Save", self.save, color=(64, 92, 70)),
            self.undo_btn, self.redo_btn,
        ]
        self.fields = {}
        self.map = MapCanvas(self.ctx, app, pygame.Rect(L.MAP_X, L.MAP_TOP,
                                                         L.MAP_W, L.MAP_MAX_H))
        self.map.on_stroke_begin = self._stroke_begin
        self.map.on_stroke_end = self._stroke_end
        self._stroke_state = None
        self._build_fields()
        self.setup_history()
        self.avail_sel = W.MultiSelect(
            self.ctx, (L.MAP_X, L.SEL_TOP, L.SEL_W, L.SEL_H))
        self.enemy_sel = W.MultiSelect(
            self.ctx, (L.MAP_X + L.SEL_W + 12, L.SEL_TOP, L.SEL_W, L.SEL_H))
        self.wave_list = W.ScrollList(self.ctx, L.WAVE_LIST_RECT, [],
                                      on_select=self._on_wave)
        self.group_list = W.ScrollList(self.ctx, L.GROUP_LIST_RECT, [],
                                       on_select=self._on_group)
        bw = (L.LEVEL_FORM_W - 3 * 8) // 4
        self.wave_buttons = [
            W.Btn(self.ctx, (L.LEVEL_FORM_X, L.WAVE_BTN_Y, bw, L.ZOOM_BTN_H),
                  "Add wave", self.add_wave),
            W.Btn(self.ctx, (L.LEVEL_FORM_X + bw + 8, L.WAVE_BTN_Y, bw,
                             L.ZOOM_BTN_H), "Del wave", self.del_wave),
            W.Btn(self.ctx, (L.LEVEL_FORM_X + 2 * (bw + 8), L.WAVE_BTN_Y, bw,
                             L.ZOOM_BTN_H), "Dup wave", self.dup_wave),
            W.Btn(self.ctx, (L.LEVEL_FORM_X + 3 * (bw + 8), L.WAVE_BTN_Y, bw,
                             L.ZOOM_BTN_H), "Clear", self.clear_wave),
        ]
        self.group_buttons = [
            W.Btn(self.ctx, (L.LEVEL_FORM_X, L.GROUP_BTN_Y, bw, L.ZOOM_BTN_H),
                  "Add unit", self.add_group),
            W.Btn(self.ctx, (L.LEVEL_FORM_X + bw + 8, L.GROUP_BTN_Y, bw,
                             L.ZOOM_BTN_H), "Del unit", self.del_group),
        ]
        self.g_unit = W.ChoiceField(self.ctx, (L.LEVEL_FORM_X, L.GROUP_FIELD_Y, 190,
                                               L.GROUP_FIELD_H), "unit", [], label_w=40)
        self.g_count = W.IntField(self.ctx, (L.LEVEL_FORM_X + 198, L.GROUP_FIELD_Y,
                                             100, L.GROUP_FIELD_H), "count", 1, label_w=52)
        self.g_interval = W.FloatField(self.ctx, (L.LEVEL_FORM_X + 306,
                                                  L.GROUP_FIELD_Y, 110,
                                                  L.GROUP_FIELD_H), "gap", 1.0,
                                       label_w=34)
        self._layout()
        self.refresh()
        self._refresh_waves()

    # -- layout -------------------------------------------------------------
    def _button(self, row, col, text, fn, color=W.PANEL2):
        rect = (L.LIST_X + col * (L.LEVEL_BTN_W + 8), L.BTN_ROWS[row],
                L.LEVEL_BTN_W, L.BTN_H)
        return W.Btn(self.ctx, rect, text, fn, color=color)

    def _layout(self):
        """Derive the map panel + palette band from the live terrain palette."""
        count = len(self.app.terrain_tab.items) + 2          # + spawn + base
        rows = max(1, (count + L.PAL_COLS - 1) // L.PAL_COLS)
        self.palette_top = L.PAL_BOTTOM - (rows - 1) * L.PAL_ROW_H - L.PAL_SWATCH
        height = max(180, self.palette_top - 10 - L.MAP_TOP)
        self.map.set_rect(pygame.Rect(L.MAP_X, L.MAP_TOP, L.MAP_W, height))
        self.zoom_y = L.ZOOM_Y
        self.zoom_buttons = [
            W.Btn(self.ctx, (L.MAP_X, self.zoom_y, L.ZOOM_BTN_W, L.ZOOM_BTN_H),
                  "zoom -", lambda: self._zoom_button(-1)),
            W.Btn(self.ctx, (L.MAP_X + L.ZOOM_BTN_W + L.ZOOM_BTN_GAP, self.zoom_y,
                             L.ZOOM_BTN_W, L.ZOOM_BTN_H), "zoom +",
                  lambda: self._zoom_button(1)),
            # "fit" also puts the scroll back at the map origin
            W.Btn(self.ctx, (L.MAP_X + 2 * (L.ZOOM_BTN_W + L.ZOOM_BTN_GAP),
                             self.zoom_y, L.ZOOM_BTN_W, L.ZOOM_BTN_H),
                  "fit map", self.map.fit_view),
        ]
        self.zoom_readout_x = L.MAP_X + 3 * (L.ZOOM_BTN_W + L.ZOOM_BTN_GAP)

    def map_to_origin(self):
        self.map.scroll_x = 0.0
        self.map.scroll_y = 0.0
        self.map._clamp_scroll()

    def _zoom_button(self, notches):
        centre = (self.map.rect.centerx, self.map.rect.centery)
        self.map.zoom_at(centre, notches)

    def on_show(self):
        """Re-read terrain + unit/race lists when the tab becomes visible."""
        self.map.invalidate()
        self._layout()
        self.fields["race"].options = [r["id"] for r in self.app.content.sorted_races()]
        self.avail_sel.set_options(
            [(u.id, u.name) for u in self.app.content.sorted_units("defender")])
        self.enemy_sel.set_options(
            [(u.id, u.name) for u in self.app.content.sorted_units("attacker")])

    # -- fields -------------------------------------------------------------
    def _build_fields(self):
        f = self.fields
        f["id"] = W.TextField(self.ctx, (0, 0, 0, 0), "id", label_w=70)
        f["name"] = W.TextField(self.ctx, (0, 0, 0, 0), "name", label_w=70)
        f["race"] = W.ChoiceField(self.ctx, (0, 0, 0, 0), "race", [], label_w=70)
        f["order"] = W.IntField(self.ctx, (0, 0, 0, 0), "order", label_w=70)
        f["gold"] = W.IntField(self.ctx, (0, 0, 0, 0), "gold", label_w=70)
        f["gold_per_sec"] = W.FloatField(self.ctx, (0, 0, 0, 0), "gold / sec",
                                          S.DEFAULT_GOLD_PER_SEC, label_w=70)
        f["lives"] = W.IntField(self.ctx, (0, 0, 0, 0), "lives", label_w=70)
        f["width"] = W.IntField(self.ctx, (0, 0, 0, 0), "grid W", label_w=70)
        f["terrain_tint_enabled"] = W.CheckField(self.ctx, (0, 0, 0, 0), "map tint",
                                                 label_w=70)
        f["terrain_tint"] = W.ColorField(self.ctx, (0, 0, 0, 0), "tint RGB", label_w=70)
        f["height"] = W.IntField(self.ctx, (0, 0, 0, 0), "grid H", label_w=70)
        f["description"] = W.TextField(self.ctx, (0, 0, 0, 0), "description",
                                       label_w=96)
        rows = [("id", 0, 0, 1), ("name", 1, 0, 1),
                ("race", 0, 1, 1), ("order", 1, 1, 1),
                ("gold", 0, 2, 1), ("gold_per_sec", 1, 2, 1),
                ("lives", 0, 3, 1), ("width", 1, 3, 1),
                ("terrain_tint_enabled", 0, 4, 1), ("height", 1, 4, 1),
                ("description", 0, 5, 2)]
        for name, col, row, span in rows:
            width = L.LEVEL_COL_W * span + L.COL_GAP * (span - 1)
            f[name].set_rect(L.row_rect(row, L.LEVEL_COLS[col], width))

    def entry_label(self, item):
        return "{} [{}]".format(item.get("name", item.get("id")), item.get("race", "?"))

    def default_entry(self):
        grid = [["g"] * 20 for _ in range(10)]
        grid[5][0] = "S"
        grid[5][19] = "B"
        race = self.app.content.sorted_races()
        return {"id": "new_level", "race": race[0]["id"] if race else "",
                "name": "New Level", "description": "", "gold": 200,
                "gold_per_sec": S.DEFAULT_GOLD_PER_SEC, "lives": 20,
                "order": 99, "grid": ["".join(r) for r in grid],
                "terrain_tint": None, "available_units": [], "enemy_pool": [],
                "waves": []}

    # -- list ops -----------------------------------------------------------
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
        f["gold_per_sec"].set_value(self._gold_per_sec(item))
        f["lives"].set_value(item.get("lives", 20))
        f["order"].set_value(item.get("order", 0))
        f["description"].set_value(item.get("description", ""))
        f["terrain_tint_enabled"].set_value(item.get("terrain_tint") is not None)
        f["terrain_tint"].set_value(item.get("terrain_tint") or [255, 255, 255])
        f["race"].options = [r["id"] for r in self.app.content.sorted_races()]
        f["race"].set_value(item.get("race"))
        grid = item.get("grid") or []
        self.map.resize(len(grid[0]) if grid else 20, len(grid) if grid else 10)
        self.map.set_grid(grid)
        self._sync_size_fields()
        self.avail_sel.set_options(
            [(u.id, u.name) for u in self.app.content.sorted_units("defender")],
            item.get("available_units") or [])
        self.enemy_sel.set_options(
            [(u.id, u.name) for u in self.app.content.sorted_units("attacker")],
            item.get("enemy_pool") or [])
        self.wave_index = 0
        self.group_index = 0
        self._refresh_waves()

    @staticmethod
    def _gold_per_sec(item):
        value = item.get("gold_per_sec")
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = S.DEFAULT_GOLD_PER_SEC
        return round(min(max(0.0, value), S.GOLD_PER_SEC_MAX), 4)

    def _sync_size_fields(self):
        self.fields["width"].set_value(self.map.width)
        self.fields["height"].set_value(self.map.height)

    def collect(self):
        """The level as the widgets currently describe it.

        ``width`` / ``height`` are deliberately absent: they are derived from
        the canvas, so editing them resizes the grid rather than the document
        (and that resize is what gets an undo entry).
        """
        f = self.fields
        return {
            "id": f["id"].value,
            "name": f["name"].value,
            "description": f["description"].value,
            "race": f["race"].value,
            "order": f["order"].value,
            "gold": f["gold"].value,
            "gold_per_sec": self._gold_per_sec({"gold_per_sec": f["gold_per_sec"].value}),
            "lives": f["lives"].value,
            "terrain_tint": (f["terrain_tint"].value
                             if f["terrain_tint_enabled"].value else None),
            "available_units": self.avail_sel.value,
            "enemy_pool": self.enemy_sel.value,
            "waves": deepcopy(self._waves()),
        }

    def _signature(self):
        try:
            return json.dumps(self.collect(), sort_keys=True, default=str)
        except (TypeError, ValueError):
            return repr(self.collect())

    def apply_current(self):
        if self.current is None or self.current not in self.items:
            return
        data = dict(self.current)
        data.update(self.collect())
        data["grid"] = self.map.rows()
        idx = self.items.index(self.current)
        self.items[idx] = data
        self.current = data
        self.rebase()

    # -- undo ---------------------------------------------------------------
    def _snapshot(self):
        return {"items": deepcopy(self.items),
                "selected": self.current.get("id") if self.current else None}

    def _restore(self, state):
        self._restoring = True
        try:
            self.items[:] = deepcopy(state["items"])
            selected = None
            for item in self.items:
                if item.get("id") == state["selected"]:
                    selected = item
            self.refresh(select=selected if selected is not None
                         else (self.items[0] if self.items else None))
        finally:
            self._restoring = False

    def _stroke_begin(self):
        """Remember the level as it was when the stroke started.

        The items still hold the pre-stroke grid (it only reaches them through
        ``apply_current``), so this snapshot is exactly what an undo needs.
        Pushing it only when the stroke actually changed something keeps a click
        on an already-correct cell from spending an undo step.
        """
        self._stroke_state = self._snapshot()

    def _stroke_end(self, changed):
        if changed and self._stroke_state is not None:
            self.record_state(self._stroke_state, "paint")
        self._stroke_state = None

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
        self._apply_group_fields()
        self._waves().append([])
        self.wave_index = len(self._waves()) - 1
        self.group_index = 0
        self._refresh_waves()

    def del_wave(self):
        self._apply_group_fields()
        waves = self._waves()
        if 0 <= self.wave_list.index < len(waves):
            waves.pop(self.wave_list.index)
        self._refresh_waves()

    def dup_wave(self):
        self._apply_group_fields()
        waves = self._waves()
        if 0 <= self.wave_list.index < len(waves):
            waves.insert(self.wave_list.index + 1,
                         [list(g) for g in waves[self.wave_list.index]])
        self._refresh_waves()

    def clear_wave(self):
        self._apply_group_fields()
        waves = self._waves()
        if 0 <= self.wave_list.index < len(waves):
            waves[self.wave_list.index] = []
        self._refresh_waves()

    def add_group(self):
        self._apply_group_fields()
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
        self._apply_group_fields()
        waves = self._waves()
        idx = self.wave_list.index
        if 0 <= idx < len(waves) and 0 <= self.group_list.index < len(waves[idx]):
            waves[idx].pop(self.group_list.index)
        self._refresh_waves()

    # -- list buttons -------------------------------------------------------
    def new(self):
        self.apply_current()
        self.record("new")
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
        self.record("duplicate")
        data = deepcopy(self.current)
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
        self.record("delete")
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
                            key=lambda lid: [i.get("order", 0) for i in self.items
                                             if i.get("id") == lid])
            race = dict(race)
            race["levels"] = linked
            self.app.content.save_race(race)
        self.app.content.reload()
        art.clear_caches()
        self.mark_saved()
        self.app.set_status("Levels: saved {} entries".format(len(self.items)))

    # -- events -------------------------------------------------------------
    def _resize_to_fields(self):
        """Apply a typed grid W / H to the canvas (undoable, like a paint)."""
        width = max(1, int(self.fields["width"].value or 0))
        height = max(1, int(self.fields["height"].value or 0))
        if (width, height) == (self.map.width, self.map.height):
            return False
        self.record("resize")
        self.map.resize(width, height)
        self._sync_size_fields()
        return True

    def handle_event(self, event):
        action = self.undo_key(event)
        if action is not None:
            self.undo() if action == "undo" else self.redo()
            return True
        if self.map.handle_event(event):
            # a paint / pan / zoom: the canvas is the document until we sync it
            if not self._restoring:
                self.apply_current()
            return True
        if self.list.handle_event(event):        # selection is never undoable
            return True
        self._recorded = False
        before = self._signature()
        handled = self._dispatch(event)
        if not handled:
            return False
        self._resize_to_fields()
        if not self._recorded and not self._restoring \
                and before != self._signature():
            self.record("edit")
            self.app.set_status("Levels: change recorded ({})".format(
                self.history.status()), W.DIM)
        # keep items (grid included) in lock-step with the widgets and canvas
        if not self._restoring:
            self.apply_current()
        return True

    def _dispatch(self, event):
        for w in (self.wave_list, self.group_list):
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
                self._apply_group_fields()
                return True
        if self.avail_sel.handle_event(event) or self.enemy_sel.handle_event(event):
            return True
        return self._palette_click(event)

    # -- palette ------------------------------------------------------------
    def palette_rects(self):
        """``[(rect, grid_char), ...]`` for every swatch, in draw order."""
        entries = [(t.get("char", "?")) for t in self.app.terrain_tab.items]
        entries = entries + ["S", "B"]
        rects = []
        for i, ch in enumerate(entries):
            rect = pygame.Rect(L.MAP_X + (i % L.PAL_COLS) * L.PAL_PITCH,
                               self.palette_top + (i // L.PAL_COLS) * L.PAL_ROW_H,
                               L.PAL_SWATCH, L.PAL_SWATCH)
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
            else:
                terr = lookup.get(ch)
                if terr is None:
                    continue
                img = art.sprite(terr.get("sprite") or
                                 {"kind": "pack", "tile": terr.get("base", 157)},
                                 44, terr.get("tint"))
            self.ctx.canvas.blit(img, rect)
            sel = self.map.selected == ch
            pygame.draw.rect(self.ctx.canvas, W.ACCENT if sel else W.EDGE,
                             rect, 3 if sel else 1)
            _text(self.ctx, ch, (rect.x + 2, rect.y + 1), (255, 255, 255))
            if ch not in ("S", "B"):
                name = lookup.get(ch, {}).get("name", ch)
                _text(self.ctx, str(name)[:9], (rect.x, rect.bottom + 1), W.DIM)

    # -- drawing ------------------------------------------------------------
    def draw(self):
        self.ctx.canvas.fill((0, 0, 0))
        self._draw_title()
        self.list.draw(self.ctx.canvas)
        for b in self.list_buttons:
            b.draw(self.ctx.canvas)
        self._draw_history_status(L.LIST_X, L.LIST_HINT_Y, L.LEVELS_LIST_W)

        self.map.draw()
        self._draw_map_readout()
        self._draw_palette()
        for b in self.zoom_buttons:
            b.draw(self.ctx.canvas)
        _right_text(self.ctx, "{} px / cell   -   {}".format(
            self.map.cell, self._visible_cells()), L.MAP_X + L.MAP_W,
            self.zoom_y + 5, W.OK if self.map.fits else W.ACCENT)

        _text(self.ctx, "Available units", (self.avail_sel.rect.x, L.SEL_LABEL_Y))
        _text(self.ctx, "Enemy pool", (self.enemy_sel.rect.x, L.SEL_LABEL_Y))
        self.avail_sel.draw(self.ctx.canvas)
        self.enemy_sel.draw(self.ctx.canvas)

        for field in self.fields.values():
            field.draw(self.ctx.canvas)
        _text(self.ctx, "Waves", (L.LEVEL_FORM_X, L.WAVE_LABEL_Y))
        self.wave_list.draw(self.ctx.canvas)
        for b in self.wave_buttons:
            b.draw(self.ctx.canvas)
        _text(self.ctx, "Units in selected wave",
              (L.LEVEL_FORM_X, L.GROUP_LABEL_Y))
        self.group_list.draw(self.ctx.canvas)
        for b in self.group_buttons:
            b.draw(self.ctx.canvas)
        for field in (self.g_unit, self.g_count, self.g_interval):
            field.draw(self.ctx.canvas)
        _text(self.ctx, "space+drag / middle / right drag pans",
              (L.LEVEL_FORM_X, L.GROUP_FIELD_Y + 34), W.DIM)

    def _draw_map_readout(self):
        status = "path OK" if self.map.path_ok else "NO PATH from S to B"
        colour = W.OK if self.map.path_ok else W.BAD
        _text(self.ctx, "Map {} x {} cells   -   {}".format(
            self.map.width, self.map.height, status), (L.MAP_X, L.TOP), colour)
        _right_text(self.ctx, "wheel: zoom   drag: pan   Ctrl+Z: undo",
                    L.MAP_X + L.MAP_W, L.TOP, W.DIM)

    def _visible_cells(self):
        x0, y0, x1, y1 = self.map.visible_range()
        return "{}x{} of {}x{}".format(x1 - x0 + 1, y1 - y0 + 1,
                                      self.map.width, self.map.height)


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
            "Save act on the current list.  Undo / Redo sit under them, and",
            "Ctrl+Z / Ctrl+Y (Ctrl+Shift+Z) work anywhere on a tab.",
            "Save writes JSON to content/ and also keeps files tidy by removing",
            "deleted entries.  A '*' next to a tab title means unsaved changes.",
            "",
            "Undo: every mutating action (paint stroke, field edit, wave edit,",
            "resize, new/delete) stores the whole document as it was *before*",
            "the change, up to 50 steps.  Undo puts it back into the list, the",
            "widgets and the map.  Zoom, pan and picking a different list row",
            "are not edits, so they never take an undo step.",
            "",
            "Map canvas (Levels tab):",
            "  The panel is fixed; the cell size is the zoom (6..48 px).",
            "  Mouse wheel over the map zooms, keeping the point under the",
            "  cursor fixed.  'zoom -' / 'zoom +' / 'fit map' / 'top left' are",
            "  the same controls, for trackpads without a wheel.",
            "  Pan: drag with the middle mouse button, hold Space and drag",
            "  with the left button, or right-drag.  A plain right *click*",
            "  still erases a cell back to grass, so a pan is never mistaken",
            "  for a paint stroke.  The corner box shows where you are.",
            "  Left click paints the selected terrain, left drag paints a",
            "  stroke.  Only the visible cells are drawn, so a 60x40 map",
            "  stays smooth.  'grid W' / 'grid H' resize the map.",
            "  A yellow line previews the route; NO PATH means unplayable.",
            "",
            "Terrain:  a grid character maps to a base tile + optional overlay.",
            "  buildable = players may place defenders there.",
            "  walkable  = ground enemies may path through it.",
            "  The spawn 'S' and base 'B' characters are reserved.",
            "  Click the base / overlay preview for a static image or animation.",
            "",
            "Units:  one schema for both sides.",
            "  side=defender -> placed by the player (a 'tower'); side=attacker ->",
            "    spawned by enemy waves.",
            "  movement: static | chase | route | direct | hunt",
            "  attack: none | melee | projectile",
            "  shots / attack: how many projectiles one attack fires.",
            "  Upgrade paths: a defender picks one branch per level-up instead",
            "    of one linear ladder.  Each branch has an id, a name, four",
            "    gain multipliers (dmg / range / rate / hp, 1.0 = unchanged)",
            "    and an additive '+shots'.  'default' restores the five",
            "    shipped branches.  Every gain is written out, so what you",
            "    type survives save + reload.",
            "  sprite: CLICK THE PREVIEW to set art - static image or an",
            "    animation split into idle / walk / attack / death.",
            "  tint: overrides the race tint (handy for recoloured variants).",
            "",
            "Races:  a campaign.  Pick which defender units are on offer and",
            "which attackers the levels use.  The base hero is the defender",
            "summoned when an attacker reaches the base ((none) to clear it).",
            "Levels are attached from the Levels tab.",
            "",
            "Levels:  the right-hand form holds the economy and the grid size.",
            "  gold / sec is passive income (0..{:g}, the default is {:g}) -",
            "  the main per-level difficulty knob.".format(
                S.GOLD_PER_SEC_MAX, S.DEFAULT_GOLD_PER_SEC),
            "  'Available units' are the level's shop; 'Enemy pool' its",
            "  attacker roster.  Build waves below: each wave holds unit",
            "  groups (unit, count, spawn gap seconds).",
            "",
            "Everything saves to content/ - the game reads the same files.",
        ]
        self.scroll = 0
        self._heights = [34 if l == "Big Tower - Level Designer" else 24
                         for l in self.lines]

    def _max_scroll(self):
        total = sum(self._heights)
        return max(0, L.TOP + total - self.ctx.canvas.get_height() + 12)

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, min(self._max_scroll(), self.scroll - event.y * 40))
            return True
        return False

    def draw(self):
        self.ctx.canvas.fill((0, 0, 0))
        y = L.TOP - self.scroll
        for line, h in zip(self.lines, self._heights):
            if y + h >= L.TOP and y <= self.ctx.canvas.get_height():
                key = "big" if h == 34 else "default"
                color = W.TEXT if not line.startswith("  ") else W.DIM
                _text(self.ctx, line, (40, y), color, key)
            y += h
        if self._max_scroll() > 0:
            _text(self.ctx, "scroll with the mouse wheel", (40, L.TITLE_Y), W.ACCENT)
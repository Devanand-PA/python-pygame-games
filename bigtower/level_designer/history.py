"""Undo / redo for the designer.

The designer edits small JSON documents, so the simplest *correct* undo is to
remember the whole document as it was before each mutating action and put it
back wholesale on undo.  A partial/incremental undo would have to reason about
which of twenty widget edits produced a given grid cell; a snapshot cannot.

The contract is deliberately tiny::

    history = History(snapshot, restore)     # snapshot() -> plain data
    history.record()                          # ...about to change something
    history.undo() / history.redo()

``record`` is called *before* the mutation, so the stack holds the state to go
back *to*.  ``snapshot`` must return a deep, self-contained structure (the tabs
use :func:`copy.deepcopy` of their item lists).  ``restore`` re-reads such a
snapshot into the item list *and* back into the widgets, the map canvas and the
dirty flag, which is why each tab implements its own.

Camera zoom / pan and list selection deliberately never call ``record`` --
neither changes the document.
"""
from __future__ import annotations


class History:
    """A capped pair of snapshot stacks (undo on the left, redo on the right)."""

    LIMIT = 50

    def __init__(self, snapshot, restore, on_change=None):
        self.snapshot = snapshot
        self.restore = restore
        self.on_change = on_change
        self.undo_stack = []
        self.redo_stack = []
        self.label = ""

    # -- writing -------------------------------------------------------------
    def record(self, label=""):
        """Remember the current state; call this *before* mutating."""
        self.record_state(self.snapshot(), label)

    def record_state(self, state, label=""):
        """Push a snapshot captured earlier.

        Used for actions whose effect is only known afterwards - a map paint
        stroke, say: the pre-stroke state is grabbed on button-down and pushed
        on button-up, but only if the stroke changed anything.
        """
        self.undo_stack.append(state)
        if len(self.undo_stack) > self.LIMIT:
            del self.undo_stack[0]
        self.redo_stack.clear()
        if label:
            self.label = label

    # -- reading -------------------------------------------------------------
    @property
    def can_undo(self):
        return bool(self.undo_stack)

    @property
    def can_redo(self):
        return bool(self.redo_stack)

    def undo(self):
        if not self.undo_stack:
            return False
        self.redo_stack.append(self.snapshot())
        self.restore(self.undo_stack.pop())
        self._changed()
        return True

    def redo(self):
        if not self.redo_stack:
            return False
        self.undo_stack.append(self.snapshot())
        self.restore(self.redo_stack.pop())
        self._changed()
        return True

    def clear(self):
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.label = ""

    def status(self):
        """One short line for the status bar, or '' when there is nothing."""
        if self.can_undo:
            redo = "  (redo {} ready)".format(len(self.redo_stack)) if self.redo_stack else ""
            return "{} undo steps{} - Ctrl+Z".format(len(self.undo_stack), redo)
        if self.can_redo:
            return "{} redo steps - Ctrl+Y".format(len(self.redo_stack))
        return "no undo history"

    def _changed(self):
        if self.on_change is not None:
            self.on_change(self)
"""A reusable drop target.

Pure presentation widget: it converts drop events into a ``list[Path]`` and
emits it. What happens next (dedup, history, drag-out) is the ViewModel's
job — never this widget's.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from ..colors import (
    BORDER_SUBTLE,
    ON_SURFACE_VARIANT,
    PRIMARY_ACTIVE,
    PRIMARY_TINT,
    SURFACE,
    TEXT_SECONDARY,
    rgba,
)

_IDLE_STYLE = (
    f"QFrame {{ background-color: {rgba(SURFACE, 235)};"
    f" border: 2px dashed {rgba(BORDER_SUBTLE)}; border-radius: 8px; }}"
    f"QLabel {{ color: {rgba(TEXT_SECONDARY)}; font-size: 12px; }}"
)
_ACTIVE_STYLE = (
    f"QFrame {{ background-color: {rgba(PRIMARY_TINT)};"
    f" border: 2px dashed {rgba(PRIMARY_ACTIVE)}; border-radius: 8px; }}"
    f"QLabel {{ color: {rgba(ON_SURFACE_VARIANT)}; font-size: 12px; }}"
)


class DropZone(QFrame):
    """Drop target that reports dropped paths and drag-hover state."""

    files_dropped = Signal(object)  # list[Path]
    drag_active = Signal(bool)      # True while a file drag hovers

    def __init__(self, hint: str = "Drop Your File(s) Here", parent=None):
        super().__init__(parent)
        # Required: drag events are only delivered to widgets that accept
        # drops.
        self.setAcceptDrops(True)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(_IDLE_STYLE)

        layout = QVBoxLayout(self)
        self._label = QLabel(hint, self)
        self._label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._label)

    # -- drag events --------------------------------------------------------
    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            self.drag_active.emit(True)
            self.setStyleSheet(_ACTIVE_STYLE)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:
        self.drag_active.emit(False)
        self.setStyleSheet(_IDLE_STYLE)

    def dropEvent(self, event) -> None:
        self.drag_active.emit(False)
        self.setStyleSheet(_IDLE_STYLE)
        paths = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                paths.append(Path(path))
        if paths:
            self.files_dropped.emit(paths)
        event.acceptProposedAction()

    # -- api -----------------------------------------------------------------
    def set_hint(self, text: str) -> None:
        """Change the idle-state label (e.g. 'Drag Your N Files Out')."""
        self._label.setText(text)

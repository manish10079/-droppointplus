"""A compact card showing one file: type icon + name (+ size, + remove).

Renders a ``FileItem``; emits ``remove_requested`` so a parent can decide
what removing means. No file logic lives here (``format_size`` only reads
``path.stat()`` for display).
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from ..colors import (
    BORDER_SUBTLE,
    ERROR,
    ON_SURFACE_VARIANT,
    SURFACE_CONTAINER,
    TEXT_SECONDARY,
    rgba,
)
from ..icons import file_type_icon
from ..models import FileItem

logger = logging.getLogger(__name__)

_CARD_STYLE = (
    f"QFrame {{ background-color: {rgba(SURFACE_CONTAINER)};"
    f" border: 1px solid {rgba(BORDER_SUBTLE)}; border-radius: 6px; }}"
    f"QLabel {{ color: {rgba(ON_SURFACE_VARIANT)}; font-size: 12px; }}"
    f"QPushButton {{ border: none; color: {rgba(TEXT_SECONDARY)};"
    " font-size: 12px; }"
    f"QPushButton:hover {{ color: {rgba(ERROR)}; }}"
)


def format_size(path: Path) -> str:
    """Human-readable file size (``12.4 MB``); ``''`` when it can't be read.

    A missing/unreadable file is logged (per the development skills, errors
    are never silently swallowed) but the card still renders with no size.
    """
    try:
        size = path.stat().st_size
    except OSError:
        logger.warning("could not stat %s for size display", path, exc_info=True)
        return ""
    for unit, divisor in (("GB", 1024**3), ("MB", 1024**2), ("KB", 1024)):
        if size >= divisor:
            return f"{size / divisor:.1f} {unit}"
    return f"{size} B"


class FileCard(QFrame):
    """Renders a single ``FileItem`` in a list/grid."""

    remove_requested = Signal(object)  # the FileItem

    def __init__(
        self,
        item: FileItem,
        removable: bool = False,
        icon_size: int = 24,
        show_size: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self._item = item
        self.setStyleSheet(_CARD_STYLE)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        icon = QLabel(self)
        icon.setPixmap(file_type_icon(item.file_type, icon_size).pixmap(
            icon_size, icon_size))
        layout.addWidget(icon)

        name = QLabel(item.path.name, self)
        name.setToolTip(str(item.path))
        name.setMinimumWidth(0)  # let the layout truncate before the size/button
        layout.addWidget(name, 1)

        if show_size:
            size_label = QLabel(format_size(item.path), self)
            size_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            size_label.setStyleSheet(
                f"color: {rgba(TEXT_SECONDARY)}; font-size: 11px;"
            )
            size_label.setMinimumWidth(52)
            layout.addWidget(size_label)

        if removable:
            remove_btn = QPushButton("✕", self)
            remove_btn.setFixedSize(18, 18)
            remove_btn.setFlat(True)
            remove_btn.setToolTip("Remove from collection")
            remove_btn.clicked.connect(
                lambda: self.remove_requested.emit(self._item))
            layout.addWidget(remove_btn)

    # -- api -----------------------------------------------------------------
    @property
    def item(self) -> FileItem:
        return self._item

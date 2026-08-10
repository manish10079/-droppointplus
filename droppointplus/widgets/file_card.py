"""A compact card showing one file: type icon + name (+ optional remove).

Renders a ``FileItem``; emits ``remove_requested`` so a parent can decide
what removing means. No file logic lives here.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
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

_CARD_STYLE = (
    f"QFrame {{ background-color: {rgba(SURFACE_CONTAINER)};"
    f" border: 1px solid {rgba(BORDER_SUBTLE)}; border-radius: 6px; }}"
    f"QLabel {{ color: {rgba(ON_SURFACE_VARIANT)}; font-size: 12px; }}"
    f"QPushButton {{ border: none; color: {rgba(TEXT_SECONDARY)};"
    " font-size: 12px; }"
    f"QPushButton:hover {{ color: {rgba(ERROR)}; }}"
)


class FileCard(QFrame):
    """Renders a single ``FileItem`` in a list/grid."""

    remove_requested = Signal(object)  # the FileItem

    def __init__(
        self,
        item: FileItem,
        removable: bool = False,
        icon_size: int = 24,
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
        name.setMinimumWidth(0)  # let the layout truncate before the button
        layout.addWidget(name, 1)

        if removable:
            remove_btn = QPushButton("✕", self)
            remove_btn.setFixedSize(18, 18)
            remove_btn.setFlat(True)
            remove_btn.clicked.connect(lambda: self.remove_requested.emit(self._item))
            layout.addWidget(remove_btn)

    # -- api -----------------------------------------------------------------
    @property
    def item(self) -> FileItem:
        return self._item

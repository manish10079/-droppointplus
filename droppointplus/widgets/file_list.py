"""Scrollable roster of collected files — the holding state's list view.

Presentation-only (per the ``widgets/`` skill): renders ``FileCard`` rows and
forwards ``remove_requested`` for each item; the ViewModel decides what
removing means. No business logic lives here.

Scrolling is wheel-driven with a thin scroll indicator. Deliberately NOT a
``QScrollArea``: its viewport would swallow the mouse presses the shelf
needs for window-drag / drag-out, which rely on unhandled presses
propagating from the rows up to the window.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QWheelEvent
from PySide6.QtWidgets import QLabel, QWidget

from .. import colors
from ..models import FileItem
from .file_card import FileCard

ROW_H = 40
ROW_SPACING = 5
HEADER_H = 22
HINT_H = 20
MARGIN = 8
_SCROLLBAR_W = 4


class FileList(QWidget):
    """Scrollable collection list; ``remove_requested`` fires per item."""

    remove_requested = Signal(object)  # FileItem

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[FileItem] = []
        self._rows: list[FileCard] = []
        self._offset = 0

        self._header = QLabel(self)
        self._header.setStyleSheet(
            f"color: {colors.rgba(colors.TEXT_SECONDARY)};"
            " font-size: 11px; font-weight: 600; letter-spacing: 2px;"
        )

        self._hint = QLabel("Drag out to move or copy the collection", self)
        self._hint.setAlignment(Qt.AlignCenter)
        self._hint.setStyleSheet(
            f"color: {colors.rgba(colors.TEXT_SECONDARY)}; font-size: 11px;"
        )

        self._relayout()

    # -- public api ---------------------------------------------------------
    def set_items(self, items: list[FileItem]) -> None:
        """Replace the roster (cheap no-op when unchanged)."""
        if items == self._items:
            return
        self._items = list(items)
        for row in self._rows:
            row.deleteLater()
        self._rows = []
        for item in self._items:
            card = FileCard(item, removable=True, parent=self)
            card.remove_requested.connect(self.remove_requested.emit)
            self._rows.append(card)
        self._offset = min(self._offset, self._max_offset())
        self._relayout()

    # -- internals ----------------------------------------------------------
    def _rows_height(self) -> int:
        n = len(self._rows)
        return n * ROW_H + (n - 1) * ROW_SPACING if n else 0

    def _view_height(self) -> int:
        return self.height() - HEADER_H - HINT_H - 2 * MARGIN

    def _max_offset(self) -> int:
        return max(0, self._rows_height() - self._view_height())

    def _relayout(self) -> None:
        n = len(self._items)
        self._header.setText(
            f"COLLECTION / {n} item{'s' if n != 1 else ''}"
        )
        self._header.setGeometry(MARGIN, 4, self.width() - 2 * MARGIN, HEADER_H)

        top = HEADER_H + MARGIN
        bottom = self.height() - HINT_H - MARGIN
        for i, card in enumerate(self._rows):
            y = top + i * (ROW_H + ROW_SPACING) - self._offset
            card.setGeometry(
                MARGIN, y,
                self.width() - 2 * MARGIN - _SCROLLBAR_W, ROW_H,
            )
            card.setVisible(y < bottom and y + ROW_H > top)

        self._hint.setGeometry(
            MARGIN, self.height() - HINT_H - 2,
            self.width() - 2 * MARGIN, HINT_H,
        )
        self.update()

    def resizeEvent(self, event) -> None:
        self._relayout()
        super().resizeEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        max_offset = self._max_offset()
        if max_offset <= 0:
            event.ignore()
            return
        # Touchpads report pixel deltas (angleDelta may be 0); classic wheels
        # report notched angle deltas. Honour whichever is non-zero.
        pixels = event.pixelDelta().y()
        if pixels:
            self._offset = max(0, min(max_offset, self._offset - pixels))
        else:
            steps = event.angleDelta().y() // 120
            if not steps:
                event.ignore()
                return
            self._offset = max(0, min(
                max_offset,
                self._offset - steps * (ROW_H + ROW_SPACING),
            ))
        self._relayout()
        event.accept()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        max_offset = self._max_offset()
        if max_offset <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        track_h = self._view_height()
        track_y = HEADER_H + MARGIN
        bar_h = max(24, round(track_h * track_h / (track_h + max_offset)))
        ratio = self._offset / max_offset
        painter.setPen(Qt.NoPen)
        painter.setBrush(colors.with_alpha(colors.TEXT_SECONDARY, 150))
        x = self.width() - MARGIN // 2
        painter.drawRoundedRect(
            x, track_y + round((track_h - bar_h) * ratio),
            _SCROLLBAR_W, bar_h, 1.5, 1.5,
        )

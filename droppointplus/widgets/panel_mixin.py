"""Shared chrome for secondary windows (Settings, History).

The shelf window is a frameless translucent rounded panel; these windows
reuse the same design language so the whole app looks like one surface. A
``PanelMixin`` (mix into a ``QWidget``/``QDialog`` subclass) provides:

* frameless + translucent flags and a fixed size;
* a header with a title and a close button (same look as the shelf header);
* header-drag-to-move (same 8 px threshold as the shelf);
* ``_paint_panel`` — the rounded ``SURFACE`` fill + header/footer dividers.

Every colour comes from ``colors``; nothing is hardcoded here.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QWidget

from .. import colors

HEADER_H = 56
FOOTER_H = 48
RADIUS = 12
DRAG_START_THRESHOLD_PX = 8

_HEADER_BTN_STYLE = (
    f"QLabel {{ color: {colors.rgba(colors.ON_SURFACE_VARIANT)};"
    " font-size: 15px; border-radius: 11px; }"
    f"QLabel:hover {{ background-color:"
    f" {colors.rgba(colors.SURFACE_CONTAINER_HIGH)}; }}"
)


class _PanelHeaderButton(QLabel):
    """Small round header button (close, …) — same pattern as the shelf's."""

    clicked = Signal()

    def __init__(self, glyph: str | QPixmap, parent: QWidget, tooltip: str = ""):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)
        # QLabel does not enable WA_Hover by default; without it the
        # ``QLabel:hover`` stylesheet rule below never fires.
        self.setAttribute(Qt.WA_Hover, True)
        self.setStyleSheet(_HEADER_BTN_STYLE)
        if tooltip:
            self.setToolTip(tooltip)
        if isinstance(glyph, QPixmap):
            self.setPixmap(glyph)
        else:
            self.setText(glyph)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # Emit LAST and consume the event (see ShelfWindow._HeaderButton for
        # the lifetime rationale): the emit may close the panel, destroying
        # this widget's C++ peer while the handler still runs.
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        event.accept()


class PanelMixin:
    """Frameless translucent rounded panel — shared chrome for secondary
    windows. Mix into a ``QWidget``/``QDialog`` subclass and call
    ``self._init_panel(title, width, height, parent)`` at the top of
    ``__init__``; paint the background from ``paintEvent`` via
    ``self._paint_panel(painter)``.
    """

    def _init_panel(
        self,
        title: str,
        width: int,
        height: int,
        parent=None,
        always_on_top: bool = False,
    ) -> None:
        super().__init__(parent)
        flags = self.windowFlags() | Qt.FramelessWindowHint | Qt.Tool
        # Match the shelf: when "Always on top" is on, the shelf carries
        # WindowStaysOnTopHint and would otherwise pin itself above these
        # panels, hiding them. The panels must float at the same level.
        if always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(width, height)
        self.setWindowTitle(title)

        self._panel_title = QLabel(title, self)
        self._panel_title.setGeometry(
            24, (HEADER_H - 22) // 2, width - 120, 22
        )
        self._panel_title.setStyleSheet(
            f"color: {colors.rgba(colors.PRIMARY)};"
            " font-size: 18px; font-weight: 700;"
        )

        self._panel_close = _PanelHeaderButton("✕", self, tooltip="Close")
        self._panel_close.setGeometry(
            width - 48, (HEADER_H - 22) // 2, 22, 22
        )
        self._panel_close.clicked.connect(self.close)

        self._drag_start_pos = None   # press origin, window-local (threshold)
        self._press_global = None     # press origin, screen coords (smooth move)
        self._win_start_pos = None    # window top-left at press (for moving)
        self._drag_started = False
        self._win_dragging = False

    def _paint_panel(self, painter: QPainter, footer: bool = True) -> None:
        """Rounded SURFACE fill + header divider (+ optional footer divider)."""
        painter.setRenderHint(QPainter.Antialiasing)
        content = QRectF(0, 0, self.width(), self.height())
        painter.setBrush(colors.SURFACE)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(content, RADIUS, RADIUS)
        painter.setPen(QPen(colors.BORDER_SUBTLE, 1))
        painter.drawLine(
            QPointF(content.left() + 1, HEADER_H),
            QPointF(content.right() - 1, HEADER_H),
        )
        if footer:
            y = self.height() - FOOTER_H
            painter.drawLine(
                QPointF(content.left() + 1, y),
                QPointF(content.right() - 1, y),
            )

    # -- header drag (same semantics as the shelf window) -------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:
        # Only the header drags the panel; presses on the body fall through
        # to child widgets (form fields, the scroll list).
        if (
            event.button() == Qt.LeftButton
            and event.position().y() <= HEADER_H
        ):
            self._drag_start_pos = event.position().toPoint()
            self._press_global = event.globalPosition().toPoint()
            self._win_start_pos = self.pos()
            self._drag_started = False
            self._win_dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start_pos is None:
            super().mouseMoveEvent(event)
            return
        # Window-local positions stop changing once the window slides under
        # the cursor, so the MOVE must use screen (global) coords or the
        # window jumps once and then stalls.
        local_delta = event.position().toPoint() - self._drag_start_pos
        global_delta = event.globalPosition().toPoint() - self._press_global
        if (
            not self._drag_started
            and local_delta.manhattanLength() >= DRAG_START_THRESHOLD_PX
        ):
            self._drag_started = True
            self._win_dragging = True
            self.setCursor(Qt.ClosedHandCursor)
        if self._win_dragging:
            self.move(self._win_start_pos + global_delta)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._win_dragging:
            self.unsetCursor()
        self._drag_start_pos = None
        self._press_global = None
        self._win_start_pos = None
        self._drag_started = False
        self._win_dragging = False
        super().mouseReleaseEvent(event)

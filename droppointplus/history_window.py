"""History window — a full view of the recent instance drops.

Companion to the tray's History submenu: the tray shows the last 5 instances
as nested submenus; this window shows the same data (last 10 instances, each
with its collected files) in the shelf's dark panel design. Like the tray,
entries are display-only for now.

Presentation-only: reads ``history.last_instances`` and renders rows; no
business logic lives here.
"""

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from . import colors, history
from .models import FileItem
from .widgets.file_card import FileCard
from .widgets.panel_mixin import FOOTER_H, HEADER_H, PanelMixin

logger = logging.getLogger(__name__)

WINDOW_W = 380
WINDOW_H = 460
_BODY_X = 16
_BODY_W = WINDOW_W - 2 * _BODY_X

_SCROLL_QSS = (
    f"QScrollArea {{ border: none; background: transparent; }}"
    f"QScrollArea > QWidget > QWidget {{ background: transparent; }}"
    f"QScrollBar:vertical {{ background: transparent; width: 6px; margin: 2px; }}"
    f"QScrollBar::handle:vertical {{ background:"
    f" {colors.rgba(colors.TEXT_SECONDARY, 140)}; border-radius: 3px; }}"
    f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{"
    " height: 0; }"
    f"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{"
    " background: transparent; }"
)


class HistoryWindow(PanelMixin, QDialog):
    """Frameless dark panel listing the last few shelf instances' drops."""

    def __init__(self, parent=None, always_on_top: bool = False):
        self._init_panel(
            "History", WINDOW_W, WINDOW_H, parent,
            always_on_top=always_on_top,
        )
        self.setWindowTitle("History - DropPoint+")

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(_SCROLL_QSS)
        self._scroll.setGeometry(
            _BODY_X, HEADER_H + 8, _BODY_W, WINDOW_H - HEADER_H - FOOTER_H - 16
        )

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(4, 4, 8, 4)
        self._layout.setSpacing(6)
        self._scroll.setWidget(self._container)

        self._footer_hint = QLabel("Entries are display-only", self)
        self._footer_hint.setStyleSheet(
            f"color: {colors.rgba(colors.TEXT_SECONDARY)}; font-size: 11px;"
        )
        self._footer_hint.setAlignment(Qt.AlignCenter)
        self._footer_hint.setGeometry(
            0, WINDOW_H - FOOTER_H + 8, WINDOW_W, 20
        )

        self._refresh()

    # -- data --------------------------------------------------------------
    def _refresh(self) -> None:
        """Rebuild the rows from history (last 10 instances with files)."""
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        instances = history.last_instances(10)
        if not instances:
            empty = QLabel("No recent drops yet", self._container)
            empty.setStyleSheet(
                f"color: {colors.rgba(colors.TEXT_SECONDARY)};"
                " font-size: 13px;"
            )
            empty.setAlignment(Qt.AlignCenter)
            self._layout.addWidget(empty)
            return

        for instance in instances:
            files = instance.get("files") or []
            section = QLabel(self._format_timestamp(instance.get("instanceId")),
                             self._container)
            section.setStyleSheet(
                f"color: {colors.rgba(colors.TEXT_SECONDARY)};"
                " font-size: 11px; font-weight: 600; letter-spacing: 1px;"
            )
            self._layout.addWidget(section)
            for f in files:
                try:
                    item = FileItem.from_dict(f)
                except (KeyError, TypeError, ValueError):
                    logger.debug("skipping malformed history entry: %r", f)
                    continue
                # History rows are display-only and the source files may no
                # longer exist — hide sizes so no stat errors are logged.
                card = FileCard(
                    item, removable=False, icon_size=22, show_size=False,
                    parent=self._container,
                )
                self._layout.addWidget(card)

        self._layout.addStretch(1)

    @staticmethod
    def _format_timestamp(ts) -> str:
        """instanceId is a millisecond epoch — render as dd/mm/yyyy hh:mm."""
        try:
            dt = datetime.fromtimestamp(int(ts) / 1000)
            return dt.strftime("%d/%m/%Y %H:%M")
        except (ValueError, OSError, TypeError) as exc:
            logger.debug("unparseable history timestamp %r (%s)", ts, exc)
            return "Recent"

    # -- painting -----------------------------------------------------------
    def paintEvent(self, event) -> None:
        from PySide6.QtGui import QPainter

        painter = QPainter(self)
        self._paint_panel(painter)
        painter.end()
        super().paintEvent(event)

"""A progress indicator with a status line (for file operations).

Percent-based with an indeterminate mode; long-running file work should run
on a worker thread and drive this widget only through these setters (signals
across threads, per the development skills).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from ..colors import (
    BORDER_SUBTLE,
    ERROR,
    PRIMARY_ACTIVE,
    SURFACE_CONTAINER,
    TEXT_SECONDARY,
    rgba,
)

_BAR_STYLE = (
    f"QProgressBar {{ background-color: {rgba(SURFACE_CONTAINER)};"
    f" border: 1px solid {rgba(BORDER_SUBTLE)}; border-radius: 4px;"
    " height: 10px; }"
    f"QProgressBar::chunk {{ background-color: {rgba(PRIMARY_ACTIVE)};"
    " border-radius: 3px; }"
)


class ProgressWidget(QWidget):
    """Percent progress + status line + optional detail + optional Cancel."""

    cancel_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        self._bar = QProgressBar(self)
        self._bar.setRange(0, 100)
        self._bar.setTextVisible(False)
        self._bar.setStyleSheet(_BAR_STYLE)
        layout.addWidget(self._bar)

        self._status = QLabel("", self)
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setStyleSheet(
            f"color: {rgba(TEXT_SECONDARY)}; font-size: 11px;"
        )
        layout.addWidget(self._status)

        self._detail = QLabel("", self)
        self._detail.setAlignment(Qt.AlignCenter)
        self._detail.setStyleSheet(
            f"color: {rgba(TEXT_SECONDARY)}; font-size: 10px;"
        )
        layout.addWidget(self._detail)

        self._cancel_btn = QPushButton("Cancel", self)
        self._cancel_btn.setCursor(Qt.PointingHandCursor)
        self._cancel_btn.setStyleSheet(
            f"QPushButton {{ background: transparent;"
            f" color: {rgba(TEXT_SECONDARY)}; font-size: 11px;"
            f" border: 1px solid {rgba(BORDER_SUBTLE)}; border-radius: 10px;"
            " padding: 1px 12px; }"
            f"QPushButton:hover {{ color: {rgba(ERROR)};"
            f" border-color: {rgba(ERROR)}; }}"
        )
        self._cancel_btn.clicked.connect(self.cancel_requested.emit)
        self._cancel_btn.hide()
        layout.addWidget(self._cancel_btn, 0, Qt.AlignHCenter)

    # -- api -----------------------------------------------------------------
    def set_progress(self, percent: float) -> None:
        """Set a determinate 0–100 percent value (clamped)."""
        self._bar.setRange(0, 100)
        self._bar.setValue(max(0, min(100, round(percent))))

    def set_indeterminate(self, active: bool) -> None:
        """Marquee mode (range 0–0) when the total is unknown."""
        self._bar.setRange(0, 0 if active else 100)

    def set_status(self, text: str) -> None:
        """Update the status line (e.g. 'Moving 3 of 12…')."""
        self._status.setText(text)

    def set_detail(self, text: str) -> None:
        """Update the smaller detail line (e.g. '2.4 MB/s · ~3s left')."""
        self._detail.setText(text)

    def set_cancellable(self, active: bool) -> None:
        """Show/hide the Cancel button."""
        self._cancel_btn.setVisible(active)

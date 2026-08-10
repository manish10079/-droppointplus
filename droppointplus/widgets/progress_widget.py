"""A progress indicator with a status line (for file operations).

Percent-based with an indeterminate mode; long-running file work should run
on a worker thread and drive this widget only through these setters (signals
across threads, per the development skills).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

from ..colors import (
    BORDER_SUBTLE,
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
    """Percent progress + status text, optionally indeterminate."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

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

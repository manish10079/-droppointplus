"""Design tokens — the single source of truth for every colour in DropPoint+.

No UI module should hardcode a colour: painting code and stylesheets must
reference these constants, so a token means the same thing everywhere it is
used and the whole app can be re-themed in one place.

The palette follows the dark Material-3 scheme from the design mockups in
``ui design/*/code.html`` (e.g. ``empty_drop_zone``).
"""

from __future__ import annotations

from PySide6.QtGui import QColor

# --- Base layers -----------------------------------------------------------
SURFACE = QColor(0x11, 0x13, 0x17)                # window / panel background
SURFACE_LOW = QColor(0x1A, 0x1C, 0x20)            # footer bar
SURFACE_CONTAINER = QColor(0x1E, 0x20, 0x24)      # cards, progress groove
SURFACE_CONTAINER_HIGH = QColor(0x28, 0x2A, 0x2E)  # icon circle, button hover

# --- Outlines / borders ----------------------------------------------------
BORDER_SUBTLE = QColor(0x2D, 0x32, 0x3E)          # dashed drop-zone border (idle)

# --- Primary (accent) ------------------------------------------------------
PRIMARY = QColor(0xCA, 0xBE, 0xFF)                # brand, download icon, accents
PRIMARY_ACTIVE = QColor(0x7C, 0x5C, 0xFF)         # drop-zone border while dragging
PRIMARY_TINT = QColor(0x7C, 0x5C, 0xFF, 13)       # rgba(124,92,255,0.05) hover wash

# --- Text ------------------------------------------------------------------
TEXT_PRIMARY = QColor(0xF5, 0xF5, 0xF7)           # headlines
ON_SURFACE_VARIANT = QColor(0xC9, 0xC4, 0xD8)     # body / secondary text
TEXT_SECONDARY = QColor(0x9C, 0xA3, 0xAF)         # hints, item counts, icons

# --- Status ----------------------------------------------------------------
SUCCESS = QColor(0x10, 0xB9, 0x81)
ERROR = QColor(0xEF, 0x44, 0x44)

# --- Window chrome ---------------------------------------------------------
GLOW_ALPHA_STEP = 7        # per-ring opacity of the drag-over outer glow
DIVIDER_ALPHA = 60         # faint rule above the footer hint


def with_alpha(color: QColor, alpha: int) -> QColor:
    """Return a copy of ``color`` with the given 0–255 opacity (clamped)."""
    return QColor(color.red(), color.green(), color.blue(),
                  max(0, min(255, alpha)))


def rgba(color: QColor, alpha: int | float | None = None) -> str:
    """Return an ``rgba(r, g, b, a)`` stylesheet string for ``color``.

    ``alpha`` overrides the colour's own alpha: pass an int 0–255 or a float
    0.0–1.0 (floats are scaled to 0–255). Omit it to keep the colour's alpha.
    Values are clamped to 0–255 so invalid QSS can never be produced.
    """
    if alpha is None:
        alpha = color.alpha()
    elif isinstance(alpha, float):
        alpha = round(alpha * 255)
    alpha = max(0, min(255, alpha))
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {alpha})"

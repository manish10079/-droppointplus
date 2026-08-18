"""Resizable-window tests.

The shelf, Settings and History windows are frameless and resizable
between min/max bounds; the children re-lay from the current size and the
edges are drag handles (frameless windows have no native resize border).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from droppointplus.app_config import ConfigManager
from droppointplus.history_window import HistoryWindow
from droppointplus.settings_dialog import SettingsDialog
from droppointplus.shelf_window import (
    MAX_H,
    MAX_W,
    MIN_H,
    MIN_W,
    _EDGE_BOTTOM,
    _EDGE_RIGHT,
)
from droppointplus.windows import WindowManager

_APP: QApplication | None = None


@pytest.fixture(autouse=True)
def _flush_qt_events():
    """Flush deferred deletions after every test (see test_smoke)."""
    yield
    app = QApplication.instance()
    if app is not None:
        app.processEvents()


def _app() -> QApplication:
    global _APP
    if _APP is None:
        _APP = QApplication.instance() or QApplication([])
        _APP.setQuitOnLastWindowClosed(False)
    return _APP


def test_shelf_window_resizes_between_bounds() -> None:
    _app()
    windows = WindowManager(ConfigManager())
    win = windows.create_window()
    try:
        assert (win.minimumWidth(), win.minimumHeight()) == (MIN_W, MIN_H)
        assert (win.maximumWidth(), win.maximumHeight()) == (MAX_W, MAX_H)

        # Growing re-lays header chrome, the drop rect and the footer.
        win.resize(600, 700)
        assert win._btn_close.x() == win.width() - 48
        assert win._btn_settings.x() == win.width() - 78
        assert win._btn_history.x() == win.width() - 108
        assert win._drop_rect().width() == win.width() - 2 * 24
        assert win._drop_rect().height() == win.height() - 56 - 48 - 2 * 24
        assert win._btn_copy.y() == win.height() - 48 + 11
        assert win._file_list.width() == round(win._drop_rect().width()) - 20

        # Resize is clamped to the bounds.
        win.resize(9999, 9999)
        assert (win.width(), win.height()) == (MAX_W, MAX_H)
        win.resize(1, 1)
        assert (win.width(), win.height()) == (MIN_W, MIN_H)
    finally:
        win.close()


def test_shelf_edge_resize_math() -> None:
    _app()
    windows = WindowManager(ConfigManager())
    win = windows.create_window()
    try:
        start = win.geometry()
        # Drag the bottom-right corner outward by 50×60 px.
        win._resizing = _EDGE_RIGHT | _EDGE_BOTTOM
        win._resize_geometry = start
        win._resize_global = QPoint(start.right(), start.bottom())
        win._apply_resize(QPoint(start.right() + 50, start.bottom() + 60))
        assert win.width() == start.width() + 50
        assert win.height() == start.height() + 60

        # Dragging a left edge keeps the right edge fixed (x follows).
        win.resize(MIN_W, MIN_H)
        start = win.geometry()
        win._resizing = _EDGE_RIGHT
        win._resize_geometry = start
        win._resize_global = QPoint(start.right(), start.center().y())
        win._apply_resize(QPoint(start.right() + 120, start.center().y()))
        assert win.width() == start.width() + 120
        assert win.x() == start.x()  # left edge unmoved
    finally:
        win.close()


def test_settings_dialog_resizes_and_relays() -> None:
    _app()
    dlg = SettingsDialog(ConfigManager())
    dlg.show()
    _app().processEvents()  # hidden windows defer their resize events
    try:
        assert (dlg.width(), dlg.height()) == (600, 450)
        dlg.resize(800, 600)
        _app().processEvents()
        assert dlg._body.width() == dlg.width() - 2 * 28
        assert dlg._body.height() == dlg.height() - 56 - 48 - 32
        assert dlg._footer_container.y() == dlg.height() - 48
        assert dlg._footer_container.width() == dlg.width()
        assert dlg._panel_close.x() == dlg.width() - 48
    finally:
        dlg.close()


def test_history_window_resizes_and_relays() -> None:
    _app()
    win = HistoryWindow(always_on_top=False)
    win.show()
    _app().processEvents()  # hidden windows defer their resize events
    try:
        assert (win.width(), win.height()) == (380, 460)
        win.resize(600, 700)
        _app().processEvents()
        assert win._scroll.width() == win.width() - 2 * 16
        assert win._scroll.height() == win.height() - 56 - 48 - 16
        assert win._footer_hint.y() == win.height() - 48 + 8
        assert win._panel_close.x() == win.width() - 48
    finally:
        win.close()

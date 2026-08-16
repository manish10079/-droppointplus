"""Smoke tests — the app's core wiring boots without errors.

Runs offscreen (``QT_QPA_PLATFORM=offscreen``) so it works in CI on all three
OSes without a display. These are the Phase-5 smoke checks from the migration
plan: construct the components ``main()`` wires together and assert the basic
invariants, then quit. The full unit suite (config round-trip, history,
drag-out orchestration, transfer progress) is planned as the next pass.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from droppointplus.app_config import ConfigManager
from droppointplus.history_window import HistoryWindow
from droppointplus.settings_dialog import SettingsDialog
from droppointplus.tray import TrayIcon
from droppointplus.windows import WindowManager


_APP: QApplication | None = None


def _app() -> QApplication:
    """Return the process-wide QApplication, keeping a strong reference.

    Holding ``_APP`` at module level is deliberate: if the local reference
    in a test is the only one, CPython can garbage-collect the QApplication
    between tests. The next test then calls ``QApplication.instance()``,
    gets ``None``, and constructs a second QApplication — which Qt aborts
    with "already a QApplication instance exists" (seen as a pytest
    internal error, flaky on Linux).
    """
    global _APP
    if _APP is None:
        _APP = QApplication.instance() or QApplication([])
        _APP.setApplicationName("DropPoint+")
        _APP.setQuitOnLastWindowClosed(False)
    return _APP


def test_window_manager_spawns_and_closes() -> None:
    _app()
    windows = WindowManager(ConfigManager())
    assert windows.count == 0
    win = windows.create_window()
    assert windows.count == 1
    assert win.instance_id >= 0
    win.close()
    assert windows.count == 0


def test_shelf_carries_always_on_top_hint() -> None:
    _app()
    # Set explicitly: the persisted config (not the DEFAULT_CONFIG) is what
    # ConfigManager.get returns, and CI/dev machines may differ.
    config = ConfigManager()
    config.set("always_on_top", True)
    windows = WindowManager(config)
    win = windows.create_window()
    assert win.windowFlags() & Qt.WindowStaysOnTopHint
    win.close()

    config.set("always_on_top", False)
    win2 = windows.create_window()
    assert not (win2.windowFlags() & Qt.WindowStaysOnTopHint)
    win2.close()


def test_settings_dialog_builds() -> None:
    _app()
    dlg = SettingsDialog(ConfigManager())
    assert dlg.width() == 600 and dlg.height() == 450
    assert dlg.windowFlags() & Qt.FramelessWindowHint
    dlg.close()


def test_history_window_builds() -> None:
    _app()
    win = HistoryWindow(always_on_top=True)
    assert win.width() == 380 and win.height() == 460
    win.close()


def test_tray_quit_action_is_wired() -> None:
    _app()
    tray = TrayIcon(WindowManager(ConfigManager()), ConfigManager())
    assert tray._quit_action is not None
    assert tray._quit_action.text() == "Quit"
    tray.hide()

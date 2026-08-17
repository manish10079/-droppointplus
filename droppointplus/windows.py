"""Window manager: owns every open ShelfWindow instance.

Qt equivalent of the instance bookkeeping that was implicit in the Electron
app (every caller did ``new Instance().createNewWindow()``). Keeps a registry
so the global hotkey can implement toggle-vs-spawn semantics and the tray can
open new instances.
"""

from __future__ import annotations

import logging
import time
from typing import Callable

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from .app_config import ConfigManager
from .drag_detect import DragDetector, EdgeStrip
from .file_service import FileService
from .models import FileItem
from .shelf_view_model import ShelfViewModel
from .shelf_window import ShelfWindow

logger = logging.getLogger(__name__)

# Summon-on-drag teardown: hide quickly once the drag ends (fast visual
# feedback), then close the summoned instance completely ~1 s later.
HIDE_DELAY_MS = 250
CLOSE_DELAY_MS = 1000


class WindowManager(QObject):
    """Registry of all open shelf windows."""

    window_created = Signal(object)  # instance id (ms epoch — too large for Qt int)

    def __init__(
        self,
        config: ConfigManager,
        parent: QObject | None = None,
        open_settings: Callable[[], None] | None = None,
        open_history: Callable[[], None] | None = None,
    ):
        super().__init__(parent)
        self._config = config
        self._service = FileService()  # shared, constructor-injected into ViewModels
        self._open_settings = open_settings  # wired to each window's header gear
        self._open_history = open_history  # wired to each window's header clock
        self._windows: list[ShelfWindow] = []
        self._next_id = int(time.time() * 1000)  # parity with `+new Date()` in Window.js

        # Summon-on-drag state (see _enable_drag_summon): a detector that
        # watches for file drags anywhere (Windows), edge strips that catch
        # drags at the screen edge, and the shelf we most recently summoned.
        self._detector: DragDetector | None = None
        self._strips: list[EdgeStrip] = []
        self._summoned: ShelfWindow | None = None
        self._hide_timer: QTimer | None = None
        self._close_timer: QTimer | None = None
        self._hide_target: ShelfWindow | None = None
        self._close_target: ShelfWindow | None = None
        if config.get("show_on_drag"):
            self._enable_drag_summon()
        config.changed.connect(self._on_drag_config_changed)

    @property
    def windows(self) -> list[ShelfWindow]:
        return list(self._windows)

    @property
    def count(self) -> int:
        return len(self._windows)

    def create_window(self) -> ShelfWindow:
        view_model = ShelfViewModel(self._next_id, self._config, self._service)
        window = ShelfWindow(
            self._next_id, view_model, bool(self._config.get("always_on_top"))
        )
        self._next_id += 1
        window.closed_signal.connect(self._on_closed)
        view_model.files_changed.connect(self._on_files_changed)
        if self._open_settings is not None:
            window.settings_requested.connect(self._open_settings)
        if self._open_history is not None:
            window.history_requested.connect(self._open_history)
        self._windows.append(window)

        if self._config.get("open_at_cursor_position"):
            window.position_at_cursor()
        else:
            window.position_center()
        window.show()
        self.window_created.emit(window.instance_id)
        return window

    def _on_closed(self, window: ShelfWindow) -> None:
        if window in self._windows:
            self._windows.remove(window)

    def _on_files_changed(self, instance_id: int, files: list[FileItem]) -> None:
        logger.debug("instance %s holding %s file(s)", instance_id, len(files))

    # -- summon-on-drag -------------------------------------------------------
    def _on_drag_config_changed(self, key: str) -> None:
        """Live-toggle the feature from Settings (no restart)."""
        if key != "show_on_drag":
            return
        if self._config.get("show_on_drag"):
            self._enable_drag_summon()
        else:
            self._disable_drag_summon()

    def _enable_drag_summon(self) -> None:
        """Start the drag detector and edge strips (idempotent)."""
        if self._detector is None:
            self._detector = DragDetector(self)
            self._detector.drag_started.connect(self._on_drag_started)
            self._detector.drag_ended.connect(self._on_drag_ended)
        if not self._strips:
            for screen in QGuiApplication.screens():
                area = screen.availableGeometry()
                for edge in ("top", "bottom", "left", "right"):
                    strip = EdgeStrip(edge, area)
                    strip.drag_over.connect(self._summon_at_edge)
                    strip.paths_dropped.connect(self._on_strip_drop)
                    strip.show()
                    self._strips.append(strip)
        # Idle strips are click-through on Windows.
        self._on_drag_ended()

    def _disable_drag_summon(self) -> None:
        for timer in (self._hide_timer, self._close_timer):
            if timer is not None:
                timer.stop()
        self._hide_timer = None
        self._close_timer = None
        self._hide_target = None
        self._close_target = None
        if self._detector is not None:
            self._detector.shutdown()
            self._detector.deleteLater()
            self._detector = None
        for strip in self._strips:
            strip.deleteLater()
        self._strips.clear()

    def _on_drag_started(self) -> None:
        """A plausible file drag began — reveal a shelf near the cursor and
        make the edge strips hit-testable (Windows)."""
        self._summon_at_cursor()
        for strip in self._strips:
            strip.set_click_through(False)

    def _on_drag_ended(self) -> None:
        """The drag finished — schedule the auto-hide and put the strips back
        to click-through so they never block the screen edge."""
        self._schedule_auto_hide()
        for strip in self._strips:
            strip.set_click_through(True)

    def _reusable_shelf(self) -> ShelfWindow | None:
        """The most recent shelf that is empty and idle — the reuse target.

        A shelf hidden by a previous auto-hide is exactly this, so repeated
        drags reuse one instance instead of piling up windows.
        """
        for window in reversed(self._windows):
            vm = window.view_model
            if not vm.files and not vm.is_working:
                return window
        return None

    def _summon_shelf(self) -> ShelfWindow:
        """Reuse an idle shelf if one exists, else spawn; show and raise it."""
        window = self._reusable_shelf() or self.create_window()
        self._summoned = window
        window.show()
        window.raise_()
        return window

    def _summon_at_cursor(self) -> None:
        self._summon_shelf().position_at_cursor()

    def _summon_at_edge(self, edge: str, area) -> None:
        self._summon_shelf().position_at_edge(edge, area)

    def _on_strip_drop(self, paths: list) -> None:
        """Files were dropped directly on an edge strip — collect them into
        the shelf we summoned next to that edge (if any)."""
        if self._summoned is not None:
            self._summoned.view_model.add_paths(paths)

    def _schedule_auto_hide(self) -> None:
        """After the drag ends: hide the summoned shelf quickly, then close it
        completely ~1 s later.

        Both steps wait for the OS to deliver the drop event first (the
        hide) and then fully close the instance: if files landed in the
        shelf meanwhile it is no longer idle and stays open. The timers
        always target the shelf they were armed for, so a new drag in
        between simply re-arms them.
        """
        target = self._summoned
        if target is None:
            return
        self._hide_target = target
        self._close_target = target
        if self._hide_timer is None:
            self._hide_timer = QTimer(self)
            self._hide_timer.setSingleShot(True)
            self._hide_timer.timeout.connect(self._hide_if_idle)
        if self._close_timer is None:
            self._close_timer = QTimer(self)
            self._close_timer.setSingleShot(True)
            self._close_timer.timeout.connect(self._close_if_idle)
        self._hide_timer.start(HIDE_DELAY_MS)
        self._close_timer.start(CLOSE_DELAY_MS)

    def _hide_if_idle(self) -> None:
        """First phase: hide the summoned shelf once the drag is over."""
        self._hide_timer = None
        window, self._hide_target = self._hide_target, None
        if window is None:
            return
        if window.view_model.files or window.view_model.is_working:
            return  # a drop landed — it is a normal instance now
        window.hide()

    def _close_if_idle(self) -> None:
        """Second phase: close the summoned shelf completely (registry drop,
        window destroyed) so no hidden instance lingers."""
        self._close_timer = None
        window, self._close_target = self._close_target, None
        if window is None:
            return
        if window.view_model.files or window.view_model.is_working:
            return
        window.close()

    def _focused(self) -> ShelfWindow | None:
        # Note: for Qt.Tool / WA_ShowWithoutActivating windows,
        # QApplication.focusWindow() is often None — the caller falls back to
        # the most recently created window. That is intentional.
        focus_win = QApplication.focusWindow()
        for window in self._windows:
            if window.windowHandle() == focus_win:
                return window
        return None

    def toggle_or_spawn(self) -> None:
        """Global-shortcut semantics (parity with src/Shortcut.js).

        * ``shortcut_action == "spawn"`` — always open a new shelf.
        * ``"toggle"`` — one shelf open: open a second; several open: close
          the focused one (falling back to the most recent).

        Improvement over the original: with zero shelves open it spawns one
        instead of indexing ``active_instances[0]`` and crashing.
        """
        if self._config.get("shortcut_action") == "spawn" or len(self._windows) <= 1:
            self.create_window()
            return
        target = self._focused() or self._windows[-1]
        target.close()

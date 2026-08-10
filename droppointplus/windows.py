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

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from .app_config import ConfigManager
from .file_service import FileService
from .models import FileItem
from .shelf_view_model import ShelfViewModel
from .shelf_window import ShelfWindow

logger = logging.getLogger(__name__)


class WindowManager(QObject):
    """Registry of all open shelf windows."""

    window_created = Signal(object)  # instance id (ms epoch — too large for Qt int)

    def __init__(
        self,
        config: ConfigManager,
        parent: QObject | None = None,
        open_settings: Callable[[], None] | None = None,
    ):
        super().__init__(parent)
        self._config = config
        self._service = FileService()  # shared, constructor-injected into ViewModels
        self._open_settings = open_settings  # wired to each window's header gear
        self._windows: list[ShelfWindow] = []
        self._next_id = int(time.time() * 1000)  # parity with `+new Date()` in Window.js

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

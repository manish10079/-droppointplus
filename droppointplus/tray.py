"""System tray icon + context menu.

Qt equivalent of ``src/Tray.js``. Also re-enables the previously commented-
out History submenu, now backed by the fixed ``history`` module.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import history
from .app_config import ConfigManager
from .icons import app_icon
from .settings_dialog import SettingsDialog
from .windows import WindowManager


class TrayIcon(QSystemTrayIcon):
    """Tray icon with New Instance / Settings / Quit (+ History submenu)."""

    def __init__(self, windows: WindowManager, config: ConfigManager, parent=None):
        super().__init__(app_icon(), parent)
        self._windows = windows
        self._config = config
        self.setToolTip("DropPoint+")

        self._menu = QMenu()
        self._menu.aboutToShow.connect(self._rebuild_menu)

        self._menu.addAction("New Instance", lambda: self._windows.create_window())
        self._menu.addAction("Settings", self._open_settings)
        self._menu.addSeparator()
        self._history_menu = self._menu.addMenu("History")
        self._menu.addSeparator()
        self._menu.addAction("Quit", QApplication.instance().quit)
        self.setContextMenu(self._menu)

        self.activated.connect(self._on_activated)

    # -- slots -------------------------------------------------------------
    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            self._windows.create_window()

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self._config)
        dialog.exec()

    def _rebuild_menu(self) -> None:
        """Refresh the History submenu each time the menu is about to open."""
        self._history_menu.clear()
        instances = history.last_instances(5)
        if not instances:
            entry = self._history_menu.addAction("No recent drops")
            entry.setEnabled(False)
            return
        for instance in instances:
            files = instance.get("files") or []
            label = self._format_timestamp(instance.get("instanceId"))
            submenu = self._history_menu.addMenu(label)
            submenu.addAction("Files").setEnabled(False)
            first = Path(files[0]["filePath"]).name if files else "?"
            submenu.addAction(
                f"{first}{' and others' if len(files) > 1 else ''}"
            ).setEnabled(False)

    @staticmethod
    def _format_timestamp(ts) -> str:
        """instanceId is a millisecond epoch — render as dd/mm/yyyy hh:mm."""
        try:
            dt = datetime.fromtimestamp(int(ts) / 1000)
            return dt.strftime("%d/%m/%Y %H:%M")
        except (ValueError, OSError, TypeError) as exc:
            logger.debug("unparseable history timestamp %r (%s)", ts, exc)
            return "Recent"

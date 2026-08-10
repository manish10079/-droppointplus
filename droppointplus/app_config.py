"""Application configuration.

Qt equivalent of the Electron project's ``src/configOptions.js`` plus the
persistence role of ``electron-store``.

The old app instantiated ``new Store(configOptions)`` in five different
places (App, Window, Shortcut, RequestHandlers, Settings), each with its own
copy of the schema. DropPoint+ uses a single ``ConfigManager`` created once
in ``main()`` and passed down, so there is one source of truth and live
change notifications (used to re-register the global hotkey the moment
settings are applied, without restarting the app).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QStandardPaths, Signal

logger = logging.getLogger(__name__)

# --- Schema ---------------------------------------------------------------
# Mirrors src/configOptions.js, extended with the backlog features
# (drag_action + a configurable global shortcut).

CONFIG_SCHEMA: dict[str, dict] = {
    "spawn_on_launch": {
        "type": "boolean",
        "title": "Open a new instance on launch",
    },
    "always_on_top": {
        "type": "boolean",
        "title": "Always on top",
    },
    "open_at_cursor_position": {
        "type": "boolean",
        "title": "Open at cursor position",
    },
    "shortcut_action": {
        "type": "enum",
        "title": "Shortcut behaviour",
        "values": ["toggle", "spawn"],
    },
    "drag_action": {
        "type": "enum",
        "title": "Drag-out behaviour",
        "values": ["copy", "move"],
    },
    "shortcut": {
        "type": "string",
        "title": "Global shortcut (e.g. Shift+Capslock)",
    },
    "debug": {
        "type": "boolean",
        "title": "Enable debug mode",
    },
}

DEFAULT_CONFIG: dict = {
    "spawn_on_launch": True,
    "always_on_top": True,
    "open_at_cursor_position": False,
    "shortcut_action": "toggle",
    "drag_action": "copy",
    # Platform-adjusted default: Caps Lock is not a modifier on macOS
    # (parity with src/Shortcut.js).
    "shortcut": "Shift+Capslock" if sys.platform != "darwin" else "Shift+Tab",
    "debug": False,
}


def app_data_dir() -> Path:
    """Stable per-user data directory.

    Fixes the old History bug of writing to a bare relative path resolved
    against the process CWD. Everything (config.json, instanceHistory.json)
    lives under the OS app-data location.
    """
    raw = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    return Path(raw) if raw else Path.home() / ".droppointplus"


class ConfigManager(QObject):
    """JSON-backed settings store with live change notification.

    ``changed`` is emitted with the key that changed, so listeners (e.g. the
    hotkey manager) can react without polling.
    """

    changed = Signal(str)  # key

    def __init__(self, path: str | os.PathLike | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self._path = Path(path) if path else app_data_dir() / "config.json"
        self._data = dict(DEFAULT_CONFIG)
        self._load()

    # -- metadata ----------------------------------------------------------
    @property
    def path(self) -> Path:
        return self._path

    # -- reads -------------------------------------------------------------
    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def as_dict(self) -> dict:
        return dict(self._data)

    # -- writes ------------------------------------------------------------
    def set(self, key: str, value) -> None:
        if self._data.get(key) == value:
            return
        self._data[key] = value
        self._persist()
        self.changed.emit(key)

    def set_many(self, mapping: dict) -> None:
        changed_keys = [k for k, v in mapping.items() if self._data.get(k) != v]
        if not changed_keys:
            return
        self._data.update(mapping)
        self._persist()
        for key in changed_keys:
            self.changed.emit(key)

    # -- internals ---------------------------------------------------------
    def _load(self) -> None:
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                stored = json.load(fh)
            if isinstance(stored, dict):
                self._data.update(
                    {k: v for k, v in stored.items() if k in DEFAULT_CONFIG}
                )
        except OSError as exc:
            # Missing config file is normal on first run.
            logger.debug("no config at %s (%s); using defaults", self._path, exc)
        except (ValueError, TypeError) as exc:
            logger.warning("config %s is corrupt (%s); using defaults",
                           self._path, exc)

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2)
        except OSError:
            # Settings must never crash the app, but the failure is reported.
            logger.exception("could not write config to %s", self._path)

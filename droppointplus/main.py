"""DropPoint+ application entry point.

Qt equivalent of ``src/App.js``:

* the Electron app kept itself alive with a hidden splash ``BrowserWindow``;
  ``QApplication.setQuitOnLastWindowClosed(False)`` + the tray icon do that
  natively, so the splash hack disappears entirely;
* wires up: config, window manager, tray, global hotkey, spawn-on-launch;
* enforces a single process (one tray, one set of global hooks) and
  registers itself to launch at Windows login.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from . import startup
from .app_config import ConfigManager
from .history_window import HistoryWindow
from .hotkey import HotkeyManager
from .settings_dialog import SettingsDialog
from .single_instance import SingleInstance
from .tray import TrayIcon
from .windows import WindowManager


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("DropPoint+")
    app.setOrganizationName("DropPointPlus")
    app.setQuitOnLastWindowClosed(False)  # tray keeps the app alive

    config = ConfigManager()

    # Logging per the development skills (logging, not print). The `debug`
    # setting controls verbosity; module loggers propagate to the root.
    logging.basicConfig(
        level=logging.DEBUG if config.get("debug") else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    # Single instance: only one DropPoint+ process may run (one tray, one
    # global mouse hook). A second launch asks the running instance to open
    # a shelf and exits without creating a second copy of the app.
    single = SingleInstance()
    if not single.is_primary:
        single.notify_existing()
        return 0

    # Launch at Windows login (HKCU Run key). Applied on startup so the
    # entry always matches the current executable, and re-applied live when
    # the setting is toggled from Settings.
    startup.set_launch_at_startup(bool(config.get("launch_at_startup")))

    def _sync_launch_at_startup(key: str) -> None:
        if key == "launch_at_startup":
            startup.set_launch_at_startup(bool(config.get("launch_at_startup")))

    config.changed.connect(_sync_launch_at_startup)

    windows = WindowManager(
        config,
        open_settings=lambda: SettingsDialog(config).exec(),
        open_history=lambda: HistoryWindow(
            always_on_top=bool(config.get("always_on_top"))
        ).exec(),
    )

    # A second launch of the app asks us to show ourselves: open a shelf.
    single.activate_requested.connect(windows.create_window)

    tray = TrayIcon(windows, config)
    tray.show()

    # Keep a reference: HotkeyManager has no parent, so dropping the local
    # would let CPython garbage-collect it and silently break live rebinding
    # of the shortcut from Settings. `hotkeys` stays alive until main()
    # returns, i.e. for the whole app.exec() lifetime.
    hotkeys = HotkeyManager(config, windows)  # noqa: F841

    if config.get("spawn_on_launch"):
        windows.create_window()

    app.aboutToQuit.connect(tray.hide)
    app.aboutToQuit.connect(single.close)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

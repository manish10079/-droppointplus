"""Global hotkey handling.

Qt equivalent of ``src/Shortcut.js``.

Deliberately dependency-free: the Qt hotkey binding packages that once
existed for Qt6 (``qthotkey``, ``PySide6-QtHotkey``, ``PyQt6-QtHotkey``) are
unmaintained and absent from PyPI, so on **Windows** the global shortcut is
implemented directly on the Win32 ``RegisterHotKey`` API via ``ctypes``, with
``WM_HOTKEY`` received through a ``QAbstractNativeEventFilter`` — the same OS
mechanism Electron uses. On **macOS/Linux** the backend (RegisterEventHotKey /
XGrabKey) is planned for a later phase; the app still works fully via the tray.

Improvements over the Electron version:

* the shortcut is a setting and re-registers live when the config changes —
  no app restart needed;
* registration failure is detected and reported instead of failing silently.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal
from PySide6.QtWidgets import QApplication, QWidget

logger = logging.getLogger(__name__)

# Win32 constants (RegisterHotKey)
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
WM_HOTKEY = 0x0312

# Virtual-key codes for non-alphanumeric keys (alphanumerics use ASCII).
_SPECIAL_KEYS: dict[str, int] = {
    "capslock": 0x14, "tab": 0x09, "space": 0x20, "enter": 0x0D, "return": 0x0D,
    "esc": 0x1B, "escape": 0x1B, "backspace": 0x08, "delete": 0x2E, "del": 0x2E,
    "insert": 0x2D, "home": 0x24, "end": 0x23, "pgup": 0x21, "pageup": 0x21,
    "pgdn": 0x22, "pagedown": 0x22, "up": 0x26, "down": 0x28, "left": 0x25,
    "right": 0x27,
}


def _key_to_vk(name: str) -> int | None:
    """Map a lowercase key name to its Windows virtual-key code."""
    if name in _SPECIAL_KEYS:
        return _SPECIAL_KEYS[name]
    if len(name) == 1 and name.isalnum():
        return ord(name.upper())
    if name.startswith("f") and name[1:].isdigit():
        num = int(name[1:])
        if 1 <= num <= 24:
            return 0x70 + num - 1
    return None


def _parse_shortcut(shortcut: str) -> tuple[int, int] | None:
    """Parse a QHotkey-style string into ``(modifiers, vk)``.

    Accepts e.g. ``"Shift+Capslock"``, ``"Ctrl+Alt+F7"``, ``"Shift+Tab"``.
    Returns ``None`` when unparseable.
    """
    parts = [p.strip() for p in (shortcut or "").split("+") if p.strip()]
    if not parts:
        return None
    modifiers = 0
    key_name = ""
    for part in parts:
        lower = part.lower()
        if lower in ("ctrl", "control"):
            modifiers |= MOD_CONTROL
        elif lower == "alt":
            modifiers |= MOD_ALT
        elif lower == "shift":
            modifiers |= MOD_SHIFT
        elif lower in ("win", "meta", "super", "cmd"):
            modifiers |= MOD_WIN
        else:
            key_name = lower
    if not key_name:
        return None
    vk = _key_to_vk(key_name)
    if vk is None:
        return None
    # RegisterHotKey refuses combinations without at least one modifier.
    if modifiers == 0:
        return None
    return modifiers, vk


class _WinHotkeyFilter(QAbstractNativeEventFilter):
    """Receives ``WM_HOTKEY`` messages posted to the hidden hotkey window."""

    def __init__(self, manager: "HotkeyManager"):
        super().__init__()
        self._manager = manager

    def nativeEventFilter(self, event_type, message) -> tuple[bool, int]:
        # `message` arrives as an int (or a void-pointer wrapper); int()
        # handles both, and the return is (handled, result) — no qintptr in
        # PySide6's public API.
        if event_type in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            import ctypes
            from ctypes import wintypes

            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and int(msg.wParam) == self._manager._hotkey_id:
                self._manager.activated.emit()
                return True, 0
        return False, 0


class HotkeyManager(QObject):
    """Owns the global shortcut and reacts to live config changes."""

    activated = Signal()             # global shortcut pressed
    shortcut_registered = Signal(bool)

    def __init__(self, config, windows, parent=None):
        super().__init__(parent)
        self._config = config
        self._windows = windows
        self._hotkey_id = 0
        self._hwnd = None
        self._target = None
        self._filter = None

        self.activated.connect(self._windows.toggle_or_spawn)

        if sys.platform == "win32":
            self._init_windows_backend()
        else:
            logger.warning(
                "global shortcut backend is Windows-only for now;"
                " macOS/Linux backends planned (the tray still works)."
            )

        self._config.changed.connect(self._on_config_changed)

    # -- backend -----------------------------------------------------------
    def _init_windows_backend(self) -> None:
        import ctypes

        self._target = QWidget()  # hidden native window that owns the hotkey
        self._target.setWindowTitle("DropPoint+ hotkey")
        self._hwnd = int(self._target.winId())
        self._filter = _WinHotkeyFilter(self)
        QApplication.instance().installNativeEventFilter(self._filter)

        self._register_from_config()

    # -- registration ------------------------------------------------------
    def _register_from_config(self) -> None:
        shortcut = self._config.get("shortcut") or ""
        ok = self._register(shortcut)
        self.shortcut_registered.emit(ok)
        if not ok and shortcut:
            logger.warning("failed to register global shortcut %r", shortcut)

    def _register(self, shortcut: str) -> bool:
        self._unregister()
        parsed = _parse_shortcut(shortcut)
        if parsed is None or self._hwnd is None:
            return False
        modifiers, vk = parsed
        import ctypes

        self._hotkey_id += 1
        result = ctypes.windll.user32.RegisterHotKey(
            self._hwnd, self._hotkey_id, modifiers, vk
        )
        if not result:
            self._hotkey_id = 0
            return False
        return True

    def _unregister(self) -> None:
        if self._hotkey_id and self._hwnd:
            import ctypes

            ctypes.windll.user32.UnregisterHotKey(self._hwnd, self._hotkey_id)
            self._hotkey_id = 0

    def _on_config_changed(self, key: str) -> None:
        if key == "shortcut" and sys.platform == "win32":
            self._register_from_config()

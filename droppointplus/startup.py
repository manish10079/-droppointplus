"""Launch-at-login support.

Windows: a value under ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run``
tells Explorer to start DropPoint+ when the user logs in. The entry is
per-user (no admin needed) and points at the current executable, so it
keeps working across updates as long as the install location is stable.

macOS/Linux: no-op for now — the setting still persists so it can be
enabled via the OS's own startup mechanisms, and the toggle in Settings
simply has no effect there.
"""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "DropPointPlus"


def command_line() -> str:
    """The command Windows should run at login.

    Frozen (PyInstaller) builds launch the exe directly; development runs
    start the package through the interpreter.
    """
    exe = f'"{sys.executable}"'
    if getattr(sys, "frozen", False):
        return exe
    return f"{exe} -m droppointplus"


def set_launch_at_startup(enabled: bool) -> bool:
    """Add or remove the Run entry. Returns True on success.

    Idempotent: enabling when already present is a harmless rewrite;
    disabling when absent is a no-op. On non-Windows platforms it logs
    and returns False (the feature is Windows-only for now).
    """
    if sys.platform != "win32":
        logger.info(
            "launch-at-startup is Windows-only for now (platform %s)",
            sys.platform,
        )
        return False

    import winreg

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        )
    except OSError:
        # Run key missing entirely — create it.
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY)
    try:
        if enabled:
            winreg.SetValueEx(
                key, RUN_VALUE, 0, winreg.REG_SZ, command_line()
            )
        else:
            try:
                winreg.DeleteValue(key, RUN_VALUE)
            except FileNotFoundError:
                pass  # nothing to remove — already off
    finally:
        winreg.CloseKey(key)
    return True

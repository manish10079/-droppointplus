"""Launch-at-login (Windows Run key) tests."""

from __future__ import annotations

import sys

import pytest

from droppointplus import startup


def test_command_line_development() -> None:
    # Dev runs (not frozen) start the package through the interpreter.
    assert startup.command_line() == f'"{sys.executable}" -m droppointplus'


def test_launch_at_startup_config_key_exists() -> None:
    from droppointplus.app_config import CONFIG_SCHEMA, DEFAULT_CONFIG

    assert CONFIG_SCHEMA["launch_at_startup"]["type"] == "boolean"
    assert DEFAULT_CONFIG["launch_at_startup"] is True


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Run key only")
def test_set_launch_at_startup_writes_and_removes_run_entry(monkeypatch) -> None:
    """Enabling writes the Run value; disabling deletes it (registry faked)."""
    import winreg

    from droppointplus import startup as startup_mod

    calls: list[str] = []

    class _FakeKey:
        pass

    def _open(*args, **kwargs):
        calls.append("open")
        return _FakeKey()

    def _set(*args, **kwargs):
        calls.append("set")

    def _delete(*args, **kwargs):
        calls.append("delete")

    monkeypatch.setattr(winreg, "OpenKey", _open)
    monkeypatch.setattr(winreg, "CreateKey", _open)
    monkeypatch.setattr(winreg, "SetValueEx", _set)
    monkeypatch.setattr(winreg, "DeleteValue", _delete)
    monkeypatch.setattr(winreg, "CloseKey", lambda *a, **k: None)

    assert startup_mod.set_launch_at_startup(True)
    assert "set" in calls

    calls.clear()
    assert startup_mod.set_launch_at_startup(False)
    assert "delete" in calls


@pytest.mark.skipif(sys.platform == "win32", reason="exercise the non-Windows path")
def test_set_launch_at_startup_is_noop_off_windows() -> None:
    assert startup.set_launch_at_startup(True) is False
    assert startup.set_launch_at_startup(False) is False

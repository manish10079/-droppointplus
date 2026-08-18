"""Single-instance guard tests.

Only one DropPoint+ process may run: the first process owns a named local
socket; a second launch connects to it, asks the primary to activate, and
exits.

These tests run the guard **in-process** with unique socket names so they
never collide with a real running instance. One caveat: on Windows,
destroying a ``QLocalServer`` (its native accept thread) while other Qt
event loops are still running later in the session crashes with an access
violation. To avoid contaminating the rest of the suite, every guard
created here is kept alive for the whole pytest session (module-level
reference) instead of being garbage-collected mid-run.
"""

from __future__ import annotations

import uuid

from droppointplus.single_instance import SingleInstance

# Strong references: guards (and their QLocalServer) must outlive every
# test so their native teardown never lands inside another test's event
# loop (Windows access-violation otherwise).
_KEEP_ALIVE: list[SingleInstance] = []


def _unique_name() -> str:
    return f"droppointplus-test-{uuid.uuid4().hex}"


def _keep(*guards: SingleInstance) -> None:
    _KEEP_ALIVE.extend(guards)


def test_first_instance_is_primary(qtbot) -> None:
    guard = SingleInstance(_unique_name())
    assert guard.is_primary
    _keep(guard)


def test_second_instance_is_secondary(qtbot) -> None:
    name = _unique_name()
    primary = SingleInstance(name)
    secondary = SingleInstance(name)
    assert primary.is_primary
    assert not secondary.is_primary
    _keep(primary)


def test_secondary_launch_asks_primary_to_activate(qtbot) -> None:
    """A second launch notifies the running instance instead of running."""
    name = _unique_name()
    primary = SingleInstance(name)
    assert primary.is_primary

    activated: list[int] = []
    primary.activate_requested.connect(lambda: activated.append(1))

    secondary = SingleInstance(name)
    assert not secondary.is_primary
    secondary.notify_existing()  # blocks until the primary acks

    assert activated == [1]
    _keep(primary)


def test_release_then_relock(qtbot) -> None:
    """After the primary closes, a new process can take the lock."""
    name = _unique_name()
    primary = SingleInstance(name)
    assert primary.is_primary
    primary.close()

    replacement = SingleInstance(name)
    assert replacement.is_primary
    _keep(replacement)

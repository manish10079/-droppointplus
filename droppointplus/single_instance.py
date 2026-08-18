"""Single-instance enforcement.

Only one DropPoint+ process may run — one tray icon, one global mouse
hook, one set of edge strips. The first process to start listens on a
named local socket (``QLocalServer``, a named pipe on Windows); any later
launch connects to that socket, asks the running instance to show itself
(open a shelf), and exits without creating a second copy.

The lock is per-user and derived from the app name, so different users on
the same machine get independent instances.
"""

from __future__ import annotations

import getpass
import logging

from PySide6.QtCore import QEventLoop, QObject, QTimer, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

logger = logging.getLogger(__name__)

_DEFAULT_SERVER_NAME = "DropPointPlus-single-instance"

_ACK_TIMEOUT_MS = 1500


def server_name() -> str:
    """The lock name, namespaced per user to avoid cross-user collisions."""
    return f"{_DEFAULT_SERVER_NAME}-{getpass.getuser()}"


class SingleInstance(QObject):
    """Guards the app against a second process.

    ``is_primary`` is True for the process that owns the lock. Secondary
    processes call :meth:`notify_existing` to ask the primary to activate
    (open a shelf window) and then exit immediately.
    """

    activate_requested = Signal()  # a second launch asked us to show ourselves

    def __init__(self, name: str | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self._name = name or server_name()
        self._server: QLocalServer | None = None
        # Strong reference to the notify socket: without it the wrapper can
        # be garbage-collected while Qt still has pending events for the
        # socket, crashing (access violation) when those events are
        # processed later.
        self._notify_socket: QLocalSocket | None = None
        self.is_primary = self._try_acquire()

    # -- lifecycle ---------------------------------------------------------
    def _try_acquire(self) -> bool:
        """Probe for a live server; if none, claim the name and listen."""
        probe = QLocalSocket()
        probe.connectToServer(self._name)
        if probe.waitForConnected(300):
            # Another instance holds the lock.
            probe.disconnectFromServer()
            probe.close()
            return False
        probe.close()

        # No live server — claim the name. A stale socket may survive a
        # crash; removeServer clears it so we can listen again.
        QLocalServer.removeServer(self._name)
        server = QLocalServer(self)
        if not server.listen(self._name):
            logger.warning(
                "could not listen on %r — running without the single-instance guard",
                self._name,
            )
            return False  # degrade: still run, just unguarded
        server.newConnection.connect(self._on_new_connection)
        self._server = server
        return True

    def close(self) -> None:
        """Release the lock (called on quit so a fresh launch can relock)."""
        if self._server is not None:
            self._server.close()
            self._server.deleteLater()
            self._server = None

    # -- secondary process -------------------------------------------------
    def notify_existing(self) -> None:
        """Ask the primary instance to activate and wait for its ack.

        The connection is kept open (and a short local event loop runs)
        until the primary confirms it read the request: closing early can
        drop the message while the primary is still accepting the
        connection, and the ack makes the handshake deterministic.
        """
        socket = QLocalSocket()
        self._notify_socket = socket
        socket.connectToServer(self._name)
        if not socket.waitForConnected(500):
            self._notify_socket = None
            socket.deleteLater()
            return

        acked = False

        def _on_ready_read() -> None:
            nonlocal acked
            acked = True

        socket.readyRead.connect(_on_ready_read)

        socket.write(b"show")
        socket.flush()

        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(_ACK_TIMEOUT_MS)
        socket.readyRead.connect(loop.quit)
        socket.disconnected.connect(loop.quit)
        loop.exec()
        timer.stop()
        if not acked:
            socket.abort()
        socket.disconnectFromServer()
        socket.deleteLater()
        self._notify_socket = None

    # -- primary process ---------------------------------------------------
    def _on_new_connection(self) -> None:
        if self._server is None:
            return
        while self._server.hasPendingConnections():
            conn = self._server.nextPendingConnection()
            conn.readyRead.connect(lambda c=conn: self._read_show(c))

    def _read_show(self, conn) -> None:
        data = bytes(conn.readAll())
        if b"show" in data:
            conn.write(b"ok")
            conn.flush()
            self.activate_requested.emit()
        # Close our end, then schedule deletion exactly once. Deleting from
        # inside the socket's own disconnected signal (a handler on
        # `disconnected`) crashes Qt on Windows, so cleanup happens only
        # here, after disconnectFromServer() has fully torn the socket
        # down. Connections that never deliver data (e.g. the probe socket
        # a secondary uses to detect the lock) are reclaimed by Python's
        # cyclic GC.
        conn.disconnectFromServer()
        conn.deleteLater()

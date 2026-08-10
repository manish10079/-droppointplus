"""Shelf view model — the WHAT behind a shelf instance.

Application layer (per ``DropPoint_Plus_Development_Skills.md``): owns the
collected-file state, applies dedup, and orchestrates the ``FileService``.
The widget only renders state and forwards input; it contains no business
logic.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt, Signal

from .app_config import ConfigManager
from .file_service import DeleteWorker, FileService
from .models import FileItem

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


class ShelfViewModel(QObject):
    """State + commands for one shelf window."""

    files_changed = Signal(object, object)   # instance_id, list[FileItem]
    close_requested = Signal()
    operation_started = Signal()             # move-mode deletion began
    operation_progress = Signal(int, int)    # done, total

    def __init__(
        self,
        instance_id: int,
        config: ConfigManager,
        service: FileService,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._instance_id = instance_id
        self._config = config
        self._service = service
        self._files: list[FileItem] = []
        self._worker: DeleteWorker | None = None
        self._failures = 0

    # -- queries ------------------------------------------------------------
    @property
    def instance_id(self) -> int:
        return self._instance_id

    @property
    def files(self) -> list[FileItem]:
        return list(self._files)

    @property
    def count(self) -> int:
        return len(self._files)

    @property
    def is_working(self) -> bool:
        """True while a background operation (move-mode deletion) runs."""
        return self._worker is not None

    # -- commands -----------------------------------------------------------
    def can_accept_drop(self, event) -> bool:
        """Whether the incoming drag can be accepted (for the View's border)."""
        return self._service.accepts(event)

    def handle_drop(self, event) -> int:
        """Collect dropped files into the shelf; returns the number added.

        Deduplicates against the current contents and persists the snapshot
        to the instance history when something new arrived. All drag
        mechanics (mime parsing) live in the FileService.
        """
        if self.is_working:
            return 0
        incoming = self._service.items_from_drop(event)
        fresh = [item for item in incoming if item not in self._files]
        if not fresh:
            return 0
        self._files.extend(fresh)
        self._service.record_drop(self._instance_id, self._files)
        self.files_changed.emit(self._instance_id, list(self._files))
        return len(fresh)

    def drag_out(self, source: "QWidget") -> None:
        """User dragged the collected files out of the shelf.

        Blocks during the native OS drag; then requests the window to close.
        In move mode the sources are deleted on a worker thread first (the
        window stays open, showing progress, until that finishes). A
        cancelled drag keeps the files and the shelf open.
        """
        if not self._files or self.is_working:
            return
        snapshot = list(self._files)  # defensive copy — don't alias internals
        action = self._service.start_drag(source, snapshot)
        if action == Qt.IgnoreAction:
            return
        if self._config.get("drag_action") == "move":
            self._begin_move(snapshot)
        else:
            self.close_requested.emit()

    def _begin_move(self, items: list[FileItem]) -> None:
        """Delete the moved sources on a worker thread, then close.

        The worker is created by the ``FileService`` (operation manager) and
        its signals are routed to the View through ``operation_started`` /
        ``operation_progress``. The window only closes once the thread has
        finished, so the UI never blocks on the file system.
        """
        self._failures = 0
        # Connect *before* start so no progress/finished signal can be lost
        # to the start/finish race when the deletion completes instantly.
        self._worker = self._service.create_delete_worker(items, parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._on_delete_finished)
        self._worker.start()
        self.operation_started.emit()

    def _on_progress(self, done: int, total: int) -> None:
        self.operation_progress.emit(done, total)

    def _on_failed(self, item: FileItem) -> None:
        # The worker already logged the failure with a traceback; we only
        # count them so the finish handler can report a summary.
        self._failures += 1

    def _on_delete_finished(self) -> None:
        worker = self._worker
        self._worker = None
        if self._failures:
            logger.warning(
                "%d of %d source(s) could not be removed (see above)",
                self._failures,
                len(self._files),
            )
        self._files.clear()
        self.files_changed.emit(self._instance_id, [])
        self.close_requested.emit()
        worker.deleteLater()

    def remove_item(self, item: FileItem) -> None:
        """Remove one collected item (the View's per-row ✕)."""
        if self.is_working or item not in self._files:
            return
        self._files.remove(item)
        # Keep the persisted snapshot in step with the shelf contents.
        self._service.record_drop(self._instance_id, self._files)
        self.files_changed.emit(self._instance_id, list(self._files))

    def clear(self) -> None:
        """Discard the collected files (Esc in the View)."""
        if not self._files or self.is_working:
            return
        self._files.clear()
        self.files_changed.emit(self._instance_id, [])

"""File service — the HOW behind shelf drag operations.

Infrastructure layer (per ``DropPoint_Plus_Development_Skills.md``): the
Qt/OS mechanics of drag-in (mime parsing), drag-out (``QDrag``), background
source deletion for move mode (``DeleteWorker`` thread), and history
persistence. Holds no UI state and no widget logic, so it can be replaced or
tested in isolation.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QMimeData, QThread, Qt, QUrl, Signal
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QWidget

from .history import add_to_instance
from .icons import file_type_icon, guess_file_type, multi_file_icon
from .models import FileItem

logger = logging.getLogger(__name__)


class DeleteWorker(QThread):
    """Deletes source files (move mode) off the UI thread.

    Background-operations pattern from the skills doc — the ``FileService``
    (operation manager) spawns this worker, which talks to the file system
    and reports back through Qt signals. ``progress`` fires after every item
    (the total is known up front, so the operation is determinate);
    ``failed`` fires per item that could not be removed — never fatal.
    """

    progress = Signal(int, int)  # done, total
    failed = Signal(object)      # the FileItem that could not be removed

    def __init__(self, items: Sequence[FileItem], parent=None):
        super().__init__(parent)
        self._items = list(items)

    def run(self) -> None:
        total = len(self._items)
        for done, item in enumerate(self._items, start=1):
            try:
                if item.path.is_dir():
                    shutil.rmtree(item.path)
                else:
                    item.path.unlink()
            except OSError:
                logger.warning(
                    "could not remove %s in move mode", item.path, exc_info=True
                )
                self.failed.emit(item)
            self.progress.emit(done, total)


class FileService:
    """Performs the actual file operations for a shelf instance."""

    def accepts(self, event) -> bool:
        """True when the drop event carries file URLs (drag-in acceptance)."""
        return bool(event.mimeData().hasUrls())

    def urls_to_items(self, urls: Sequence[QUrl]) -> list[FileItem]:
        """Convert drop URLs to FileItems, skipping non-file URLs."""
        items: list[FileItem] = []
        for url in urls:
            path = url.toLocalFile()
            if not path:
                continue
            items.append(FileItem(path=Path(path), file_type=guess_file_type(path)))
        return items

    def items_from_drop(self, event) -> list[FileItem]:
        """Extract the dropped files from a drag event (drag-in mechanics)."""
        return self.urls_to_items(event.mimeData().urls())

    def start_drag(self, source: QWidget, items: Sequence[FileItem]) -> Qt.DropAction:
        """Begin a native OS drag of the given files.

        Blocks until the drop completes or is cancelled, then returns the
        resulting drop action (``Qt.IgnoreAction`` when cancelled).
        """
        if not items:
            return Qt.IgnoreAction
        drag = QDrag(source)
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(item.path)) for item in items])
        drag.setMimeData(mime)
        if len(items) > 1:
            drag.setPixmap(multi_file_icon(64).pixmap(64, 64))
        else:
            drag.setPixmap(file_type_icon(items[0].file_type, 64).pixmap(64, 64))
        return drag.exec(Qt.CopyAction | Qt.MoveAction)

    def create_delete_worker(
        self, items: Sequence[FileItem], parent=None
    ) -> DeleteWorker:
        """Create a (not yet started) worker that deletes the source files.

        Operation manager: the caller (typically the ViewModel) connects the
        worker's ``progress``/``failed``/``finished`` signals and then calls
        ``worker.start()``. Connecting *before* starting is what guarantees
        no signal is lost to the start/finish race on fast deletions.
        """
        return DeleteWorker(list(items), parent=parent)

    def record_drop(self, instance_id: int, items: Sequence[FileItem]) -> None:
        """Persist the collected files to the instance history."""
        add_to_instance(instance_id, list(items))

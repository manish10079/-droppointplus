"""File service — the HOW behind shelf drag operations.

Infrastructure layer (per ``DropPoint_Plus_Development_Skills.md``): the
Qt/OS mechanics of drag-in (mime parsing), drag-out (``QDrag``), background
source deletion for move mode (``DeleteWorker`` thread), and history
persistence. Holds no UI state and no widget logic, so it can be replaced or
tested in isolation.
"""

from __future__ import annotations

import logging
import os
import shutil
import time
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


class TransferWorker(QThread):
    """Copies or moves collected items to a destination off the UI thread.

    Reports byte-level progress (``progress(done_bytes, total_bytes, speed)``)
    and one ``item_done`` per finished item so the ViewModel can trim the
    collection live. ``cancel()`` is cooperative — checked between chunks and
    items — so the operation stops promptly without corrupting state.
    Duplicate names at the destination are auto-renamed (``file (1).ext``),
    never overwritten.
    """

    progress = Signal(int, int, float)   # bytes done, bytes total, speed B/s
    item_done = Signal(object)           # the FileItem just completed
    failed = Signal(object)              # the FileItem that could not transfer

    _CHUNK = 1024 * 1024

    def __init__(
        self,
        items: Sequence[FileItem],
        destination: str | os.PathLike,
        action: str,  # "copy" | "move"
        parent=None,
    ):
        super().__init__(parent)
        self._items = list(items)
        self._destination = Path(destination)
        self._action = action
        self._cancelled = False
        self._done_bytes = 0
        self._last_bytes = 0
        self._last_t = time.monotonic()
        self._speed = 0.0

    # -- api -----------------------------------------------------------------
    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        self._cancelled = True

    # -- worker --------------------------------------------------------------
    def run(self) -> None:
        total = self._total_bytes()
        start = time.monotonic()
        for item in self._items:
            if self._cancelled:
                break
            try:
                self._transfer_one(item)
            except OSError:
                logger.warning("transfer failed for %s", item.path, exc_info=True)
                self.failed.emit(item)
                continue
            self.item_done.emit(item)
        if not self._speed and self._done_bytes:
            elapsed = max(time.monotonic() - start, 1e-6)
            self._speed = self._done_bytes / elapsed
        self.progress.emit(self._done_bytes, total, self._speed)
        # Note: do NOT emit ``finished`` here — ``finished`` is QThread's own
        # signal, which Qt emits exactly once after run() returns. Emitting
        # it manually would double-fire the completion handler.

    def _total_bytes(self) -> int:
        total = 0
        for item in self._items:
            try:
                total += self._size_of(item.path)
            except OSError:
                logger.warning("could not size %s", item.path, exc_info=True)
        return total

    @staticmethod
    def _size_of(path: Path) -> int:
        if path.is_dir():
            return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
        return path.stat().st_size

    def _transfer_one(self, item: FileItem) -> None:
        dest = self._unique_dest(item.path.name)
        if self._action == "copy":
            if item.path.is_dir():
                self._copy_tree(item.path, dest)
            else:
                self._copy_file(item.path, dest)
        else:
            shutil.move(str(item.path), str(dest))

    def _unique_dest(self, name: str) -> Path:
        candidate = self._destination / name
        if not candidate.exists():
            return candidate
        stem, ext = Path(name).stem, Path(name).suffix
        for i in range(1, 1000):
            candidate = self._destination / f"{stem} ({i}){ext}"
            if not candidate.exists():
                return candidate
        return candidate

    def _copy_file(self, src: Path, dst: Path) -> None:
        with open(src, "rb") as r, open(dst, "wb") as w:
            while True:
                chunk = r.read(self._CHUNK)
                if not chunk:
                    break
                w.write(chunk)
                self._bump(len(chunk))

    def _copy_tree(self, src: Path, dst: Path) -> None:
        for root, dirs, files in os.walk(src):
            if self._cancelled:
                return
            rel = os.path.relpath(root, src)
            target = dst if rel == "." else dst / rel
            target.mkdir(parents=True, exist_ok=True)
            for name in files:
                if self._cancelled:
                    return
                self._copy_file(Path(root) / name, target / name)

    def _bump(self, n: int) -> None:
        self._done_bytes += n
        now = time.monotonic()
        if now - self._last_t >= 0.5:
            inst = (self._done_bytes - self._last_bytes) / (now - self._last_t)
            self._speed = inst if not self._speed else self._speed * 0.6 + inst * 0.4
            self._last_t = now
            self._last_bytes = self._done_bytes


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

    def create_transfer_worker(
        self,
        items: Sequence[FileItem],
        destination: str | os.PathLike,
        action: str,
        parent=None,
    ) -> TransferWorker:
        """Create a (not yet started) copy/move worker.

        Same contract as ``create_delete_worker``: connect signals first,
        then ``start()``. Progress is byte-based; the ViewModel routes it to
        the shelf's progress overlay.
        """
        return TransferWorker(list(items), destination, action, parent=parent)

    def record_drop(self, instance_id: int, items: Sequence[FileItem]) -> None:
        """Persist the collected files to the instance history."""
        add_to_instance(instance_id, list(items))

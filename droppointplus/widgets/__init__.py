"""Reusable widgets (per ``DropPoint_Plus_Development_Skills.md``: a
``widgets/`` package of presentation-only components).

These widgets render data and emit raw signals — they never contain business
logic. What happens with the data (dedup, history, move mode…) belongs to the
ViewModel/Service layers.

The skills doc names these ``DropZone.py`` / ``FileCard.py`` /
``ProgressWidget.py``; the package uses standard Python snake_case filenames
(``drop_zone.py`` etc.) with the same class names.
"""

from .drop_zone import DropZone
from .file_card import FileCard
from .file_list import FileList
from .progress_widget import ProgressWidget

__all__ = ["DropZone", "FileCard", "FileList", "ProgressWidget"]

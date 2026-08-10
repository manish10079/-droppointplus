"""Domain models for DropPoint+.

Per the project's development skills (``DropPoint_Plus_Development_Skills.md``):
dataclasses for models, ``pathlib``, type hints everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# JSON keys are kept identical to the original DropPoint history format so any
# pre-existing instanceHistory.json stays readable.
_FILE_PATH_KEY = "filePath"
_FILE_TYPE_KEY = "fileType"

# Coarse type buckets produced by icons.guess_file_type().
FILE_TYPES = ("audio", "video", "image", "text", "folder", "file")


@dataclass(frozen=True)
class FileItem:
    """A single file (or folder) collected by a shelf instance."""

    path: Path
    file_type: str  # one of FILE_TYPES

    def __post_init__(self) -> None:
        if self.file_type not in FILE_TYPES:
            raise ValueError(
                f"invalid file_type {self.file_type!r}; expected one of"
                f" {FILE_TYPES}"
            )

    @classmethod
    def from_dict(cls, data: dict) -> "FileItem":
        return cls(
            path=Path(data[_FILE_PATH_KEY]),
            file_type=data[_FILE_TYPE_KEY],
        )

    def to_dict(self) -> dict:
        return {_FILE_PATH_KEY: str(self.path), _FILE_TYPE_KEY: self.file_type}

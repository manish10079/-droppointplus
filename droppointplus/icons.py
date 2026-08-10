"""File-type and application icons.

Qt equivalent of ``src/Icons.js``. The PNG assets are reused from the
original GPL-3.0 DropPoint project (see README for licensing notes); only the
code around them is new.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon

ICON_DIR = Path(__file__).resolve().parent / "resources" / "icons"
PNG_LOGO_DIR = ICON_DIR / "pngLogo"

# filetype bucket -> asset filename (parity with src/Icons.js mapping)
TYPE_TO_FILENAME: dict[str, str] = {
    "audio": "audio.png",
    "video": "video.png",
    "image": "image.png",
    "text": "text.png",
    "folder": "folder.png",
    "file": "file.png",
}

_AUDIO_EXTS = {
    ".mp3", ".wav", ".flac", ".m4a", ".ogg", ".oga", ".opus", ".aac",
    ".wma", ".aiff", ".mid", ".midi",
}
_VIDEO_EXTS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v",
    ".mpg", ".mpeg", ".3gp", ".ts",
}
_IMAGE_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp", ".ico",
    ".tif", ".tiff", ".heic", ".raw",
}
_TEXT_EXTS = {
    ".txt", ".md", ".log", ".json", ".xml", ".html", ".htm", ".css",
    ".js", ".ts", ".py", ".csv", ".ini", ".yml", ".yaml", ".toml",
    ".sh", ".bat", ".cfg", ".conf",
}


def guess_file_type(path: str) -> str:
    """Coarse filetype bucket from a path.

    The Electron renderer derived the type from the browser MIME type
    (``f.type.split("/")[0]``); we infer the same buckets from the file
    extension and directory-ness.
    """
    p = Path(path)
    if p.is_dir():
        return "folder"
    ext = p.suffix.lower()
    if ext in _AUDIO_EXTS:
        return "audio"
    if ext in _VIDEO_EXTS:
        return "video"
    if ext in _IMAGE_EXTS:
        return "image"
    if ext in _TEXT_EXTS:
        return "text"
    return "file"


def _icon(filename: str, size: int) -> QIcon:
    icon = QIcon(str(ICON_DIR / filename))
    pixmap = icon.pixmap(size, size)
    return QIcon(pixmap)


def file_type_icon(file_type: str, size: int = 64) -> QIcon:
    """Icon for a single file of the given type."""
    name = TYPE_TO_FILENAME.get(file_type, TYPE_TO_FILENAME["file"])
    return _icon(name, size)


def multi_file_icon(size: int = 64) -> QIcon:
    """Icon shown when several files are being dragged out."""
    return _icon("multifile.png", size)


def app_icon() -> QIcon:
    """Application / tray icon.

    Windows: multi-resolution .ico handed straight to the OS (DPI-aware,
    parity with src/Tray.js). macOS: menu-bar template PNG. Linux: plain PNG.
    """
    if sys.platform == "win32":
        return QIcon(str(ICON_DIR / "droppoint.ico"))
    if sys.platform == "darwin":
        # macOS menu-bar template: must be marked as a mask or it renders
        # as a solid block in the menu bar.
        icon = QIcon(str(PNG_LOGO_DIR / "droppointMacTemplate.png"))
        icon.setIsMask(True)
        return icon
    return QIcon(str(PNG_LOGO_DIR / "droppoint.png"))

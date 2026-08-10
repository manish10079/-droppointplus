"""Destination picker — choose where collected files go (design.md #4).

A pure View: lists FAVORITES (standard folders + user-pinned ones from the
config) and RECENT destinations, filters them as you type, and offers a
Browse… button. Emits ``selected(path)``; it never touches files itself.
Favouriting/unfavouriting is persisted through the injected ConfigManager.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, QStandardPaths, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from . import colors
from .app_config import ConfigManager

logger = logging.getLogger(__name__)

_STANDARD_FAVORITES = (
    ("Desktop", QStandardPaths.DesktopLocation),
    ("Downloads", QStandardPaths.DownloadLocation),
    ("Documents", QStandardPaths.DocumentsLocation),
    ("Pictures", QStandardPaths.PicturesLocation),
)

_ROW_STYLE = (
    f"QPushButton {{ background-color: {colors.rgba(colors.SURFACE_CONTAINER)};"
    f" color: {colors.rgba(colors.TEXT_PRIMARY)};"
    f" border: 1px solid {colors.rgba(colors.BORDER_SUBTLE)};"
    " border-radius: 6px; padding: 6px 10px; text-align: left; font-size: 12px; }"
    f"QPushButton:hover {{ border-color: {colors.rgba(colors.PRIMARY_ACTIVE)}; }}"
)
_PIN_STYLE = (
    f"QPushButton {{ background: transparent; color: {colors.rgba(colors.TEXT_SECONDARY)};"
    " border: none; font-size: 14px; }"
    f"QPushButton:hover {{ color: {colors.rgba(colors.PRIMARY)}; }}"
)
_HEADER_STYLE = (
    f"color: {colors.rgba(colors.TEXT_SECONDARY)};"
    " font-size: 10px; font-weight: 600; letter-spacing: 2px;"
)
_SEARCH_STYLE = (
    f"QLineEdit {{ background-color: {colors.rgba(colors.SURFACE_CONTAINER)};"
    f" color: {colors.rgba(colors.TEXT_PRIMARY)};"
    f" border: 1px solid {colors.rgba(colors.BORDER_SUBTLE)};"
    " border-radius: 6px; padding: 6px 10px; font-size: 12px; }"
)


class DestinationDialog(QDialog):
    """Modal picker; emits ``selected(path)`` when a destination is chosen."""

    selected = Signal(str)  # destination path

    def __init__(
        self,
        config: ConfigManager,
        action: str = "copy",  # "copy" | "move" — only used for the title
        parent=None,
    ):
        super().__init__(parent)
        self._config = config
        self.setWindowTitle(
            f"{'Copy' if action == 'copy' else 'Move'} to…"
        )
        self.setFixedSize(420, 480)
        self.setStyleSheet(f"QDialog {{ background-color: {colors.rgba(colors.SURFACE)}; }}")
        self.setModal(True)

        self._build()

    # -- ui -------------------------------------------------------------------
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(8)

        title = QLabel(self.windowTitle(), self)
        title.setStyleSheet(
            f"color: {colors.rgba(colors.TEXT_PRIMARY)};"
            " font-size: 16px; font-weight: 700;"
        )
        outer.addWidget(title)

        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Search destinations… or type a folder path")
        self._search.setStyleSheet(_SEARCH_STYLE)
        self._search.textChanged.connect(self._apply_filter)
        outer.addWidget(self._search)

        # A typed text that is an existing folder becomes a direct target.
        self._use_path_btn = QPushButton(self)
        self._use_path_btn.setStyleSheet(_ROW_STYLE)
        self._use_path_btn.hide()
        self._use_path_btn.clicked.connect(self._on_use_typed_path)
        outer.addWidget(self._use_path_btn)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._list = QVBoxLayout(self._container)
        self._list.setContentsMargins(0, 0, 4, 0)
        self._list.setSpacing(4)
        self._list.addStretch(1)
        scroll.setWidget(self._container)
        outer.addWidget(scroll, 1)

        browse = QPushButton("Choose Folder…", self)
        browse.setStyleSheet(
            f"QPushButton {{ background-color: {colors.rgba(colors.PRIMARY_ACTIVE)};"
            f" color: {colors.rgba(colors.SURFACE)}; font-size: 12px; font-weight: 700;"
            " border: none; border-radius: 6px; padding: 8px; }"
            f"QPushButton:hover {{ background-color: {colors.rgba(colors.PRIMARY)}; }}"
        )
        browse.clicked.connect(self._on_browse)
        outer.addWidget(browse)

        self._rebuild()

    def _rebuild(self) -> None:
        """Re-render the favourites/recent sections from the config."""
        self._favorites = self._standard_favorites() + [
            str(p) for p in self._config.get("favorites", [])
            if Path(p).is_dir()
        ]
        self._recents = [
            str(p) for p in self._config.get("recent_destinations", [])
            if Path(p).is_dir() and str(p) not in self._favorites
        ]

    @staticmethod
    def _standard_favorites() -> list[str]:
        found = []
        for name, location in _STANDARD_FAVORITES:
            path = QStandardPaths.writableLocation(location)
            if path and Path(path).is_dir():
                found.append(str(Path(path)))
        return found

    # -- rows -----------------------------------------------------------------
    def _add_section(self, label: str) -> None:
        header = QLabel(label, self._container)
        header.setStyleSheet(_HEADER_STYLE)
        self._list.addWidget(header)

    def _add_row(self, path: str, pinned: bool, filter_text: str) -> bool:
        name = Path(path).name or str(Path(path))
        if filter_text and filter_text.lower() not in name.lower():
            return False
        row = QHBoxLayout()
        row.setSpacing(4)
        btn = QPushButton(name, self._container)
        btn.setToolTip(path)
        btn.setStyleSheet(_ROW_STYLE)
        btn.clicked.connect(lambda _=False, p=path: self._pick(p))
        row.addWidget(btn, 1)
        pin = QPushButton("★" if pinned else "☆", self._container)
        pin.setToolTip("Unpin" if pinned else "Pin to favourites")
        pin.setStyleSheet(_PIN_STYLE)
        pin.setFixedWidth(28)
        pin.clicked.connect(
            lambda _=False, p=path, is_pinned=pinned: (
                self._unpin(p) if is_pinned else self._pin(p)
            )
        )
        row.addWidget(pin)
        self._list.addLayout(row)
        return True

    def _apply_filter(self, text: str) -> None:
        self._rebuild()
        # Drop every row from the previous render.
        while self._list.count() > 1:  # keep the trailing stretch
            item = self._list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

        if not self._favorites and not self._recents:
            empty = QLabel("No destinations yet — choose a folder below.", self._container)
            empty.setStyleSheet(
                f"color: {colors.rgba(colors.TEXT_SECONDARY)}; font-size: 12px;"
            )
            self._list.insertWidget(0, empty)
        else:
            index = 0
            if self._favorites:
                self._list.insertWidget(index, self._section_label("FAVORITES"))
                index += 1
                for path in self._favorites:
                    if self._row_at(index, path, pinned=True, filter_text=text):
                        index += 1
            if self._recents:
                self._list.insertWidget(index, self._section_label("RECENT"))
                index += 1
                for path in self._recents:
                    if self._row_at(index, path, pinned=False, filter_text=text):
                        index += 1

        # Typed text that is an existing folder becomes a direct target.
        typed = text.strip()
        if typed and Path(typed).is_dir():
            self._use_path_btn.setText(f"Use this folder:  {typed}")
            self._use_path_btn.show()
        else:
            self._use_path_btn.hide()

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text, self._container)
        label.setStyleSheet(_HEADER_STYLE)
        return label

    def _row_at(self, index: int, path: str, pinned: bool, filter_text: str) -> bool:
        name = Path(path).name or str(Path(path))
        if filter_text and filter_text.lower() not in name.lower():
            return False
        row = QHBoxLayout()
        row.setSpacing(4)
        btn = QPushButton(name, self._container)
        btn.setToolTip(path)
        btn.setStyleSheet(_ROW_STYLE)
        btn.clicked.connect(lambda _=False, p=path: self._pick(p))
        row.addWidget(btn, 1)
        pin = QPushButton("★" if pinned else "☆", self._container)
        pin.setToolTip("Unpin from favourites" if pinned else "Pin to favourites")
        pin.setStyleSheet(_PIN_STYLE)
        pin.setFixedWidth(28)
        pin.clicked.connect(
            lambda _=False, p=path, is_pinned=pinned: (
                self._unpin(p) if is_pinned else self._pin(p)
            )
        )
        row.addWidget(pin)
        self._list.insertLayout(index, row)
        return True

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    # -- actions ---------------------------------------------------------------
    def _pick(self, path: str) -> None:
        self.selected.emit(path)
        self.accept()

    def _on_use_typed_path(self) -> None:
        self._pick(self._search.text().strip())

    def _on_browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "Choose destination", str(Path.home())
        )
        if chosen:
            self._pick(chosen)

    def _pin(self, path: str) -> None:
        favorites = list(self._config.get("favorites", []))
        if path not in favorites:
            self._config.set("favorites", [path, *favorites])
        self._apply_filter(self._search.text())

    def _unpin(self, path: str) -> None:
        favorites = [p for p in self._config.get("favorites", []) if p != path]
        self._config.set("favorites", favorites)
        self._apply_filter(self._search.text())

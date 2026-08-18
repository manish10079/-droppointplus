"""Settings dialog.

Qt equivalent of ``src/Settings.js`` + ``renderer/settings-renderer.js`` +
``static/settings.html``. Controls are generated from ``CONFIG_SCHEMA``, so
adding a setting only touches ``app_config.py`` — the same schema-driven
behaviour the original implemented in JS with Tailwind/Preline.

The window uses the same frameless dark panel chrome as the shelf
(``PanelMixin``) so it looks like one surface with the rest of the app.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .app_config import CONFIG_SCHEMA, ConfigManager
from .colors import (
    BORDER_SUBTLE,
    ON_SURFACE_VARIANT,
    PRIMARY_ACTIVE,
    SUCCESS,
    SURFACE,
    SURFACE_CONTAINER,
    SURFACE_CONTAINER_HIGH,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    rgba,
)
from .widgets.panel_mixin import FOOTER_H, HEADER_H, PanelMixin

WINDOW_W = 600
WINDOW_H = 450
_BODY_X = 28
_BODY_W = WINDOW_W - 2 * _BODY_X
# Resize bounds: the schema-driven form needs the designed size as its
# lower limit (rows clip below it); it may grow on larger screens.
MIN_W, MIN_H = 600, 450
MAX_W, MAX_H = 900, 700

_TOAST_STYLE = f"color: {rgba(SUCCESS)}; font-weight: 600; font-size: 12px;"

# Dark control styling — same Material palette as the shelf.
_CONTROL_QSS = (
    f"QLineEdit, QComboBox {{"
    f" background-color: {rgba(SURFACE_CONTAINER)};"
    f" border: 1px solid {rgba(BORDER_SUBTLE)}; border-radius: 6px;"
    f" color: {rgba(TEXT_PRIMARY)}; font-size: 13px;"
    " padding: 6px 10px;"
    "}"
    f"QLineEdit:focus, QComboBox:focus {{"
    f" border: 1px solid {rgba(PRIMARY_ACTIVE)};"
    "}"
    f"QComboBox::drop-down {{ border: none; width: 24px; }}"
    f"QComboBox QAbstractItemView {{"
    f" background-color: {rgba(SURFACE_CONTAINER)};"
    f" color: {rgba(TEXT_PRIMARY)};"
    f" border: 1px solid {rgba(BORDER_SUBTLE)};"
    f" selection-background-color: {rgba(PRIMARY_ACTIVE)};"
    f" selection-color: {rgba(SURFACE)};"
    "}"
    f"QCheckBox {{ color: {rgba(ON_SURFACE_VARIANT)};"
    " font-size: 13px; spacing: 8px; }"
    f"QCheckBox::indicator {{ width: 16px; height: 16px;"
    f" border: 1px solid {rgba(BORDER_SUBTLE)}; border-radius: 4px;"
    f" background-color: {rgba(SURFACE_CONTAINER)}; }}"
    f"QCheckBox::indicator:checked {{"
    f" background-color: {rgba(PRIMARY_ACTIVE)};"
    f" border-color: {rgba(PRIMARY_ACTIVE)}; }}"
)


class SettingsDialog(PanelMixin, QDialog):
    """Schema-driven settings window, styled like the shelf."""

    def __init__(self, config: ConfigManager, parent=None):
        self._config = config
        self._controls: dict[str, object] = {}

        self._init_panel(
            "DropPoint+ Settings", WINDOW_W, WINDOW_H, parent,
            always_on_top=bool(config.get("always_on_top")),
            min_width=MIN_W, min_height=MIN_H,
            max_width=MAX_W, max_height=MAX_H,
        )
        self.setWindowTitle("Settings - DropPoint+")

        # --- body: schema-driven form --------------------------------------
        self._body = QWidget(self)
        self._body.setGeometry(
            _BODY_X, HEADER_H + 16, _BODY_W, WINDOW_H - HEADER_H - FOOTER_H - 32
        )
        self._body.setStyleSheet(_CONTROL_QSS)

        body = self._body
        form = QFormLayout(body)
        form.setContentsMargins(0, 0, 0, 0)
        form.setVerticalSpacing(14)
        form.setHorizontalSpacing(20)
        for key, schema in CONFIG_SCHEMA.items():
            control = self._create_control(key, schema)
            self._controls[key] = control
            label = QLabel(schema["title"])
            label.setStyleSheet(
                f"color: {rgba(TEXT_PRIMARY)}; font-size: 13px; font-weight: 500;"
            )
            form.addRow(label, control)

        # --- footer: toast + Apply/Cancel ----------------------------------
        self._status = QLabel("")
        self._status.setStyleSheet(_TOAST_STYLE)

        apply_btn = self._footer_button("Apply", primary=True)
        apply_btn.setDefault(True)
        apply_btn.clicked.connect(self._apply)
        cancel_btn = self._footer_button("Cancel")
        cancel_btn.clicked.connect(self.reject)

        footer = QHBoxLayout()
        footer.setContentsMargins(_BODY_X, 0, _BODY_X, 0)
        footer.setSpacing(12)
        footer.addWidget(self._status, 1)
        footer.addWidget(apply_btn)
        footer.addWidget(cancel_btn)

        self._footer_container = QWidget(self)
        self._footer_container.setGeometry(
            0, WINDOW_H - FOOTER_H, WINDOW_W, FOOTER_H
        )
        self._footer_container.setLayout(footer)

        self._load_values()

    def resizeEvent(self, event) -> None:
        """Re-lay the form body and footer strip to the new size."""
        super().resizeEvent(event)  # PanelMixin repositions the header chrome
        w, h = self.width(), self.height()
        self._body.setGeometry(
            _BODY_X, HEADER_H + 16, w - 2 * _BODY_X, h - HEADER_H - FOOTER_H - 32
        )
        self._footer_container.setGeometry(0, h - FOOTER_H, w, FOOTER_H)

    # -- footer buttons ------------------------------------------------------
    @staticmethod
    def _footer_button(text: str, primary: bool = False) -> QPushButton:
        btn = QPushButton(text)
        if primary:
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {rgba(PRIMARY_ACTIVE)};"
                f" color: {rgba(SURFACE)}; font-size: 12px; font-weight: 700;"
                " border: none; border-radius: 13px; padding: 6px 20px; }"
                f"QPushButton:hover {{ background-color:"
                f" {rgba(PRIMARY_ACTIVE, 210)}; }}"
            )
        else:
            btn.setStyleSheet(
                f"QPushButton {{ background-color: transparent;"
                f" color: {rgba(TEXT_SECONDARY)}; font-size: 12px;"
                " font-weight: 600; border: none; border-radius: 13px;"
                " padding: 6px 20px; }"
                f"QPushButton:hover {{ color: {rgba(TEXT_PRIMARY)};"
                f" background-color: {rgba(SURFACE_CONTAINER_HIGH)}; }}"
            )
        return btn

    # -- control construction ----------------------------------------------
    def _create_control(self, key: str, schema: dict) -> object:
        kind = schema["type"]
        if kind == "boolean":
            return QCheckBox()
        if kind == "enum":
            combo = QComboBox()
            for value in schema["values"]:
                combo.addItem(value.capitalize(), value)
            return combo
        if kind == "string":
            edit = QLineEdit()
            edit.setPlaceholderText("e.g. Shift+Capslock (needs a modifier)")
            return edit
        raise ValueError(f"Unsupported schema type {kind!r} for {key!r}")

    def _load_values(self) -> None:
        for key, control in self._controls.items():
            value = self._config.get(key)
            if isinstance(control, QCheckBox):
                control.setChecked(bool(value))
            elif isinstance(control, QComboBox):
                idx = control.findData(value)
                control.setCurrentIndex(idx if idx >= 0 else 0)
            elif isinstance(control, QLineEdit):
                control.setText(str(value or ""))

    # -- apply -------------------------------------------------------------
    def _apply(self) -> None:
        values = {}
        for key, control in self._controls.items():
            if isinstance(control, QCheckBox):
                values[key] = control.isChecked()
            elif isinstance(control, QComboBox):
                values[key] = control.currentData()
            elif isinstance(control, QLineEdit):
                values[key] = control.text().strip()
        self._config.set_many(values)
        self._show_toast("Settings applied")

    def _show_toast(self, text: str) -> None:
        self._status.setText(text)
        QTimer.singleShot(2000, lambda: self._status.setText(""))

    # -- painting -----------------------------------------------------------
    def paintEvent(self, event) -> None:
        from PySide6.QtGui import QPainter

        painter = QPainter(self)
        self._paint_panel(painter)
        painter.end()
        super().paintEvent(event)

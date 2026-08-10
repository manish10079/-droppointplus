"""Settings dialog.

Qt equivalent of ``src/Settings.js`` + ``renderer/settings-renderer.js`` +
``static/settings.html``. Controls are generated from ``CONFIG_SCHEMA``, so
adding a setting only touches ``app_config.py`` — the same schema-driven
behaviour the original implemented in JS with Tailwind/Preline.
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
)

from .app_config import CONFIG_SCHEMA, ConfigManager
from .colors import SUCCESS

_TOAST_STYLE = f"color: {SUCCESS.name()}; font-weight: bold;"


class SettingsDialog(QDialog):
    """Schema-driven settings window."""

    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self._config = config
        self._controls: dict[str, object] = {}

        self.setWindowTitle("Settings - DropPoint+")
        self.setFixedSize(600, 450)  # parity with the Electron settings window

        layout = QVBoxLayout(self)

        title = QLabel("DropPoint+ Settings")
        title.setStyleSheet("font-size: 18px; font-weight: bold; padding: 8px 0;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setVerticalSpacing(12)
        for key, schema in CONFIG_SCHEMA.items():
            control = self._create_control(key, schema)
            self._controls[key] = control
            form.addRow(schema["title"], control)
        layout.addLayout(form)
        layout.addStretch()

        self._status = QLabel("")
        self._status.setStyleSheet(_TOAST_STYLE)
        layout.addWidget(self._status)

        buttons = QHBoxLayout()
        apply_btn = QPushButton("Apply")
        apply_btn.setDefault(True)
        apply_btn.clicked.connect(self._apply)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(apply_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

        self._load_values()

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

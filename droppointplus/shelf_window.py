"""The shelf window — the View in the MVVM stack.

Qt equivalent of the Electron ``Instance`` class (``src/Window.js``) merged
with the shelf renderer (``renderer/droppoint.js`` + ``static/index.html``).

Per the development skills, this widget is presentation-only:

* it renders the state exposed by the ``ShelfViewModel`` (file count, the
  COLLECTION roster) and forwards raw input (drag events, mouse, keys);
* every decision ("WHAT should happen") lives in the ``ShelfViewModel``,
  which delegates the mechanics ("HOW") to the ``FileService``;
* window framing, animations and positioning remain view concerns.

The layout replicates the ``ui design/empty_drop_zone`` mockup: a header
with the brand + settings/close buttons, a dashed drop zone that highlights
purple while a drag hovers (the "selected" state), and a footer with the
collected-item count. Every colour comes from ``colors.py`` — nothing is
hardcoded here.
"""

from __future__ import annotations

import logging

from pathlib import Path

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QPointF,
    QRectF,
    Qt,
    QUrl,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QCursor,
    QDesktopServices,
    QGuiApplication,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QLabel, QWidget

from .destination_dialog import DestinationDialog
from .widgets.file_card import format_bytes

from . import colors
from .shelf_view_model import ShelfViewModel
from .widgets import FileList, ProgressWidget

logger = logging.getLogger(__name__)

CONTENT_W = 360          # visible shelf size (mockup scaled to 90%)
CONTENT_H = 450
# The painted drop shadow was removed (it trailed behind the window while
# dragging); SHADOW_MARGIN stays 0 so the layout math reads naturally.
SHADOW_MARGIN = 0
WINDOW_W = CONTENT_W + 2 * SHADOW_MARGIN
WINDOW_H = CONTENT_H + 2 * SHADOW_MARGIN
HEADER_H = 56            # top bar: brand + settings/close
FOOTER_H = 48            # bottom bar: collected-item count
DROP_PAD = 24            # padding inside the dashed drop zone
CIRCLE_SIZE = 80         # empty-state icon circle
DRAG_START_THRESHOLD_PX = 8

# Dashed drop-zone border: a custom pattern whose offset is animated so the
# dashes march around the drop zone (marching-ants). The cycle durations give
# a gentle drift while idle and a lively one while a drag hovers.
DASH_PATTERN = (6.0, 4.0)
DASH_PERIOD = float(sum(DASH_PATTERN))
DASH_CYCLE_IDLE_MS = 3000
DASH_CYCLE_ACTIVE_MS = 800

# The dashed drop zone (painted border + child-widget layout bounds).
DROP_RECT = QRectF(
    SHADOW_MARGIN + DROP_PAD,
    SHADOW_MARGIN + HEADER_H + DROP_PAD,
    CONTENT_W - 2 * DROP_PAD,
    CONTENT_H - HEADER_H - FOOTER_H - 2 * DROP_PAD,
)

_HEADER_BTN_STYLE = (
    f"QLabel {{ color: {colors.rgba(colors.ON_SURFACE_VARIANT)};"
    " font-size: 15px; border-radius: 11px; }"
    f"QLabel:hover {{ background-color:"
    f" {colors.rgba(colors.SURFACE_CONTAINER_HIGH)}; }}"
)


def _download_icon(size: int = 40) -> QPixmap:
    """Down-arrow-into-tray glyph (the mockup's ``download`` material icon)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(colors.PRIMARY, 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(pen)
    cx = size / 2
    painter.drawLine(QPointF(cx, 5), QPointF(cx, size - 14))          # shaft
    painter.drawLine(QPointF(cx - 9, size - 23), QPointF(cx, size - 14))
    painter.drawLine(QPointF(cx + 9, size - 23), QPointF(cx, size - 14))
    painter.drawLine(QPointF(9, size - 6), QPointF(size - 9, size - 6))  # tray
    painter.end()
    return pm


def _history_icon(size: int = 16) -> QPixmap:
    """Clock glyph for the header History button (a simple drawn clock)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(
        colors.ON_SURFACE_VARIANT, 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin
    )
    painter.setPen(pen)
    cx = cy = size / 2
    painter.drawEllipse(QPointF(cx, cy), size / 2 - 1, size / 2 - 1)
    painter.drawLine(QPointF(cx, cy), QPointF(cx, cy - size / 2 + 3.5))   # hour
    painter.drawLine(QPointF(cx, cy), QPointF(cx + size / 2 - 3.5, cy))   # min
    painter.end()
    return pm


class _HeaderButton(QLabel):
    """Small round header icon button (settings gear / history / close)."""

    clicked = Signal()

    def __init__(self, glyph: str | QPixmap, parent: QWidget):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)
        # QLabel does not enable WA_Hover by default; without it the
        # ``QLabel:hover`` stylesheet rule below never fires.
        self.setAttribute(Qt.WA_Hover, True)
        self.setStyleSheet(_HEADER_BTN_STYLE)
        if isinstance(glyph, QPixmap):
            self.setPixmap(glyph)
        else:
            self.setText(glyph)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # Emit LAST and consume the event: the close button's click closes
        # the window, whose registry entry is dropped immediately — the C++
        # widget (and its children) can be destroyed while this handler is
        # still running. Calling super() afterwards would touch a deleted
        # C++ object ("Internal C++ object already deleted"). The event
        # object itself is not owned by the widget, so accept() stays safe.
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        event.accept()


class _TextButton(QLabel):
    """Small text button (footer actions). Same lifetime-safe pattern as
    ``_HeaderButton``: emit LAST, then consume the event — never touch the
    widget after an emit that could destroy it.
    """

    clicked = Signal()

    def __init__(self, text: str, parent: QWidget, variant: str = "ghost"):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        if variant == "primary":
            style = (
                f"QLabel {{ background-color:"
                f" {colors.rgba(colors.PRIMARY_ACTIVE)};"
                f" color: {colors.rgba(colors.SURFACE)};"
                " font-size: 12px; font-weight: 700; border-radius: 13px; }"
                f"QLabel:hover {{ background-color:"
                f" {colors.rgba(colors.PRIMARY)}; }}"
            )
        elif variant == "outline":
            style = (
                f"QLabel {{ color: {colors.rgba(colors.PRIMARY)};"
                " font-size: 12px; font-weight: 600; border-radius: 13px;"
                f" border: 1px solid {colors.rgba(colors.PRIMARY_ACTIVE)}; }}"
                f"QLabel:hover {{ background-color:"
                f" {colors.rgba(colors.PRIMARY_TINT)}; }}"
            )
        else:
            style = (
                f"QLabel {{ color: {colors.rgba(colors.TEXT_SECONDARY)};"
                " font-size: 12px; font-weight: 600; border-radius: 13px; }"
                f"QLabel:hover {{ color: {colors.rgba(colors.TEXT_PRIMARY)};"
                f" background-color:"
                f" {colors.rgba(colors.SURFACE_CONTAINER_HIGH)}; }}"
            )
        self.setStyleSheet(style)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        event.accept()


class ShelfWindow(QWidget):
    """A single DropPoint+ shelf instance — renders a ShelfViewModel."""

    closed_signal = Signal(object)   # emits the window itself
    settings_requested = Signal()    # header gear pressed
    history_requested = Signal()     # header history (clock) pressed

    def __init__(
        self,
        instance_id: int,
        view_model: ShelfViewModel,
        always_on_top: bool,
    ):
        flags = Qt.FramelessWindowHint | Qt.Tool
        if always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        super().__init__(None, flags)

        self.instance_id = instance_id
        self._vm = view_model
        self._dragging_in = False
        self._drag_start_pos = None   # press origin, window-local (threshold)
        self._press_global = None     # press origin, screen coords (smooth move)
        self._win_start_pos = None    # window top-left at press (for moving)
        self._pressed_in_header = False
        self._drag_started = False
        self._win_dragging = False

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.ClickFocus)
        # Required: drag events are only delivered to widgets that accept
        # drops — without this the whole drag-IN feature never fires.
        self.setAcceptDrops(True)
        self.setFixedSize(WINDOW_W, WINDOW_H)
        self.setWindowTitle(f"DropPoint+ {instance_id}")

        self._build_ui()
        self._vm.files_changed.connect(self._refresh_ui)
        self._vm.close_requested.connect(self.close)
        self._vm.operation_started.connect(self._on_operation_started)
        self._vm.operation_progress.connect(self._on_operation_progress)
        self._vm.transfer_started.connect(self._on_transfer_started)
        self._vm.transfer_progress.connect(self._on_transfer_progress)
        self._vm.transfer_finished.connect(self._on_transfer_finished)
        self._vm.transfer_cancelled.connect(self._finish_transfer_ui)
        self._transfer_verb = ""
        self._transfer_dest = None
        self._transfer_count = 0
        self._refresh_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        # --- header -------------------------------------------------------
        self._brand = QLabel("DropPoint+", self)
        self._brand.setGeometry(
            SHADOW_MARGIN + 24, SHADOW_MARGIN + 17, 160, 22
        )
        self._brand.setStyleSheet(
            f"color: {colors.rgba(colors.PRIMARY)};"
            " font-size: 18px; font-weight: 700;"
        )

        # Header actions: history (clock) · settings (gear) · close (✕).
        self._btn_history = _HeaderButton(_history_icon(), self)
        self._btn_history.setToolTip("History")
        self._btn_history.setGeometry(
            SHADOW_MARGIN + CONTENT_W - 108, SHADOW_MARGIN + 17, 22, 22
        )
        self._btn_history.clicked.connect(self.history_requested.emit)

        self._btn_settings = _HeaderButton("⚙", self)
        self._btn_settings.setToolTip("Settings")
        self._btn_settings.setGeometry(
            SHADOW_MARGIN + CONTENT_W - 78, SHADOW_MARGIN + 17, 22, 22
        )
        self._btn_settings.clicked.connect(self.settings_requested.emit)

        self._btn_close = _HeaderButton("✕", self)
        self._btn_close.setToolTip("Close")
        self._btn_close.setGeometry(
            SHADOW_MARGIN + CONTENT_W - 48, SHADOW_MARGIN + 17, 22, 22
        )
        self._btn_close.clicked.connect(self.close)

        # --- empty state --------------------------------------------------
        self._circle = QLabel(self)
        self._circle.setAlignment(Qt.AlignCenter)
        self._circle.setGeometry(
            SHADOW_MARGIN + CONTENT_W // 2 - CIRCLE_SIZE // 2,
            round(DROP_RECT.y()) + 44,
            CIRCLE_SIZE,
            CIRCLE_SIZE,
        )
        self._circle.setPixmap(_download_icon(40))
        self._circle.setStyleSheet(
            f"background-color: {colors.rgba(colors.SURFACE_CONTAINER_HIGH)};"
            f" border: 1px solid {colors.rgba(colors.BORDER_SUBTLE)};"
            " border-radius: 40px;"
        )

        self._title = QLabel("Drop files here", self)
        self._title.setAlignment(Qt.AlignCenter)
        self._title.setGeometry(
            SHADOW_MARGIN,
            round(DROP_RECT.y()) + 44 + CIRCLE_SIZE + 18,
            CONTENT_W,
            34,
        )
        self._title.setStyleSheet(
            f"color: {colors.rgba(colors.TEXT_PRIMARY)};"
            " font-size: 24px; font-weight: 700;"
        )

        self._subtitle = QLabel("Drop files or folders to collect them", self)
        self._subtitle.setAlignment(Qt.AlignCenter)
        self._subtitle.setGeometry(
            SHADOW_MARGIN,
            round(DROP_RECT.y()) + 44 + CIRCLE_SIZE + 52,
            CONTENT_W,
            24,
        )
        self._subtitle.setStyleSheet(
            f"color: {colors.rgba(colors.ON_SURFACE_VARIANT)};"
            " font-size: 15px; font-weight: 500;"
        )

        self._hint = QLabel(
            "Files stay here until you're\nready to move or copy them.", self
        )
        self._hint.setAlignment(Qt.AlignCenter)
        self._hint.setGeometry(
            SHADOW_MARGIN + 16,
            round(DROP_RECT.bottom()) - 42,
            CONTENT_W - 32,
            36,
        )
        self._hint.setStyleSheet(
            f"color: {colors.rgba(colors.TEXT_SECONDARY)}; font-size: 13px;"
        )

        # --- holding state: scrollable COLLECTION roster -------------------
        # Rows forward remove_requested -> ViewModel.remove_item; presses on
        # row bodies fall through to the window (drag-out / window move).
        self._file_list = FileList(self)
        self._file_list.setGeometry(
            round(DROP_RECT.x()) + 10,
            round(DROP_RECT.y()) + 8,
            round(DROP_RECT.width()) - 20,
            round(DROP_RECT.height()) - 16,
        )
        self._file_list.remove_requested.connect(self._vm.remove_item)
        self._file_list.hide()

        # --- footer -------------------------------------------------------
        self._items_label = QLabel("0 items", self)
        self._items_label.setGeometry(
            SHADOW_MARGIN + 24, SHADOW_MARGIN + CONTENT_H - FOOTER_H + 15, 100, 18
        )
        self._items_label.setStyleSheet(
            f"color: {colors.rgba(colors.TEXT_SECONDARY)};"
            " font-size: 12px; font-weight: 500;"
        )

        # Footer actions: Clear all · MOVE (outline) · COPY (filled).
        self._btn_clear = _TextButton("Clear all", self)
        self._btn_clear.setGeometry(
            SHADOW_MARGIN + 136,
            SHADOW_MARGIN + CONTENT_H - FOOTER_H + 11,
            66,
            26,
        )
        self._btn_clear.clicked.connect(self._vm.clear)

        self._btn_move = _TextButton("MOVE", self, variant="outline")
        self._btn_move.setGeometry(
            SHADOW_MARGIN + 212,
            SHADOW_MARGIN + CONTENT_H - FOOTER_H + 11,
            58,
            26,
        )
        self._btn_move.clicked.connect(lambda: self._open_destination_picker("move"))

        self._btn_copy = _TextButton("COPY", self, variant="primary")
        self._btn_copy.setGeometry(
            SHADOW_MARGIN + 278,
            SHADOW_MARGIN + CONTENT_H - FOOTER_H + 11,
            58,
            26,
        )
        self._btn_copy.clicked.connect(lambda: self._open_destination_picker("copy"))
        for btn in (self._btn_clear, self._btn_move, self._btn_copy):
            btn.hide()

        # --- operation overlay (progress / success) -----------------------
        self._progress = ProgressWidget(self)
        self._progress.setGeometry(
            round(DROP_RECT.x()) + 20,
            round(DROP_RECT.y()) + (round(DROP_RECT.height()) - 96) // 2,
            round(DROP_RECT.width()) - 40,
            96,
        )
        self._progress.setAttribute(Qt.WA_StyledBackground, True)
        self._progress.setStyleSheet(
            f"background-color: {colors.rgba(colors.SURFACE_CONTAINER, 230)};"
            " border-radius: 8px;"
        )
        self._progress.cancel_requested.connect(self._vm.cancel_transfer)
        self._progress.hide()

        # Transfer-complete panel (reuses the overlay area).
        overlay_x = round(DROP_RECT.x()) + 20
        overlay_y = round(DROP_RECT.y()) + (round(DROP_RECT.height()) - 96) // 2
        self._success = QLabel("", self)
        self._success.setAlignment(Qt.AlignCenter)
        self._success.setWordWrap(True)
        self._success.setGeometry(overlay_x, overlay_y + 10, 272, 40)
        self._success.setStyleSheet(
            f"color: {colors.rgba(colors.SUCCESS)};"
            " font-size: 13px; font-weight: 600;"
        )
        self._btn_open_dest = _TextButton("Open destination", self, variant="outline")
        self._btn_open_dest.setGeometry(overlay_x + 16, overlay_y + 58, 120, 26)
        self._btn_open_dest.clicked.connect(self._open_destination)
        self._btn_done = _TextButton("Done", self, variant="primary")
        self._btn_done.setGeometry(overlay_x + 272 - 16 - 76, overlay_y + 58, 76, 26)
        self._btn_done.clicked.connect(self._finish_transfer_ui)
        for w in (self._success, self._btn_open_dest, self._btn_done):
            w.hide()

        # Pulsing dashed border while a drag hovers over the window.
        self._border_anim = QVariantAnimation(self)
        self._border_anim.setStartValue(60)
        self._border_anim.setEndValue(220)
        self._border_anim.setDuration(700)
        self._border_anim.setLoopCount(-1)
        self._border_anim.setEasingCurve(QEasingCurve.InOutSine)
        self._border_anim.valueChanged.connect(self.update)

        # Marching-ants border: the dash pattern offset drifts continuously
        # so the dashes appear to travel around the drop zone (runs for the
        # life of the shelf; a drag-over speeds it up).
        self._dash_anim = QVariantAnimation(self)
        self._dash_anim.setStartValue(0.0)
        self._dash_anim.setEndValue(DASH_PERIOD)
        self._dash_anim.setDuration(DASH_CYCLE_IDLE_MS)
        self._dash_anim.setLoopCount(-1)
        self._dash_anim.setEasingCurve(QEasingCurve.Linear)
        self._dash_anim.valueChanged.connect(self._on_dash_tick)
        self._last_dash_step = -1
        self._dash_anim.start()

    def _refresh_ui(self, *_args) -> None:
        n = self._vm.count
        holding = n > 0
        empty_visible = not holding and not self._vm.is_working
        for widget in (self._circle, self._title, self._subtitle, self._hint):
            widget.setVisible(empty_visible)
        self._file_list.setVisible(holding)
        self._btn_clear.setVisible(holding)
        self._btn_copy.setVisible(holding)
        self._btn_move.setVisible(holding)
        self._items_label.setText(f"{n} item{'s' if n != 1 else ''}")
        # Sync unconditionally (a no-op when the roster is unchanged) so the
        # list never keeps stale rows after clear/remove.
        self._file_list.set_items(self._vm.files)
        self.update()

    # ----------------------------------------------------------- positioning
    @property
    def view_model(self) -> ShelfViewModel:
        """The VM this window renders (exposed for the window manager)."""
        return self._vm

    def position_at_edge(self, edge: str, area) -> None:
        """Dock the shelf next to a screen edge (drag-summon).

        ``edge`` is "top"/"bottom"/"left"/"right"; ``area`` is the screen's
        available geometry the strip belongs to. The shelf is centred along
        the edge and clamped inside the screen.
        """
        x = area.center().x() - CONTENT_W // 2
        y = area.center().y() - CONTENT_H // 2
        if edge == "top":
            y = area.top()
        elif edge == "bottom":
            y = area.bottom() - CONTENT_H + 1
        elif edge == "left":
            x = area.left()
        else:  # right
            x = area.right() - CONTENT_W + 1
        x = max(area.left(), min(x, area.right() - CONTENT_W))
        y = max(area.top(), min(y, area.bottom() - CONTENT_H))
        self.move(x, y)

    def position_at_cursor(self) -> None:
        """Open just above the cursor, clamped to the screen (Window.js parity)."""
        pos = QCursor.pos()
        screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        # Position the content exactly where the original did (top-left at
        # the cursor).
        x = pos.x()
        y = pos.y() - CONTENT_H
        if x + CONTENT_W > area.right():
            x = area.right() - CONTENT_W
        if y < area.top():
            y = area.top()
        self.move(x, y)

    def position_center(self) -> None:
        """Top-centre of the primary screen (Window.js parity)."""
        area = QGuiApplication.primaryScreen().availableGeometry()
        self.move(
            area.center().x() - CONTENT_W // 2,
            area.top(),
        )

    # ------------------------------------------------------------- drag-in
    def dragEnterEvent(self, event) -> None:
        if self._vm.is_working:
            event.ignore()
            return
        if self._vm.can_accept_drop(event):
            self._dragging_in = True
            self._start_border_animation()
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if self._vm.can_accept_drop(event):
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:
        self._dragging_in = False
        self._stop_border_animation()
        self.update()

    def dropEvent(self, event) -> None:
        self._dragging_in = False
        self._stop_border_animation()
        self._vm.handle_drop(event)
        event.acceptProposedAction()

    # ----------------------------------------------- window move / drag-out
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and not self._vm.is_working:
            self._drag_start_pos = event.position().toPoint()
            self._press_global = event.globalPosition().toPoint()
            self._win_start_pos = self.pos()
            self._pressed_in_header = (
                event.position().y() <= SHADOW_MARGIN + HEADER_H
            )
            self._drag_started = False
            self._win_dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start_pos is None or self._vm.is_working:
            super().mouseMoveEvent(event)
            return
        # Window-local positions stop changing once the window slides under
        # the cursor, so the MOVE must use screen (global) coords or the
        # window jumps once and then stalls. The 8px threshold still uses
        # the local delta (it is only evaluated before the drag begins).
        local_delta = event.position().toPoint() - self._drag_start_pos
        global_delta = event.globalPosition().toPoint() - self._press_global
        # The header is always a move handle; the content area also moves
        # the window when it is empty. With files held, the content drags
        # the files out instead (see below).
        window_move = self._pressed_in_header or not self._vm.files
        if window_move:
            if (
                not self._drag_started
                and local_delta.manhattanLength() >= DRAG_START_THRESHOLD_PX
            ):
                self._drag_started = True
                self._win_dragging = True
                self.setCursor(Qt.ClosedHandCursor)
            if self._win_dragging:
                self.move(self._win_start_pos + global_delta)
                return
            super().mouseMoveEvent(event)
            return
        # Files held and pressed in the content area: drag them out.
        # Blocks during the native drag; may close the window.
        if (
            not self._drag_started
            and local_delta.manhattanLength() >= DRAG_START_THRESHOLD_PX
        ):
            self._drag_started = True
            self._vm.drag_out(self)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._win_dragging:
            self.unsetCursor()
        self._drag_start_pos = None
        self._press_global = None
        self._win_start_pos = None
        self._drag_started = False
        self._win_dragging = False
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------- helpers
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape and self._vm.files:
            self._vm.clear()
        else:
            super().keyPressEvent(event)

    # ----------------------------------------------------------- operation
    def _enter_operation_view(self) -> None:
        """Freeze the shelf while a background operation runs."""
        for widget in (
            self._circle,
            self._title,
            self._subtitle,
            self._hint,
            self._file_list,
        ):
            widget.hide()
        self._btn_history.hide()
        self._btn_settings.hide()
        self._btn_close.hide()
        self._btn_clear.hide()
        self._btn_copy.hide()
        self._btn_move.hide()
        self.setAcceptDrops(False)
        self.update()

    def _leave_operation_view(self) -> None:
        """Restore the shelf after an operation ends or is cancelled."""
        self._progress.hide()
        self.setAcceptDrops(True)
        self._refresh_ui()

    def _on_operation_started(self) -> None:
        """Move-mode deletion is running — show progress, freeze the shelf.

        Note: nothing here is ever reset — the ViewModel always follows with
        ``close_requested`` once the worker finishes, so the window closes
        (state restore would only matter if the auto-close were removed).
        """
        self._progress.show()
        self._progress.set_progress(0)
        self._progress.set_status("Moving files…")
        self._progress.set_detail("")
        self._progress.set_cancellable(False)
        self._items_label.setText("Moving…")
        self._enter_operation_view()

    def _on_operation_progress(self, done: int, total: int) -> None:
        percent = (done / total * 100) if total else 0
        self._progress.set_progress(percent)
        self._progress.set_status(f"Moving {done} of {total}…")

    # -------------------------------------------------------------- transfer
    def _open_destination_picker(self, action: str) -> None:
        """Open the destination picker; a selection starts the transfer."""
        dialog = DestinationDialog(self._vm.config, action=action, parent=self)
        dialog.selected.connect(lambda dest: self._vm.start_transfer(dest, action))
        dialog.exec()

    def _on_transfer_started(self, verb: str, destination: str) -> None:
        self._transfer_verb = verb
        self._transfer_dest = destination
        self._transfer_count = self._vm.count
        self._progress.show()
        self._progress.set_progress(0)
        self._progress.set_status(f"{verb} files…")
        self._progress.set_detail(Path(destination).name)
        self._progress.set_cancellable(True)
        self._enter_operation_view()

    def _on_transfer_progress(
        self, done: int, total: int, speed: float
    ) -> None:
        if not total:
            return
        self._progress.set_progress(done / total * 100)
        self._progress.set_status(
            f"{self._transfer_verb} {format_bytes(done)} of {format_bytes(total)}"
        )
        detail = f"{format_bytes(round(speed))}/s" if speed > 0 else ""
        if speed > 0 and done < total:
            detail += f" · ~{(total - done) / speed:.0f}s left"
        self._progress.set_detail(detail)

    def _on_transfer_finished(self, failures: int) -> None:
        """Transfer done — show the success panel (design.md #7)."""
        self._progress.hide()
        dest_name = Path(self._transfer_dest or "").name or (self._transfer_dest or "")
        n = self._transfer_count
        msg = (
            f"✓ {self._transfer_verb} complete —"
            f" {n} item{'s' if n != 1 else ''} → {dest_name}"
        )
        if failures:
            msg += f"  ({failures} failed — still in collection)"
        self._success.setText(msg)
        self._success.show()
        self._btn_open_dest.show()
        self._btn_done.show()
        self.update()

    def _finish_transfer_ui(self) -> None:
        """Leave the success panel / cancelled state and restore the shelf."""
        self._success.hide()
        self._btn_open_dest.hide()
        self._btn_done.hide()
        self._leave_operation_view()

    def _open_destination(self) -> None:
        if self._transfer_dest:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._transfer_dest))
        self._finish_transfer_ui()

    def _on_dash_tick(self, value: float) -> None:
        """Repaint only when the marching offset crossed a 0.5 px step.

        QVariantAnimation ticks at ~60 Hz, but the border only needs a few
        repaints per cycle segment — quantizing keeps an idle shelf's
        repaints in the low single digits per second.
        """
        step = round(float(value) * 2) / 2
        if step != self._last_dash_step:
            self._last_dash_step = step
            self.update()

    def _start_border_animation(self) -> None:
        if self._border_anim.state() != QAbstractAnimation.State.Running:
            self._border_anim.start()
        self._dash_anim.setDuration(DASH_CYCLE_ACTIVE_MS)

    def _stop_border_animation(self) -> None:
        self._border_anim.stop()
        self._dash_anim.setDuration(DASH_CYCLE_IDLE_MS)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        full = QRectF(0, 0, self.width(), self.height())

        # No drop shadow (removed: it trailed behind the window when
        # dragging). The rounded window is drawn with a translucent
        # background, so the corners stay transparent.
        content = full.adjusted(
            SHADOW_MARGIN, SHADOW_MARGIN, -SHADOW_MARGIN, -SHADOW_MARGIN
        )
        painter.setBrush(colors.SURFACE)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(content, 12, 12)

        # Header / footer dividers.
        painter.setPen(QPen(colors.BORDER_SUBTLE, 1))
        header_y = SHADOW_MARGIN + HEADER_H
        painter.drawLine(QPointF(content.left() + 1, header_y),
                         QPointF(content.right() - 1, header_y))
        footer_y = SHADOW_MARGIN + CONTENT_H - FOOTER_H
        painter.drawLine(QPointF(content.left() + 1, footer_y),
                         QPointF(content.right() - 1, footer_y))

        # The dashed drop zone — idle grey, purple + glow while dragging
        # (the "selected" state from the mockup).
        rect = DROP_RECT
        if self._dragging_in:
            # Outer glow rings behind the border.
            for ring in range(3, 0, -1):
                painter.setPen(Qt.NoPen)
                painter.setBrush(colors.with_alpha(
                    colors.PRIMARY_ACTIVE, colors.GLOW_ALPHA_STEP * ring))
                painter.drawRoundedRect(rect.adjusted(-ring, -ring, ring, ring),
                                        12, 12)
            painter.setBrush(colors.PRIMARY_TINT)
            value = self._border_anim.currentValue()
            alpha = int(value) if value is not None else self._border_anim.endValue()
            pen_color = colors.with_alpha(colors.PRIMARY_ACTIVE, int(alpha))
        else:
            painter.setBrush(Qt.NoBrush)
            pen_color = colors.BORDER_SUBTLE
        pen = QPen(pen_color, 2, Qt.DashLine)
        pen.setDashPattern(DASH_PATTERN)
        # March the dashes around the border: the pattern is periodic, so the
        # animated offset loops seamlessly (negative = forward motion).
        pen.setDashOffset(-float(self._dash_anim.currentValue() or 0.0))
        painter.setPen(pen)
        painter.drawRoundedRect(rect, 12, 12)

        # Divider above the footer hint (empty state only).
        if not self._vm.count and not self._vm.is_working:
            painter.setPen(QPen(colors.with_alpha(
                colors.BORDER_SUBTLE, colors.DIVIDER_ALPHA), 1))
            y = self._hint.y() - 16
            painter.drawLine(QPointF(rect.left() + 12, y),
                             QPointF(rect.right() - 12, y))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # The marching border runs while visible only: an infinite animation
        # must never keep ticking on a hidden or closed window (it would burn
        # CPU for the app's auto-hidden shelves and can outlive the widget at
        # teardown). The state guard makes the initial start in _build_ui and
        # re-shows idempotent.
        if self._dash_anim.state() != QAbstractAnimation.State.Running:
            self._dash_anim.start()

    def hideEvent(self, event) -> None:
        self._dash_anim.stop()
        super().hideEvent(event)

    def closeEvent(self, event) -> None:
        self._border_anim.stop()
        self._dash_anim.stop()
        self.closed_signal.emit(self)
        super().closeEvent(event)

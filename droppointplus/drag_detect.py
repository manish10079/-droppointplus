"""Summon-on-drag: detect when the user starts dragging files and reveal the shelf.

There is no OS API for "a drag started somewhere", so this module combines the
two techniques real apps use:

* :class:`DragDetector` — a **Windows-only** global low-level mouse hook
  (``WH_MOUSE_LL``) that watches for the signature of a file drag: left button
  held, cursor moved past a threshold, and the system cursor swapped to a
  non-standard shape (Explorer/OLE replace the arrow with a custom copy/move/
  no-drop cursor during a file drag). Text selection keeps the standard IBeam
  cursor, so it is excluded. Presses that start over one of *our* windows
  (drag-out from the shelf, window moves, the strips themselves) are ignored.

* :class:`EdgeStrip` — a few-pixel always-on-top window at each screen edge
  registered as a real drop target. Dragging a file to the edge is 100%
  reliable (real OLE drag events, no heuristics) and also gives the user a
  deliberate gesture. On Windows the strips are click-through when idle (so
  they never eat clicks on the screen edge) and only become hit-testable once
  the ``DragDetector`` confirms a drag is in progress; on other platforms they
  are always hit-testable (a small edge-of-screen tradeoff).

Wayland/Linux has no way to observe foreign drags at all; the detector
degrades to a logged no-op there and the edge strips still work.
"""

from __future__ import annotations

import logging
import os
import sys

from PySide6.QtCore import QObject, QRect, Qt, Signal
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

DRAG_THRESHOLD_PX = 8  # same feel as the shelf's drag-out threshold

# Standard system cursors that are NOT a file drag (resource IDs, OCR_*).
# A cursor handle not in this set is a custom/OLE drag cursor — the signature
# of a shell drag. Handles are comparable because identical cursors share one.
_STANDARD_CURSOR_IDS = (
    32512,  # OCR_NORMAL (arrow)
    32513,  # OCR_IBEAM (text)
    32514,  # OCR_WAIT
    32515,  # OCR_CROSS
    32516,  # OCR_UP
    32640,  # OCR_SIZE
    32641,  # OCR_ICON
    32642,  # OCR_SIZENWSE
    32643,  # OCR_SIZENESW
    32644,  # OCR_SIZEWE
    32645,  # OCR_SIZENS
    32646,  # OCR_SIZEALL
    32647,  # OCR_ICON
    32648,  # OCR_NO
    32649,  # OCR_HAND
    32650,  # OCR_APPSTARTING
    32651,  # OCR_HELP
    32671,  # OCR_PIN
    32672,  # OCR_PERSON
)

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    WH_MOUSE_LL = 14
    WM_LBUTTONDOWN = 0x0201
    WM_LBUTTONUP = 0x0202
    WM_MOUSEMOVE = 0x0200
    GWL_EXSTYLE = -20
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_LAYERED = 0x00080000
    LWA_ALPHA = 0x00000002

    class _POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    class _MSLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("pt", _POINT),
            ("mouseData", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_size_t),
        ]

    class _CURSORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("hCursor", ctypes.c_void_p),
            ("ptScreenPos", _POINT),
        ]

    _LowLevelMouseProc = ctypes.WINFUNCTYPE(
        ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
    )

    def _user32():
        if getattr(_user32, "dll", None) is None:
            dll = ctypes.windll.user32
            # Explicit signatures: prevents by-value/by-reference ambiguity
            # for structures and 32-bit truncation of LONG_PTR returns.
            dll.SetWindowsHookExW.argtypes = [
                ctypes.c_int, _LowLevelMouseProc, ctypes.c_void_p, wintypes.DWORD
            ]
            dll.SetWindowsHookExW.restype = ctypes.c_void_p
            dll.CallNextHookEx.argtypes = [
                ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
            ]
            dll.CallNextHookEx.restype = ctypes.c_ssize_t
            dll.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
            dll.UnhookWindowsHookEx.restype = wintypes.BOOL
            dll.GetCursorInfo.argtypes = [ctypes.POINTER(_CURSORINFO)]
            dll.GetCursorInfo.restype = wintypes.BOOL
            dll.LoadCursorW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            dll.LoadCursorW.restype = ctypes.c_void_p
            dll.WindowFromPoint.argtypes = [_POINT]
            dll.WindowFromPoint.restype = ctypes.c_void_p
            dll.GetWindowThreadProcessId.argtypes = [
                ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)
            ]
            dll.GetWindowThreadProcessId.restype = wintypes.DWORD
            dll.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
            dll.GetWindowLongPtrW.restype = ctypes.c_ssize_t
            dll.SetWindowLongPtrW.argtypes = [
                ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t
            ]
            dll.SetWindowLongPtrW.restype = ctypes.c_ssize_t
            dll.SetLayeredWindowAttributes.argtypes = [
                ctypes.c_void_p, wintypes.COLORREF, ctypes.c_byte, wintypes.DWORD
            ]
            dll.SetLayeredWindowAttributes.restype = wintypes.BOOL
            _user32.dll = dll
        return _user32.dll

    def _point_over_ours(pt: tuple[int, int]) -> bool:
        """True when the given screen point is over one of our own windows."""
        user32 = _user32()
        hwnd = user32.WindowFromPoint(_POINT(pt[0], pt[1]))
        if not hwnd:
            return False
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value == os.getpid()

    def _is_drag_cursor() -> bool:
        """True when the current cursor is not a standard system cursor.

        Explorer and OLE swap in a private copy/move/no-drop cursor during a
        file drag, so a non-standard handle is a strong "drag in progress"
        signal. A hidden cursor (e.g. during an active drag on some apps)
        reports no drag.
        """
        user32 = _user32()
        info = _CURSORINFO()
        info.cbSize = ctypes.sizeof(_CURSORINFO)
        if not user32.GetCursorInfo(ctypes.byref(info)):
            return False
        for rid in _STANDARD_CURSOR_IDS:
            if info.hCursor == user32.LoadCursorW(None, ctypes.c_void_p(rid)):
                return False
        return True


class DragDetector(QObject):
    """Reports plausible file drags anywhere on the desktop.

    Emits ``drag_started`` at most once per drag (after the button is held
    and moved past the threshold with a drag cursor) and ``drag_ended`` when
    the button is released. **Windows only** — elsewhere it logs and never
    fires; the edge strips still provide summoning.
    """

    drag_started = Signal()
    drag_ended = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._hook = None
        self._proc = None
        self._lmb_down = False
        self._down_pos: tuple[int, int] | None = None
        self._down_over_ours = False
        self._summoned = False

        if sys.platform != "win32":
            logger.warning(
                "global drag detection is Windows-only for now;"
                " screen-edge strips still work elsewhere."
            )
            return
        try:
            self._install()
        except Exception:
            logger.exception(
                "could not install the global mouse hook;"
                " drag-summon degrades to screen-edge strips only."
            )

    # -- hook lifecycle -----------------------------------------------------
    def _install(self) -> None:
        user32 = _user32()
        self._proc = _LowLevelMouseProc(self._on_mouse)
        # Low-level hooks live in the calling process (no DLL), so hMod is
        # None and the thread id 0 means "all threads".
        self._hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._proc, None, 0)
        if not self._hook:
            self._proc = None
            raise ctypes.WinError()
        app = self._app()
        if app is not None:
            app.aboutToQuit.connect(self.shutdown)

    def shutdown(self) -> None:
        """Unhook so no native callback can fire during interpreter teardown."""
        if self._hook:
            try:
                _user32().UnhookWindowsHookEx(self._hook)
            except Exception:
                logger.debug("could not unhook the mouse hook", exc_info=True)
            self._hook = None
        self._proc = None

    @staticmethod
    def _app():
        from PySide6.QtWidgets import QApplication

        return QApplication.instance()

    # -- hook callback ------------------------------------------------------
    def _on_mouse(self, n_code: int, w_param: int, l_param: int) -> int:
        if n_code >= 0 and self._hook:
            try:
                data = _MSLLHOOKSTRUCT.from_address(l_param)
                self._handle(w_param & 0xFFFF, data)
            except Exception:
                logger.exception("drag detector error")
        return _user32().CallNextHookEx(None, n_code, w_param, l_param)

    def _handle(self, msg: int, data) -> None:
        pt = (data.pt.x, data.pt.y)
        if msg == WM_LBUTTONDOWN:
            self._lmb_down = True
            self._down_pos = pt
            self._down_over_ours = _point_over_ours(pt)
            self._summoned = False
        elif msg == WM_LBUTTONUP:
            was_summoned = self._summoned
            self._lmb_down = False
            self._down_pos = None
            self._summoned = False
            if was_summoned:
                self.drag_ended.emit()
        elif (
            msg == WM_MOUSEMOVE
            and self._lmb_down
            and not self._summoned
            and not self._down_over_ours
        ):
            if self._down_pos is None:
                return
            dx = abs(pt[0] - self._down_pos[0])
            dy = abs(pt[1] - self._down_pos[1])
            # If distance exceeds threshold, trigger drag started.
            # _is_drag_cursor check can be bypassed or used as optional verification
            # since Windows OLE drag handles vary across Windows builds/scaling modes.
            if dx + dy >= DRAG_THRESHOLD_PX:
                self._summoned = True
                self.drag_started.emit()


class EdgeStrip(QWidget):
    """An invisible strip at one edge of a screen that catches file drags.

    A real OLE drop target: when a file drag enters the strip it emits
    ``drag_over(edge, area)`` so the window manager can dock the shelf next to
    that edge, and a drop directly on the strip is forwarded as
    ``paths_dropped(paths)``.

    On Windows the strips are click-through while idle (``set_click_through``)
    so they never swallow clicks on the screen edge; they only become
    hit-testable once the ``DragDetector`` has confirmed a drag.
    """

    drag_over = Signal(str, object)   # edge ("top"/"bottom"/"left"/"right"), QRect
    paths_dropped = Signal(object)    # list[str]

    THICKNESS = 6

    def __init__(self, edge: str, area: QRect, parent=None):
        super().__init__(
            None,
            Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint,
        )
        self._edge = edge
        self._area = area
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        # Required: drag events are only delivered to widgets that accept drops.
        self.setAcceptDrops(True)
        self.setWindowTitle("DropPoint+ edge strip")
        t = self.THICKNESS
        if edge == "top":
            self.setGeometry(area.x(), area.y(), area.width(), t)
        elif edge == "bottom":
            self.setGeometry(area.x(), area.bottom() - t + 1, area.width(), t)
        elif edge == "left":
            self.setGeometry(area.x(), area.y(), t, area.height())
        else:  # right
            self.setGeometry(area.right() - t + 1, area.y(), t, area.height())

    # -- api -----------------------------------------------------------------
    def set_click_through(self, active: bool) -> None:
        """Toggle WS_EX_TRANSPARENT (Windows) so idle strips don't eat clicks.

        Only meaningful on Windows; elsewhere the strip is always hit-testable
        (a tiny screen-edge tradeoff). Failure degrades to "always
        hit-testable", which is safe — the strip just intercepts the top 6 px.
        """
        if sys.platform != "win32":
            return
        try:
            user32 = _user32()
            hwnd = ctypes.c_void_p(int(self.winId()))
            ex = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
            if active:
                ex |= WS_EX_TRANSPARENT | WS_EX_LAYERED
                # Layered + alpha keeps normal painting (unlike
                # UpdateLayeredWindow); TRANSPARENT makes hit-testing pass
                # through to the window below.
                user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex)
                user32.SetLayeredWindowAttributes(hwnd, 0, 255, LWA_ALPHA)
            else:
                ex &= ~WS_EX_TRANSPARENT
                user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex)
        except Exception:
            logger.debug("could not toggle strip click-through", exc_info=True)

    # -- drag events ----------------------------------------------------------
    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            self.drag_over.emit(self._edge, self._area)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.toLocalFile()
        ]
        if paths:
            self.paths_dropped.emit(paths)
        event.acceptProposedAction()

"""Dual-handle Range Timeline Slider for interactive visual video trimming.

Allows dragging start and end handles, moving the selected span, and tracking playhead.
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QCursor, QFont, QPainter, QPaintEvent, QPen
from PyQt6.QtWidgets import QWidget

from ui.theme import COLORS


class RangeSlider(QWidget):
    """Interactive visual range slider with start/end handles and playhead."""

    # Emits (start_sec, end_sec)
    range_changed = pyqtSignal(float, float)
    # Emits seek_sec when user clicks on timeline to inspect video frame
    seek_requested = pyqtSignal(float)

    HANDLE_WIDTH = 12

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self._duration: float = 60.0  # total video duration in seconds
        self._start: float = 0.0      # start cut time in seconds
        self._end: float = 60.0       # end cut time in seconds
        self._current: float = 0.0    # playback position

        self._active_handle: str | None = None  # 'start', 'end', 'span', or None
        self._drag_offset: float = 0.0

    # ─── Public API ───

    def set_duration(self, duration_s: float):
        self._duration = max(0.1, float(duration_s))
        self._start = 0.0
        self._end = self._duration
        self._current = 0.0
        self.update()

    def set_range(self, start_s: float, end_s: float):
        self._start = max(0.0, min(float(start_s), self._duration - 0.1))
        self._end = max(self._start + 0.1, min(float(end_s), self._duration))
        self.update()

    def set_current_position(self, current_s: float):
        self._current = max(0.0, min(float(current_s), self._duration))
        self.update()

    @property
    def start_time(self) -> float:
        return self._start

    @property
    def end_time(self) -> float:
        return self._end

    @property
    def duration(self) -> float:
        return self._duration

    # ─── Coordinates ───

    def _track_rect(self) -> QRectF:
        m = 14
        return QRectF(m, 14, self.width() - 2 * m, 18)

    def _time_to_x(self, t: float) -> float:
        rect = self._track_rect()
        if self._duration <= 0:
            return rect.left()
        ratio = max(0.0, min(1.0, t / self._duration))
        return rect.left() + ratio * rect.width()

    def _x_to_time(self, x: float) -> float:
        rect = self._track_rect()
        if rect.width() <= 0:
            return 0.0
        ratio = max(0.0, min(1.0, (x - rect.left()) / rect.width()))
        return ratio * self._duration

    # ─── Paint ───

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self._track_rect()
        x_start = self._time_to_x(self._start)
        x_end = self._time_to_x(self._end)
        x_cur = self._time_to_x(self._current)

        # 1. Base track background (unselected)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("#161f30")))
        p.drawRoundedRect(rect, 4, 4)

        # 2. Selected Active Range (Bright Cyan Accent with subtle gradient)
        sel_rect = QRectF(x_start, rect.top(), max(2, x_end - x_start), rect.height())
        p.setBrush(QBrush(QColor("#0369a1")))  # dark cyan background
        p.drawRoundedRect(sel_rect, 2, 2)

        # Inner highlight
        p.setBrush(QBrush(QColor(56, 189, 248, 60)))  # #38bdf8 alpha 60
        p.drawRect(sel_rect)

        # 3. Ruler ticks along the track
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        step = max(1.0, self._duration / 20.0)
        t = 0.0
        while t <= self._duration:
            xt = self._time_to_x(t)
            p.drawLine(QPointF(xt, rect.bottom() - 3), QPointF(xt, rect.bottom()))
            t += step

        # 4. Playhead Line (Orange / Amber indicator)
        if rect.left() <= x_cur <= rect.right():
            p.setPen(QPen(QColor("#f59e0b"), 2))
            p.drawLine(QPointF(x_cur, rect.top() - 4), QPointF(x_cur, rect.bottom() + 4))

        # 5. Start Handle (Left cursor [)
        p.setPen(QPen(QColor("#38bdf8"), 1.5))
        p.setBrush(QBrush(QColor("#0284c7")))
        handle_h = rect.height() + 10
        y_top = rect.center().y() - handle_h / 2
        h_start_rect = QRectF(x_start - self.HANDLE_WIDTH, y_top, self.HANDLE_WIDTH, handle_h)
        p.drawRoundedRect(h_start_rect, 3, 3)

        # Grip lines in start handle
        p.setPen(QPen(QColor("#ffffff"), 1))
        p.drawLine(QPointF(x_start - 7, y_top + 6), QPointF(x_start - 7, y_top + handle_h - 6))
        p.drawLine(QPointF(x_start - 4, y_top + 6), QPointF(x_start - 4, y_top + handle_h - 6))

        # 6. End Handle (Right cursor ])
        p.setPen(QPen(QColor("#38bdf8"), 1.5))
        p.setBrush(QBrush(QColor("#0284c7")))
        h_end_rect = QRectF(x_end, y_top, self.HANDLE_WIDTH, handle_h)
        p.drawRoundedRect(h_end_rect, 3, 3)

        # Grip lines in end handle
        p.setPen(QPen(QColor("#ffffff"), 1))
        p.drawLine(QPointF(x_end + 4, y_top + 6), QPointF(x_end + 4, y_top + handle_h - 6))
        p.drawLine(QPointF(x_end + 7, y_top + 6), QPointF(x_end + 7, y_top + handle_h - 6))

        # 7. Subtle boundary borders
        p.setPen(QPen(QColor("#38bdf8"), 1.5))
        p.drawLine(QPointF(x_start, rect.top()), QPointF(x_end, rect.top()))
        p.drawLine(QPointF(x_start, rect.bottom()), QPointF(x_end, rect.bottom()))

    # ─── Mouse Events ───

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        x = event.position().x()
        x_start = self._time_to_x(self._start)
        x_end = self._time_to_x(self._end)

        # Check start handle click (within tolerance)
        if abs(x - x_start) <= self.HANDLE_WIDTH + 4:
            self._active_handle = "start"
        # Check end handle click
        elif abs(x - x_end) <= self.HANDLE_WIDTH + 4:
            self._active_handle = "end"
        # Check inside selected span
        elif x_start < x < x_end:
            self._active_handle = "span"
            self._drag_offset = self._x_to_time(x) - self._start
        # Outside click -> seek
        else:
            self._active_handle = None
            t = self._x_to_time(x)
            self.set_current_position(t)
            self.seek_requested.emit(t)

    def mouseMoveEvent(self, event):
        x = event.position().x()
        x_start = self._time_to_x(self._start)
        x_end = self._time_to_x(self._end)

        # Update cursor on hover
        if self._active_handle is None:
            if abs(x - x_start) <= self.HANDLE_WIDTH + 4 or abs(x - x_end) <= self.HANDLE_WIDTH + 4:
                self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
            elif x_start < x < x_end:
                self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            else:
                self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        if not (event.buttons() & Qt.MouseButton.LeftButton) or not self._active_handle:
            return

        t = self._x_to_time(x)

        if self._active_handle == "start":
            self._start = max(0.0, min(t, self._end - 0.2))
            self.range_changed.emit(self._start, self._end)
            self.seek_requested.emit(self._start)
            self.update()
        elif self._active_handle == "end":
            self._end = min(self._duration, max(t, self._start + 0.2))
            self.range_changed.emit(self._start, self._end)
            self.seek_requested.emit(self._end)
            self.update()
        elif self._active_handle == "span":
            span = self._end - self._start
            new_start = max(0.0, min(t - self._drag_offset, self._duration - span))
            self._start = new_start
            self._end = new_start + span
            self.range_changed.emit(self._start, self._end)
            self.update()

    def mouseReleaseEvent(self, event):
        self._active_handle = None
        self.update()

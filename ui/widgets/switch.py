"""Custom iOS-style Bento Toggle Switch Widget for DubStudio PyQt6 Application."""
from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    pyqtProperty,
)
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QCheckBox, QWidget


class SwitchToggle(QCheckBox):
    """
    Sleek, animated iOS / HyperOS style toggle switch widget.
    Fully compatible with standard QCheckBox API (isChecked, setChecked, toggled).
    """

    def __init__(self, text: str = "", parent: QWidget | None = None, checked: bool = False):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Geometry metrics
        self._track_w = 40.0
        self._track_h = 22.0
        self._thumb_radius = 8.5
        self._thumb_margin = 2.5

        # Animation state: 0.0 (unchecked / left) to 1.0 (checked / right)
        self._progress = 1.0 if checked else 0.0
        self.setChecked(checked)

        self._anim = QPropertyAnimation(self, b"progress", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.OutQuad)

        self.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool):
        self._anim.stop()
        self._anim.setStartValue(self._progress)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    @pyqtProperty(float)
    def progress(self) -> float:
        return self._progress

    @progress.setter
    def progress(self, val: float):
        self._progress = max(0.0, min(1.0, val))
        self.update()

    def sizeHint(self) -> QSize:
        font = self.font()
        text = self.text()
        from PyQt6.QtGui import QFontMetrics
        fm = QFontMetrics(font)
        text_w = fm.horizontalAdvance(text) if text else 0
        total_w = int(self._track_w + (12 + text_w if text else 0))
        total_h = max(26, fm.height())
        return QSize(total_w, total_h)

    def hitButton(self, pos) -> bool:
        return self.rect().contains(pos)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        h = rect.height()
        track_y = (h - self._track_h) / 2.0
        track_rect = QRectF(0.0, track_y, self._track_w, self._track_h)

        # Interpolate track colors: Off (#222634) -> On (#0284c7)
        r = int(34 + (2 - 34) * self._progress)
        g = int(38 + (132 - 38) * self._progress)
        b = int(52 + (199 - 52) * self._progress)
        track_color = QColor(r, g, b)

        # Border color: Off (#2e3447) -> On (#38bdf8)
        br_r = int(46 + (56 - 46) * self._progress)
        br_g = int(52 + (189 - 52) * self._progress)
        br_b = int(71 + (248 - 71) * self._progress)
        border_color = QColor(br_r, br_g, br_b)

        # Draw track pill
        path = QPainterPath()
        path.addRoundedRect(track_rect, self._track_h / 2.0, self._track_h / 2.0)
        painter.fillPath(path, track_color)

        pen = QPen(border_color, 1.2)
        painter.setPen(pen)
        painter.drawPath(path)

        # Calculate thumb center position
        thumb_min_x = track_rect.left() + self._thumb_margin + self._thumb_radius
        thumb_max_x = track_rect.right() - self._thumb_margin - self._thumb_radius
        thumb_cx = thumb_min_x + (thumb_max_x - thumb_min_x) * self._progress
        thumb_cy = track_rect.center().y()

        # Thumb drop shadow
        shadow_rect = QRectF(
            thumb_cx - self._thumb_radius,
            thumb_cy - self._thumb_radius + 1.0,
            self._thumb_radius * 2.0,
            self._thumb_radius * 2.0,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 45))
        painter.drawEllipse(shadow_rect)

        # Thumb knob
        thumb_rect = QRectF(
            thumb_cx - self._thumb_radius,
            thumb_cy - self._thumb_radius,
            self._thumb_radius * 2.0,
            self._thumb_radius * 2.0,
        )
        painter.setBrush(QColor(255, 255, 255))
        painter.drawEllipse(thumb_rect)

        # Draw text label if present
        text = self.text()
        if text:
            painter.setFont(self.font())
            painter.setPen(QColor(241, 243, 247))
            text_rect = QRectF(
                self._track_w + 10.0,
                0.0,
                rect.width() - self._track_w - 10.0,
                float(h),
            )
            painter.drawText(
                text_rect,
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                text,
            )

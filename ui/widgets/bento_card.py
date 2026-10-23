"""HyperOS Bento Grid Card & Row Component for DubStudio PyQt6 Application."""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.icons import get_icon


class BentoCard(QFrame):
    """
    Sleek, minimalist Bento Grid Card container with rounded corners (16px),
    subtle dark glass depth, and an optional clean internal header (icon + title + action).
    """

    def __init__(
        self,
        title: str = "",
        icon_name: str = "",
        parent: QWidget | None = None,
        header_widget: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("bento_card")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        self._title = title
        self._icon_name = icon_name

        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(16, 16, 16, 16)
        self._main_layout.setSpacing(10)

        if self._title or self._icon_name or header_widget:
            hdr = QHBoxLayout()
            hdr.setSpacing(8)

            if self._icon_name:
                lbl_ic = QLabel()
                lbl_ic.setPixmap(get_icon(self._icon_name, "#38bdf8", "#38bdf8", 15).pixmap(15, 15))
                hdr.addWidget(lbl_ic)

            if self._title:
                lbl_t = QLabel(self._title)
                lbl_t.setStyleSheet(
                    "font-size: 13px; font-weight: 600; color: #f1f3f7; letter-spacing: 0.3px; background: transparent;"
                )
                hdr.addWidget(lbl_t)

            hdr.addStretch(1)

            if header_widget:
                hdr.addWidget(header_widget)

            self._main_layout.addLayout(hdr)

    def add_widget(self, widget: QWidget):
        """Add a child widget to this Bento Card."""
        self._main_layout.addWidget(widget)

    def add_layout(self, layout: QLayout):
        """Add a child layout to this Bento Card."""
        self._main_layout.addLayout(layout)

    def add_divider(self):
        """Add a thin minimalist horizontal divider line inside the card."""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Plain)
        line.setStyleSheet("border: none; border-top: 1px solid #1c2030; max-height: 1px; margin: 4px 0;")
        self._main_layout.addWidget(line)

    def content_layout(self) -> QVBoxLayout:
        """Access the card's internal layout directly."""
        return self._main_layout

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = 16.0

        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)

        # Base dark matte surface
        painter.fillPath(path, QColor(18, 20, 31))

        # Thin outer border
        border_pen = QPen(QColor(28, 32, 48), 1.0)
        painter.setPen(border_pen)
        painter.drawPath(path)

        # Subtle top-edge inner highlight line (Apple/HyperOS glass edge)
        top_line = QPainterPath()
        top_line.moveTo(rect.left() + radius, rect.top() + 1.0)
        top_line.lineTo(rect.right() - radius, rect.top() + 1.0)
        painter.setPen(QPen(QColor(42, 48, 70, 140), 1.0))
        painter.drawPath(top_line)


class BentoRow(QWidget):
    """
    A minimalist settings row inside a BentoCard:
    Left: Clean label (title)
    Right: Interactive control widget (SwitchToggle, ComboBox, etc.)
    """

    def __init__(
        self,
        label: str,
        control_widget: QWidget,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setFixedHeight(34)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        lbl = QLabel(label)
        lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #d1d5db; background: transparent;")
        layout.addWidget(lbl)
        layout.addStretch(1)

        layout.addWidget(control_widget)

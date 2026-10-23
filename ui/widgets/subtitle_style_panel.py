"""Interactive subtitle styling customization panel and overlay controls."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.icons import get_icon


class SubtitleStylePanel(QGroupBox):
    """
    Panel providing deep customization of subtitles:
    - Font family & Size
    - Primary text color & Outline width/color
    - Background box: Color, Opacity, Padding, Border radius, Blur
    - Alignment (Trái, Giữa, Phải)
    """
    style_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__("Tùy biến Phụ đề & Hộp nền", parent)
        self._current_style = {
            "font_name": "Arial",
            "font_size": 24,
            "primary_color": "#FFFFFF",
            "outline_color": "#000000",
            "outline_width": 2,
            "box_color": "rgba(0, 0, 0, 0.6)",
            "box_padding": 10,
            "box_radius": 8,
            "box_blur": 4,
            "text_align": "center",
        }
        self._setup_ui()

    def _setup_ui(self):
        grid = QGridLayout(self)
        grid.setContentsMargins(10, 12, 10, 10)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        # 1. Font Family & Size
        grid.addWidget(QLabel("Phông chữ:"), 0, 0)
        self._combo_font = QComboBox()
        self._combo_font.addItems(["Arial", "Segoe UI", "Tahoma", "Times New Roman", "Roboto", "Montserrat"])
        self._combo_font.currentTextChanged.connect(self._emit_change)
        grid.addWidget(self._combo_font, 0, 1)

        grid.addWidget(QLabel("Cỡ chữ:"), 0, 2)
        self._spin_size = QSpinBox()
        self._spin_size.setRange(12, 72)
        self._spin_size.setValue(24)
        self._spin_size.valueChanged.connect(self._emit_change)
        grid.addWidget(self._spin_size, 0, 3)

        # 2. Text Color & Outline
        grid.addWidget(QLabel("Màu chữ:"), 1, 0)
        self._btn_color = QPushButton(" Màu chữ")
        self._btn_color.setIcon(get_icon("palette", "#000000", "#000000", 14))
        self._btn_color.setStyleSheet("background-color: #FFFFFF; color: #000000; font-weight: bold;")
        self._btn_color.clicked.connect(self._pick_text_color)
        grid.addWidget(self._btn_color, 1, 1)

        grid.addWidget(QLabel("Viền chữ:"), 1, 2)
        self._spin_outline = QSpinBox()
        self._spin_outline.setRange(0, 10)
        self._spin_outline.setValue(2)
        self._spin_outline.valueChanged.connect(self._emit_change)
        grid.addWidget(self._spin_outline, 1, 3)

        # 3. Background Box: Radius & Padding
        grid.addWidget(QLabel("Bo góc nền:"), 2, 0)
        self._spin_radius = QSpinBox()
        self._spin_radius.setRange(0, 30)
        self._spin_radius.setValue(8)
        self._spin_radius.valueChanged.connect(self._emit_change)
        grid.addWidget(self._spin_radius, 2, 1)

        grid.addWidget(QLabel("Đệm khung:"), 2, 2)
        self._spin_padding = QSpinBox()
        self._spin_padding.setRange(0, 40)
        self._spin_padding.setValue(10)
        self._spin_padding.valueChanged.connect(self._emit_change)
        grid.addWidget(self._spin_padding, 2, 3)

        # 4. Box Opacity & Alignment
        grid.addWidget(QLabel("Độ mờ nền:"), 3, 0)
        self._slider_opacity = QSlider(Qt.Orientation.Horizontal)
        self._slider_opacity.setRange(0, 100)
        self._slider_opacity.setValue(60)
        self._slider_opacity.valueChanged.connect(self._emit_change)
        grid.addWidget(self._slider_opacity, 3, 1)

        grid.addWidget(QLabel("Căn lề:"), 3, 2)
        self._combo_align = QComboBox()
        self._combo_align.addItems(["Giữa (Center)", "Trái (Left)", "Phải (Right)"])
        self._combo_align.currentTextChanged.connect(self._emit_change)
        grid.addWidget(self._combo_align, 3, 3)

    def _pick_text_color(self):
        col = QColorDialog.getColor()
        if col.isValid():
            hex_col = col.name()
            self._current_style["primary_color"] = hex_col
            self._btn_color.setStyleSheet(f"background-color: {hex_col}; color: {'#000' if col.lightness() > 128 else '#fff'};")
            self._emit_change()

    def _emit_change(self):
        self._current_style["font_name"] = self._combo_font.currentText()
        self._current_style["font_size"] = self._spin_size.value()
        self._current_style["outline_width"] = self._spin_outline.value()
        self._current_style["box_radius"] = self._spin_radius.value()
        self._current_style["box_padding"] = self._spin_padding.value()
        opacity = self._slider_opacity.value() / 100.0
        self._current_style["box_color"] = f"rgba(0, 0, 0, {opacity:.2f})"
        align_text = self._combo_align.currentText()
        self._current_style["text_align"] = "left" if "Trái" in align_text else ("right" if "Phải" in align_text else "center")
        self.style_changed.emit(self._current_style)

    def get_style(self) -> dict:
        return self._current_style

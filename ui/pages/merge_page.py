"""Video Editor & Merge Page: Visual interactive Crop, Color Box overlay, Logo watermark, and Video Merging."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtGui import QColor, QImage, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ui.icons import get_icon
from ui.widgets.bento_card import BentoCard
from ui.widgets.range_slider import RangeSlider
from ui.widgets.switch import SwitchToggle
from ui.widgets.video_editor_overlay import VideoEditorOverlay
from ui.widgets.video_player import VideoPlayerWidget
from ui.workers import EditVideoWorker, MergeVideosWorker, StopTTSWorker, TrimVideoWorker


class ViewportOverlayFilter(QObject):
    """Event filter to ensure the interactive overlay stays perfectly aligned with the video viewport."""

    def __init__(self, overlay: VideoEditorOverlay, update_callback=None):
        super().__init__()
        self._overlay = overlay
        self._callback = update_callback

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self._overlay.setGeometry(obj.rect())
            self._overlay.raise_()
            self._overlay.update()
            if self._callback:
                self._callback()
        return False


class MergePage(QWidget):
    """
    Video Editor Page:
    - Tab 1: Video Editing Studio (Visual interactive preview + Crop, Color Box, Logo overlay)
    - Tab 2: Video Merging (Concatenate multiple clips)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers: List[any] = []
        self._edit_worker: Optional[EditVideoWorker] = None
        self._merge_worker: Optional[MergeVideosWorker] = None
        self._trim_worker: Optional[TrimVideoWorker] = None
        self._trim_video_path: str = ""
        self._is_previewing_cut: bool = False
        self._input_video_path: str = ""
        self._overlay_image_path: str = ""
        self._overlay_pixmap: Optional[QPixmap] = None
        self._video_w: int = 1280
        self._video_h: int = 720
        self._img_orig_w: int = 200
        self._img_orig_h: int = 200
        self._color_box_hex: str = "#000000"
        self._box_text_color_hex: str = "#FFFFFF"
        self._box_outline_color_hex: str = "#000000"
        self._combo_boxes: Optional[QComboBox] = None
        self._job_id: str = ""
        self._segments: List[dict] = []
        self._style: dict = {}
        self._subtitles_path: str = ""
        self._canvas_color: str = "#000000"

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        title = QLabel("CHỈNH SỬA VIDEO")
        title.setObjectName("section_title")
        main_layout.addWidget(title)

        tabs = QTabWidget()
        tabs.setObjectName("editor_tabs")

        # ─── Tab 1: Visual Editing Studio (Crop / Khối che / Logo) ───
        tab_edit = QWidget()
        self._setup_tab_edit(tab_edit)
        tabs.addTab(tab_edit, "  Chỉnh sửa")
        tabs.setTabIcon(0, get_icon("sliders", "#9ca3af", "#38bdf8", 16))

        # ─── Tab 2: Ghép nối video ───
        tab_merge = QWidget()
        self._setup_tab_merge(tab_merge)
        tabs.addTab(tab_merge, "  Ghép nối")
        tabs.setTabIcon(1, get_icon("link", "#9ca3af", "#38bdf8", 16))

        # ─── Tab 3: Cắt video ───
        tab_trim = QWidget()
        self._setup_tab_trim(tab_trim)
        tabs.addTab(tab_trim, "  Cắt video")
        tabs.setTabIcon(2, get_icon("scissors", "#9ca3af", "#38bdf8", 16))

        main_layout.addWidget(tabs, 1)

    # ─── Tab 1 Implementation (Split View: Visual Canvas + Parameter Controls) ──

    def _setup_tab_edit(self, parent: QWidget):
        split_layout = QHBoxLayout(parent)
        split_layout.setContentsMargins(4, 4, 4, 4)
        split_layout.setSpacing(12)

        # ── LEFT PANE: Interactive Video Preview Canvas ──
        left_box = QWidget()
        v_left = QVBoxLayout(left_box)
        v_left.setContentsMargins(0, 0, 0, 0)
        v_left.setSpacing(6)

        head_left = QHBoxLayout()
        lbl_preview_title = QLabel("Xem trước")
        lbl_preview_title.setStyleSheet("font-weight: 600; color: #38bdf8; font-size: 13px;")
        head_left.addWidget(lbl_preview_title)
        head_left.addStretch(1)

        # Minimal Status Pills
        self._lbl_pill_aspect = QLabel("Gốc")
        self._lbl_pill_aspect.setStyleSheet(
            "background: #14161f; color: #9ca3af; border: 1px solid #1e2230; border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: 500;"
        )
        head_left.addWidget(self._lbl_pill_aspect)

        self._lbl_pill_dim = QLabel("1280 × 720")
        self._lbl_pill_dim.setStyleSheet(
            "background: #14161f; color: #9ca3af; border: 1px solid #1e2230; border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: 500;"
        )
        head_left.addWidget(self._lbl_pill_dim)

        self._lbl_pill_bg = QLabel("")
        self._lbl_pill_bg.setVisible(False)
        self._lbl_pill_subs = QLabel("")
        self._lbl_pill_subs.setVisible(False)

        v_left.addLayout(head_left)

        # Embedded Video Player Widget
        self._video_player = VideoPlayerWidget(left_box)
        self._video_player.set_overlay_preview_visible(False)
        self._video_player.position_changed.connect(self._on_player_pos_changed)
        v_left.addWidget(self._video_player, 1)

        # Install Visual Interaction Overlay on top of the video player's viewport
        self._editor_overlay = VideoEditorOverlay(self._video_player._view.viewport())
        self._editor_overlay.set_video_dimensions(
            self._video_w, self._video_h, self._video_player._get_active_video_rect
        )

        # Event filter to keep overlay geometry synchronized with viewport resizing
        self._viewport_filter = ViewportOverlayFilter(
            self._editor_overlay,
            lambda: self._editor_overlay.set_video_dimensions(
                self._video_w, self._video_h, self._video_player._get_active_video_rect
            ),
        )
        self._video_player._view.viewport().installEventFilter(self._viewport_filter)

        # Connect overlay signals (screen drag/resize -> update controls in real time)
        self._editor_overlay.crop_changed.connect(self._on_overlay_crop_changed)
        self._editor_overlay.box_changed.connect(self._on_overlay_box_changed)
        self._editor_overlay.boxes_updated.connect(self._on_overlay_boxes_updated)
        self._editor_overlay.box_selected.connect(self._on_overlay_box_selected)
        self._editor_overlay.img_changed.connect(self._on_overlay_img_changed)

        split_layout.addWidget(left_box, 6)

        # ── RIGHT PANE: Scrollable Parameter Controls ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(12)

        # 1. Video Source Card
        card_src = BentoCard("Video nguồn", "film")

        h_proj = QHBoxLayout()
        h_proj.setSpacing(8)
        lbl_p = QLabel("Dự án:")
        lbl_p.setStyleSheet("font-size: 12px; font-weight: 500; color: #d1d5db;")
        h_proj.addWidget(lbl_p, 0, Qt.AlignmentFlag.AlignVCenter)

        self._combo_projects = QComboBox()
        self._combo_projects.setFixedHeight(34)
        self._combo_projects.addItem("-- Chọn từ dự án --", "")
        self._combo_projects.currentIndexChanged.connect(self._on_project_selected)
        h_proj.addWidget(self._combo_projects, 1, Qt.AlignmentFlag.AlignVCenter)

        btn_refresh = QPushButton()
        btn_refresh.setIcon(get_icon("refresh", "#9ca3af", "#38bdf8", 14))
        btn_refresh.setToolTip("Quét lại danh sách video dự án")
        btn_refresh.setFixedSize(34, 34)
        btn_refresh.setStyleSheet("border-radius: 8px;")
        btn_refresh.clicked.connect(self._refresh_project_videos)
        h_proj.addWidget(btn_refresh, 0, Qt.AlignmentFlag.AlignVCenter)
        card_src.add_layout(h_proj)

        h_src = QHBoxLayout()
        h_src.setSpacing(8)
        self._txt_src_video = QLineEdit()
        self._txt_src_video.setFixedHeight(34)
        self._txt_src_video.setPlaceholderText("Hoặc chọn tệp video từ máy tính (.mp4, .mkv, .avi...)")
        self._txt_src_video.textChanged.connect(self._on_src_video_changed)
        h_src.addWidget(self._txt_src_video, 1, Qt.AlignmentFlag.AlignVCenter)

        btn_browse_vid = QPushButton(" Duyệt tệp...")
        btn_browse_vid.setIcon(get_icon("folder", "#9ca3af", "#f0f2f5", 14))
        btn_browse_vid.setFixedHeight(34)
        btn_browse_vid.setStyleSheet("font-size: 12px; font-weight: 500; padding: 0 14px; border-radius: 8px;")
        btn_browse_vid.clicked.connect(self._browse_source_video)
        h_src.addWidget(btn_browse_vid, 0, Qt.AlignmentFlag.AlignVCenter)
        card_src.add_layout(h_src)

        self._lbl_video_dims = QLabel("Độ phân giải: Chưa tải")
        self._lbl_video_dims.setStyleSheet("color: #38bdf8; font-weight: 500;")
        card_src.add_widget(self._lbl_video_dims)
        layout.addWidget(card_src)

        # 2. Frame & Aspect Card
        card_frame = BentoCard("Khung hình & Tỉ lệ", "scissors")

        self._chk_enable_crop = SwitchToggle("Cắt khung hình (Crop)")
        self._chk_enable_crop.stateChanged.connect(self._sync_ui_to_overlay)
        card_frame.add_widget(self._chk_enable_crop)

        # Presets bar
        h_presets = QHBoxLayout()
        h_presets.addWidget(QLabel("Tỉ lệ:"))
        for name, preset_key in [
            ("16:9", "16:9"),
            ("9:16", "9:16"),
            ("1:1", "1:1"),
            ("4:3", "4:3"),
            ("Toàn bộ", "full"),
        ]:
            b = QPushButton(name)
            b.setFixedHeight(24)
            b.clicked.connect(lambda _, pk=preset_key: self._apply_crop_preset(pk))
            h_presets.addWidget(b)
        h_presets.addStretch(1)
        card_frame.add_layout(h_presets)

        grid_crop = QGridLayout()
        grid_crop.addWidget(QLabel("X:"), 0, 0)
        self._spin_crop_x = QSpinBox()
        self._spin_crop_x.setRange(0, 7680)
        self._spin_crop_x.valueChanged.connect(self._sync_ui_to_overlay)
        grid_crop.addWidget(self._spin_crop_x, 0, 1)

        grid_crop.addWidget(QLabel("Y:"), 0, 2)
        self._spin_crop_y = QSpinBox()
        self._spin_crop_y.setRange(0, 4320)
        self._spin_crop_y.valueChanged.connect(self._sync_ui_to_overlay)
        grid_crop.addWidget(self._spin_crop_y, 0, 3)

        grid_crop.addWidget(QLabel("Rộng:"), 1, 0)
        self._spin_crop_w = QSpinBox()
        self._spin_crop_w.setRange(10, 7680)
        self._spin_crop_w.setValue(1280)
        self._spin_crop_w.valueChanged.connect(self._sync_ui_to_overlay)
        grid_crop.addWidget(self._spin_crop_w, 1, 1)

        grid_crop.addWidget(QLabel("Cao:"), 1, 2)
        self._spin_crop_h = QSpinBox()
        self._spin_crop_h.setRange(10, 4320)
        self._spin_crop_h.setValue(720)
        self._spin_crop_h.valueChanged.connect(self._sync_ui_to_overlay)
        grid_crop.addWidget(self._spin_crop_h, 1, 3)
        card_frame.add_layout(grid_crop)

        card_frame.add_divider()

        self._chk_enable_scale = SwitchToggle("Mở rộng tỉ lệ nền")
        self._chk_enable_scale.stateChanged.connect(self._on_scale_config_changed)
        card_frame.add_widget(self._chk_enable_scale)

        h_scale_controls = QHBoxLayout()
        h_scale_controls.addWidget(QLabel("Tỉ lệ:"))
        self._combo_aspect = QComboBox()
        self._combo_aspect.addItem("Gốc", "original")
        self._combo_aspect.addItem("9:16", "9:16")
        self._combo_aspect.addItem("16:9", "16:9")
        self._combo_aspect.addItem("1:1", "1:1")
        self._combo_aspect.addItem("4:5", "4:5")
        self._combo_aspect.addItem("4:3", "4:3")
        self._combo_aspect.setMinimumWidth(120)
        self._combo_aspect.currentIndexChanged.connect(self._on_scale_config_changed)
        h_scale_controls.addWidget(self._combo_aspect, 1)

        h_scale_controls.addWidget(QLabel("Màu nền:"))
        self._btn_canvas_color = QPushButton("  Đen")
        self._btn_canvas_color.setFixedHeight(28)
        self._btn_canvas_color.setStyleSheet("background-color: #000000; color: #FFFFFF; font-weight: bold; border: 1px solid #374151; border-radius: 4px; padding: 0 10px;")
        self._btn_canvas_color.clicked.connect(self._pick_canvas_color)
        h_scale_controls.addWidget(self._btn_canvas_color)
        card_frame.add_layout(h_scale_controls)

        layout.addWidget(card_frame)

        # 3. Overlays & Export Card
        card_overlay = BentoCard("Lớp phủ & Xuất video", "layers")

        # Multi-box management row
        h_box_mgmt = QHBoxLayout()
        h_box_mgmt.setSpacing(8)
        lbl_box = QLabel("Khối:")
        lbl_box.setStyleSheet("font-size: 12px; font-weight: 500; color: #d1d5db;")
        h_box_mgmt.addWidget(lbl_box, 0, Qt.AlignmentFlag.AlignVCenter)

        self._combo_boxes = QComboBox()
        self._combo_boxes.setFixedHeight(32)
        self._combo_boxes.currentIndexChanged.connect(self._on_box_combo_changed)
        h_box_mgmt.addWidget(self._combo_boxes, 1, Qt.AlignmentFlag.AlignVCenter)

        self._btn_add_box = QPushButton(" Thêm")
        self._btn_add_box.setIcon(get_icon("plus", "#9ca3af", "#22c55e", 14))
        self._btn_add_box.setToolTip("Thêm một khối màu che mới")
        self._btn_add_box.setFixedHeight(32)
        self._btn_add_box.setStyleSheet("border-radius: 8px; font-size: 12px; font-weight: 500; padding: 0 12px;")
        self._btn_add_box.clicked.connect(self._on_add_box_clicked)
        h_box_mgmt.addWidget(self._btn_add_box, 0, Qt.AlignmentFlag.AlignVCenter)

        self._btn_del_box = QPushButton(" Xóa")
        self._btn_del_box.setIcon(get_icon("trash", "#9ca3af", "#ef4444", 14))
        self._btn_del_box.setToolTip("Xóa khối màu đang chọn")
        self._btn_del_box.setFixedHeight(32)
        self._btn_del_box.setStyleSheet("border-radius: 8px; font-size: 12px; font-weight: 500; padding: 0 12px;")
        self._btn_del_box.clicked.connect(self._on_delete_box_clicked)
        h_box_mgmt.addWidget(self._btn_del_box, 0, Qt.AlignmentFlag.AlignVCenter)
        card_overlay.add_layout(h_box_mgmt)

        # Container for box parameter adjustments
        self._box_controls_container = QWidget()
        grid_box = QGridLayout(self._box_controls_container)
        grid_box.setContentsMargins(0, 4, 0, 4)
        grid_box.setSpacing(6)
        grid_box.addWidget(QLabel("X:"), 0, 0)
        self._spin_box_x = QSpinBox()
        self._spin_box_x.setRange(0, 7680)
        self._spin_box_x.valueChanged.connect(self._sync_ui_to_overlay)
        grid_box.addWidget(self._spin_box_x, 0, 1)

        grid_box.addWidget(QLabel("Y:"), 0, 2)
        self._spin_box_y = QSpinBox()
        self._spin_box_y.setRange(0, 4320)
        self._spin_box_y.setValue(580)
        self._spin_box_y.valueChanged.connect(self._sync_ui_to_overlay)
        grid_box.addWidget(self._spin_box_y, 0, 3)

        grid_box.addWidget(QLabel("Rộng:"), 1, 0)
        self._spin_box_w = QSpinBox()
        self._spin_box_w.setRange(10, 7680)
        self._spin_box_w.setValue(1280)
        self._spin_box_w.valueChanged.connect(self._sync_ui_to_overlay)
        grid_box.addWidget(self._spin_box_w, 1, 1)

        grid_box.addWidget(QLabel("Cao:"), 1, 2)
        self._spin_box_h = QSpinBox()
        self._spin_box_h.setRange(10, 4320)
        self._spin_box_h.setValue(120)
        self._spin_box_h.valueChanged.connect(self._sync_ui_to_overlay)
        grid_box.addWidget(self._spin_box_h, 1, 3)

        grid_box.addWidget(QLabel("Màu:"), 2, 0)
        self._btn_box_color = QPushButton(" Chọn màu")
        self._btn_box_color.setIcon(get_icon("palette", "#ffffff", "#ffffff", 14))
        self._btn_box_color.setStyleSheet(f"background-color: {self._color_box_hex}; color: #FFFFFF; font-weight: bold;")
        self._btn_box_color.clicked.connect(self._pick_box_color)
        grid_box.addWidget(self._btn_box_color, 2, 1)

        grid_box.addWidget(QLabel("Độ mờ:"), 2, 2)
        h_op = QHBoxLayout()
        self._slider_box_opacity = QSlider(Qt.Orientation.Horizontal)
        self._slider_box_opacity.setRange(0, 100)
        self._slider_box_opacity.setValue(80)
        self._slider_box_opacity.valueChanged.connect(self._on_opacity_slider_changed)
        h_op.addWidget(self._slider_box_opacity, 1)
        self._lbl_box_op_val = QLabel("80%")
        self._lbl_box_op_val.setFixedWidth(36)
        h_op.addWidget(self._lbl_box_op_val)
        grid_box.addLayout(h_op, 2, 3)

        grid_box.addWidget(QLabel("Bo góc:"), 3, 0)
        h_rad = QHBoxLayout()
        self._slider_box_radius = QSlider(Qt.Orientation.Horizontal)
        self._slider_box_radius.setRange(0, 40)
        self._slider_box_radius.setValue(8)
        self._slider_box_radius.valueChanged.connect(self._on_radius_slider_changed)
        h_rad.addWidget(self._slider_box_radius, 1)
        self._lbl_box_rad_val = QLabel("8px")
        self._lbl_box_rad_val.setFixedWidth(36)
        h_rad.addWidget(self._lbl_box_rad_val)
        grid_box.addLayout(h_rad, 3, 1)

        grid_box.addWidget(QLabel("Xoay:"), 3, 2)
        h_rot = QHBoxLayout()
        self._slider_box_rotation = QSlider(Qt.Orientation.Horizontal)
        self._slider_box_rotation.setRange(-180, 180)
        self._slider_box_rotation.setValue(0)
        self._slider_box_rotation.valueChanged.connect(self._on_rotation_slider_changed)
        h_rot.addWidget(self._slider_box_rotation, 1)
        self._lbl_box_rot_val = QLabel("0°")
        self._lbl_box_rot_val.setFixedWidth(36)
        h_rot.addWidget(self._lbl_box_rot_val)
        grid_box.addLayout(h_rot, 3, 3)

        # Text inside box
        grid_box.addWidget(QLabel("Chữ:"), 4, 0)
        self._txt_box_text = QLineEdit()
        self._txt_box_text.setPlaceholderText("Gõ chữ để biến khối này thành chữ...")
        self._txt_box_text.textChanged.connect(self._sync_ui_to_overlay)
        grid_box.addWidget(self._txt_box_text, 4, 1, 1, 3)

        grid_box.addWidget(QLabel("Phông:"), 5, 0)
        self._combo_box_font = QComboBox()
        self._combo_box_font.addItems(["Arial", "Segoe UI", "Tahoma", "Times New Roman", "Calibri", "Verdana"])
        self._combo_box_font.currentIndexChanged.connect(self._sync_ui_to_overlay)
        grid_box.addWidget(self._combo_box_font, 5, 1)

        grid_box.addWidget(QLabel("Cỡ chữ:"), 5, 2)
        self._spin_box_font_size = QSpinBox()
        self._spin_box_font_size.setRange(8, 120)
        self._spin_box_font_size.setValue(24)
        self._spin_box_font_size.valueChanged.connect(self._sync_ui_to_overlay)
        grid_box.addWidget(self._spin_box_font_size, 5, 3)

        grid_box.addWidget(QLabel("Màu chữ:"), 6, 0)
        self._btn_box_text_color = QPushButton(" Màu chữ")
        self._btn_box_text_color.setIcon(get_icon("palette", "#ffffff", "#ffffff", 14))
        self._btn_box_text_color.setStyleSheet(f"background-color: {self._box_text_color_hex}; color: #000000; font-weight: bold;")
        self._btn_box_text_color.clicked.connect(self._pick_box_text_color)
        grid_box.addWidget(self._btn_box_text_color, 6, 1)

        grid_box.addWidget(QLabel("Viền chữ:"), 6, 2)
        self._btn_box_outline_color = QPushButton(" Màu viền")
        self._btn_box_outline_color.setIcon(get_icon("palette", "#ffffff", "#ffffff", 14))
        self._btn_box_outline_color.setStyleSheet(f"background-color: {self._box_outline_color_hex}; color: #FFFFFF; font-weight: bold;")
        self._btn_box_outline_color.clicked.connect(self._pick_box_outline_color)
        grid_box.addWidget(self._btn_box_outline_color, 6, 3)

        grid_box.addWidget(QLabel("Độ dày viền:"), 7, 0)
        self._spin_box_outline_width = QSpinBox()
        self._spin_box_outline_width.setRange(0, 10)
        self._spin_box_outline_width.setValue(2)
        self._spin_box_outline_width.valueChanged.connect(self._sync_ui_to_overlay)
        grid_box.addWidget(self._spin_box_outline_width, 7, 1)

        card_overlay.add_widget(self._box_controls_container)

        card_overlay.add_divider()

        # Logo Sub-section
        self._chk_enable_img = SwitchToggle("Kích hoạt logo")
        self._chk_enable_img.stateChanged.connect(self._sync_ui_to_overlay)
        card_overlay.add_widget(self._chk_enable_img)

        h_img_pick = QHBoxLayout()
        self._txt_img_path = QLineEdit()
        self._txt_img_path.setPlaceholderText("Chọn file ảnh (.png, .jpg...)")
        h_img_pick.addWidget(self._txt_img_path, 1)

        btn_browse_img = QPushButton(" Chọn ảnh...")
        btn_browse_img.setIcon(get_icon("image", "#9ca3af", "#f0f2f5", 14))
        btn_browse_img.clicked.connect(self._browse_overlay_image)
        h_img_pick.addWidget(btn_browse_img)
        card_overlay.add_layout(h_img_pick)

        # Quick corner placement buttons
        h_corners = QHBoxLayout()
        h_corners.addWidget(QLabel("Vị trí:"))
        for name, corner_key in [
            ("Trên-Trái", "tl"),
            ("Trên-Phải", "tr"),
            ("Dưới-Trái", "bl"),
            ("Dưới-Phải", "br"),
        ]:
            b = QPushButton(name)
            b.setFixedHeight(24)
            b.clicked.connect(lambda _, ck=corner_key: self._apply_logo_corner(ck))
            h_corners.addWidget(b)
        h_corners.addStretch(1)
        card_overlay.add_layout(h_corners)

        grid_img = QGridLayout()
        grid_img.addWidget(QLabel("X:"), 0, 0)
        self._spin_img_x = QSpinBox()
        self._spin_img_x.setRange(0, 7680)
        self._spin_img_x.setValue(20)
        self._spin_img_x.valueChanged.connect(self._sync_ui_to_overlay)
        grid_img.addWidget(self._spin_img_x, 0, 1)

        grid_img.addWidget(QLabel("Y:"), 0, 2)
        self._spin_img_y = QSpinBox()
        self._spin_img_y.setRange(0, 4320)
        self._spin_img_y.setValue(20)
        self._spin_img_y.valueChanged.connect(self._sync_ui_to_overlay)
        grid_img.addWidget(self._spin_img_y, 0, 3)

        grid_img.addWidget(QLabel("Rộng:"), 1, 0)
        self._spin_img_w = QSpinBox()
        self._spin_img_w.setRange(10, 7680)
        self._spin_img_w.setValue(180)
        self._spin_img_w.valueChanged.connect(self._on_img_w_changed)
        grid_img.addWidget(self._spin_img_w, 1, 1)

        grid_img.addWidget(QLabel("Cao:"), 1, 2)
        self._spin_img_h = QSpinBox()
        self._spin_img_h.setRange(10, 4320)
        self._spin_img_h.setValue(180)
        self._spin_img_h.valueChanged.connect(self._sync_ui_to_overlay)
        grid_img.addWidget(self._spin_img_h, 1, 3)

        self._chk_fix_scale = SwitchToggle("Khóa tỉ lệ", checked=True)
        self._chk_fix_scale.stateChanged.connect(self._sync_ui_to_overlay)
        grid_img.addWidget(self._chk_fix_scale, 2, 0, 1, 4)

        card_overlay.add_layout(grid_img)

        card_overlay.add_divider()

        # Output Execution Sub-section
        self._chk_subtitles = SwitchToggle("Nhúng phụ đề tiếng Việt", checked=True)
        self._chk_subtitles.toggled.connect(self._on_subtitles_toggled)
        card_overlay.add_widget(self._chk_subtitles)

        h_out_name = QHBoxLayout()
        h_out_name.addWidget(QLabel("Tên tệp:"))
        self._txt_edit_out_name = QLineEdit("edited_video.mp4")
        h_out_name.addWidget(self._txt_edit_out_name, 1)
        card_overlay.add_layout(h_out_name)

        h_out_dir = QHBoxLayout()
        h_out_dir.addWidget(QLabel("Thư mục:"))
        from dubstudio.paths import get_out_dir
        self._lbl_edit_out_dir = QLabel(str(get_out_dir()))
        self._lbl_edit_out_dir.setStyleSheet("color: #9ca3af; font-size: 11px;")
        self._lbl_edit_out_dir.setWordWrap(True)
        h_out_dir.addWidget(self._lbl_edit_out_dir, 1)

        btn_change_out = QPushButton()
        btn_change_out.setIcon(get_icon("folder", "#9ca3af", "#f0f2f5", 13))
        btn_change_out.setToolTip("Đổi thư mục lưu video")
        btn_change_out.setFixedSize(28, 28)
        btn_change_out.clicked.connect(self._change_output_folder)
        h_out_dir.addWidget(btn_change_out)
        card_overlay.add_layout(h_out_dir)

        self._btn_run_edit = QPushButton(" Xuất video")
        self._btn_run_edit.setIcon(get_icon("play", "#ffffff", "#ffffff", 14))
        self._btn_run_edit.setObjectName("primary")
        self._btn_run_edit.setFixedHeight(36)
        self._btn_run_edit.clicked.connect(self._start_edit_video)
        card_overlay.add_widget(self._btn_run_edit)

        self._progress_edit = QProgressBar()
        self._progress_edit.setVisible(False)
        self._progress_edit.setRange(0, 0)
        card_overlay.add_widget(self._progress_edit)

        self._lbl_edit_status = QLabel("")
        self._lbl_edit_status.setStyleSheet("color: #4f9cf9; font-size: 12px;")
        card_overlay.add_widget(self._lbl_edit_status)

        layout.addWidget(card_overlay)
        layout.addStretch(1)

        scroll.setWidget(container)
        split_layout.addWidget(scroll, 5)

        self._refresh_project_videos()
        self._refresh_box_combo()

    # ─── Two-Way Synchronization (Screen <-> Controls) ───────────────────────

    def _sync_ui_to_overlay(self):
        """Push spinbox/slider values to the on-screen visual overlay."""
        if not hasattr(self, "_editor_overlay") or not self._editor_overlay:
            return

        # 1. Crop
        self._editor_overlay.set_crop_params(
            self._chk_enable_crop.isChecked(),
            self._spin_crop_x.value(),
            self._spin_crop_y.value(),
            self._spin_crop_w.value(),
            self._spin_crop_h.value(),
        )

        # 2. Box
        if self._editor_overlay.get_boxes():
            self._editor_overlay.set_box_params(
                True,
                self._spin_box_x.value(),
                self._spin_box_y.value(),
                self._spin_box_w.value(),
                self._spin_box_h.value(),
                self._color_box_hex,
                self._slider_box_opacity.value() / 100.0,
                self._slider_box_radius.value(),
                float(self._slider_box_rotation.value()) if hasattr(self, "_slider_box_rotation") else 0.0,
                self._txt_box_text.text() if hasattr(self, "_txt_box_text") else "",
                self._combo_box_font.currentText() if hasattr(self, "_combo_box_font") else "Arial",
                self._spin_box_font_size.value() if hasattr(self, "_spin_box_font_size") else 24,
                getattr(self, "_box_text_color_hex", "#FFFFFF"),
                getattr(self, "_box_outline_color_hex", "#000000"),
                self._spin_box_outline_width.value() if hasattr(self, "_spin_box_outline_width") else 2,
            )

        # 3. Logo
        self._editor_overlay.set_img_params(
            self._chk_enable_img.isChecked(),
            self._spin_img_x.value(),
            self._spin_img_y.value(),
            self._spin_img_w.value(),
            self._spin_img_h.value(),
            self._overlay_pixmap,
            self._chk_fix_scale.isChecked(),
        )

    def _on_overlay_crop_changed(self, x: int, y: int, w: int, h: int):
        """User dragged or resized crop box directly on screen -> update spinboxes."""
        self._chk_enable_crop.setChecked(True)
        for spin, val in [
            (self._spin_crop_x, x),
            (self._spin_crop_y, y),
            (self._spin_crop_w, w),
            (self._spin_crop_h, h),
        ]:
            spin.blockSignals(True)
            spin.setValue(val)
            spin.blockSignals(False)

    def _on_overlay_box_changed(self, x: int, y: int, w: int, h: int):
        """User dragged or resized color box directly on screen -> update spinboxes."""
        for spin, val in [
            (self._spin_box_x, x),
            (self._spin_box_y, y),
            (self._spin_box_w, w),
            (self._spin_box_h, h),
        ]:
            spin.blockSignals(True)
            spin.setValue(val)
            spin.blockSignals(False)

    def _on_add_box_clicked(self):
        new_idx = self._editor_overlay.add_box()
        self._refresh_box_combo(select_idx=new_idx)

    def _on_delete_box_clicked(self):
        new_idx = self._editor_overlay.delete_selected_box()
        self._refresh_box_combo(select_idx=new_idx)

    def _refresh_box_combo(self, select_idx: int = 0):
        if not self._combo_boxes:
            return
        boxes = self._editor_overlay.get_boxes()
        self._combo_boxes.blockSignals(True)
        self._combo_boxes.clear()
        if not boxes:
            self._combo_boxes.addItem("Chưa có khối che")
            self._combo_boxes.setEnabled(False)
            if hasattr(self, "_btn_del_box"):
                self._btn_del_box.setEnabled(False)
            if hasattr(self, "_box_controls_container"):
                self._box_controls_container.setEnabled(False)
        else:
            self._combo_boxes.setEnabled(True)
            if hasattr(self, "_btn_del_box"):
                self._btn_del_box.setEnabled(True)
            if hasattr(self, "_box_controls_container"):
                self._box_controls_container.setEnabled(True)
            for i, b in enumerate(boxes):
                txt = str(b.get("text", "") or "").strip()
                name = f"Khối #{i + 1}"
                if txt:
                    name += f": {txt[:8]}.." if len(txt) > 8 else f": {txt}"
                self._combo_boxes.addItem(name)
            if 0 <= select_idx < len(boxes):
                self._combo_boxes.setCurrentIndex(select_idx)
        self._combo_boxes.blockSignals(False)
        self._load_selected_box_into_ui()

    def _on_box_combo_changed(self, idx: int):
        if idx >= 0:
            self._editor_overlay.set_selected_box_idx(idx)
            self._load_selected_box_into_ui()

    def _on_overlay_box_selected(self, idx: int):
        if self._combo_boxes and 0 <= idx < self._combo_boxes.count():
            self._combo_boxes.blockSignals(True)
            self._combo_boxes.setCurrentIndex(idx)
            self._combo_boxes.blockSignals(False)
        self._load_selected_box_into_ui()

    def _on_overlay_boxes_updated(self, boxes: list):
        if self._combo_boxes:
            cur_idx = self._editor_overlay._selected_box_idx
            self._refresh_box_combo(select_idx=cur_idx)

    def _load_selected_box_into_ui(self):
        b = self._editor_overlay.get_selected_box()
        if not b:
            if hasattr(self, "_box_controls_container"):
                self._box_controls_container.setEnabled(False)
            return
        if hasattr(self, "_box_controls_container"):
            self._box_controls_container.setEnabled(True)

        for spin, key in [
            (self._spin_box_x, "x"),
            (self._spin_box_y, "y"),
            (self._spin_box_w, "w"),
            (self._spin_box_h, "h"),
        ]:
            spin.blockSignals(True)
            spin.setValue(int(b.get(key, 0)))
            spin.blockSignals(False)

        self._color_box_hex = b.get("color", "#000000")
        self._btn_box_color.setStyleSheet(
            f"background-color: {self._color_box_hex}; color: #FFFFFF; font-weight: bold;"
        )

        op = int(round(float(b.get("opacity", 0.8)) * 100))
        self._slider_box_opacity.blockSignals(True)
        self._slider_box_opacity.setValue(op)
        self._slider_box_opacity.blockSignals(False)
        self._lbl_box_op_val.setText(f"{op}%")

        rad = int(b.get("radius", 8))
        self._slider_box_radius.blockSignals(True)
        self._slider_box_radius.setValue(rad)
        self._slider_box_radius.blockSignals(False)
        self._lbl_box_rad_val.setText(f"{rad}px")

        rot = int(round(float(b.get("rotation", 0.0) or 0.0)))
        if hasattr(self, "_slider_box_rotation"):
            self._slider_box_rotation.blockSignals(True)
            self._slider_box_rotation.setValue(rot)
            self._slider_box_rotation.blockSignals(False)
            self._lbl_box_rot_val.setText(f"{rot}°")

        if hasattr(self, "_txt_box_text"):
            self._txt_box_text.blockSignals(True)
            self._txt_box_text.setText(str(b.get("text", "") or ""))
            self._txt_box_text.blockSignals(False)

        if hasattr(self, "_combo_box_font"):
            f_name = b.get("font_name", "Arial")
            idx = self._combo_box_font.findText(f_name)
            if idx >= 0:
                self._combo_box_font.blockSignals(True)
                self._combo_box_font.setCurrentIndex(idx)
                self._combo_box_font.blockSignals(False)

        if hasattr(self, "_spin_box_font_size"):
            self._spin_box_font_size.blockSignals(True)
            self._spin_box_font_size.setValue(int(b.get("font_size", 24) or 24))
            self._spin_box_font_size.blockSignals(False)

        self._box_text_color_hex = b.get("text_color", "#FFFFFF")
        if hasattr(self, "_btn_box_text_color"):
            self._btn_box_text_color.setStyleSheet(f"background-color: {self._box_text_color_hex}; color: #000000; font-weight: bold;")

        self._box_outline_color_hex = b.get("text_outline_color", "#000000")
        if hasattr(self, "_btn_box_outline_color"):
            self._btn_box_outline_color.setStyleSheet(f"background-color: {self._box_outline_color_hex}; color: #FFFFFF; font-weight: bold;")

        if hasattr(self, "_spin_box_outline_width"):
            self._spin_box_outline_width.blockSignals(True)
            self._spin_box_outline_width.setValue(int(b.get("text_outline_width", 2) or 2))
            self._spin_box_outline_width.blockSignals(False)

    def _on_rotation_slider_changed(self, v: int):
        self._lbl_box_rot_val.setText(f"{v}°")
        self._sync_ui_to_overlay()

    def _pick_box_text_color(self):
        c = QColorDialog.getColor(QColor(getattr(self, "_box_text_color_hex", "#FFFFFF")), self, "Chọn màu chữ")
        if c.isValid():
            self._box_text_color_hex = c.name().upper()
            self._btn_box_text_color.setStyleSheet(f"background-color: {self._box_text_color_hex}; color: #000000; font-weight: bold;")
            self._sync_ui_to_overlay()

    def _pick_box_outline_color(self):
        c = QColorDialog.getColor(QColor(getattr(self, "_box_outline_color_hex", "#000000")), self, "Chọn màu viền chữ")
        if c.isValid():
            self._box_outline_color_hex = c.name().upper()
            self._btn_box_outline_color.setStyleSheet(f"background-color: {self._box_outline_color_hex}; color: #FFFFFF; font-weight: bold;")
            self._sync_ui_to_overlay()

    def _on_overlay_img_changed(self, x: int, y: int, w: int, h: int):
        """User dragged or resized logo image directly on screen -> update spinboxes."""
        self._chk_enable_img.setChecked(True)
        for spin, val in [
            (self._spin_img_x, x),
            (self._spin_img_y, y),
            (self._spin_img_w, w),
            (self._spin_img_h, h),
        ]:
            spin.blockSignals(True)
            spin.setValue(val)
            spin.blockSignals(False)

    def _on_opacity_slider_changed(self, v: int):
        self._lbl_box_op_val.setText(f"{v}%")
        self._sync_ui_to_overlay()

    def _on_radius_slider_changed(self, v: int):
        self._lbl_box_rad_val.setText(f"{v}px")
        self._sync_ui_to_overlay()

    # ─── Video Loading & Project Selection ───────────────────────────────────

    def _refresh_project_videos(self):
        """Scan workspace and out folders for available videos."""
        self._combo_projects.blockSignals(True)
        self._combo_projects.clear()
        self._combo_projects.addItem("-- Chọn video từ dự án studio --", "")

        found: List[tuple[str, dict]] = []

        # Out rendered videos
        from dubstudio.paths import get_out_dir, get_workspace_dir, resolve_job_workspace, open_in_file_manager
        out_dir = get_out_dir()
        if out_dir.exists():
            for f in out_dir.glob("*_vi.mp4"):
                j_id = f.stem.replace("_vi", "")
                found.append((f"Xuất phẩm: {f.name}", {"path": str(f.resolve()), "job_id": j_id}))

        # Workspace inputs
        ws_dir = get_workspace_dir()
        if ws_dir.exists():
            for j_dir in ws_dir.iterdir():
                if j_dir.is_dir():
                    prev = j_dir / "preview_dubbed.mp4"
                    inp = j_dir / "input.mp4"
                    if prev.exists():
                        found.append((f"Dự án {j_dir.name} (Lồng tiếng)", {"path": str(prev.resolve()), "job_id": j_dir.name}))
                    elif inp.exists():
                        found.append((f"Dự án {j_dir.name} (Gốc)", {"path": str(inp.resolve()), "job_id": j_dir.name}))

        # Samples
        samples_dir = Path("samples")
        if samples_dir.exists():
            for f in samples_dir.glob("*.mp4"):
                found.append((f"Mẫu: {f.name}", {"path": str(f.resolve()), "job_id": ""}))

        for label, item in found:
            self._combo_projects.addItem(label, item)

        self._combo_projects.blockSignals(False)

    def _on_project_selected(self, idx: int):
        data = self._combo_projects.currentData()
        if not data:
            return
        if isinstance(data, dict):
            path = data.get("path", "")
            job_id = data.get("job_id", "")
        else:
            path = str(data)
            job_id = ""

        if path and Path(path).exists():
            self._job_id = job_id
            self._txt_src_video.setText(path)
            if self._job_id:
                if hasattr(self, "_txt_edit_out_name"):
                    self._txt_edit_out_name.setText(f"{self._job_id}.mp4")
                self._load_project_subtitles(self._job_id)
            else:
                self._clear_subtitles()

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_project_videos()
        if hasattr(self, "_lbl_edit_out_dir"):
            from dubstudio.paths import get_out_dir
            self._lbl_edit_out_dir.setText(str(get_out_dir()))
        if hasattr(self, "_video_player") and self._video_player:
            self._video_player.set_overlay_draggable(False)
        if hasattr(self, "_editor_overlay") and self._video_player:
            self._editor_overlay.setGeometry(self._video_player._view.viewport().rect())
            self._editor_overlay.raise_()
            self._editor_overlay.update()

    def _change_output_folder(self):
        """Allow user to select custom export directory and persist."""
        from dubstudio.paths import get_out_dir
        new_d = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu video xuất", str(get_out_dir()))
        if new_d:
            os.environ["DUBSTUDIO_OUT_DIR"] = new_d
            if hasattr(self, "_lbl_edit_out_dir"):
                self._lbl_edit_out_dir.setText(new_d)

    def load_project_data(self, job_id: str, video_path: str, style: Optional[dict] = None, segments: Optional[list] = None):
        """Seamlessly transition from Subtitle tab into Merge/Export page with 1:1 live preview."""
        if job_id:
            self._job_id = job_id
            if hasattr(self, "_txt_edit_out_name"):
                self._txt_edit_out_name.setText(f"{job_id}.mp4")

        if style:
            self._style = dict(style)
        if segments:
            self._segments = list(segments)

        if hasattr(self, "_txt_src_video") and video_path:
            self._txt_src_video.setText(video_path)

        if self._job_id and (not style or not segments):
            self._load_project_subtitles(self._job_id)

        if hasattr(self, "_chk_subtitles"):
            self._chk_subtitles.blockSignals(True)
            self._chk_subtitles.setEnabled(True)
            self._chk_subtitles.setChecked(True)
            self._chk_subtitles.setText(f"Nhúng phụ đề tiếng Việt (Dự án: {job_id})")
            self._chk_subtitles.blockSignals(False)

        # Configure player
        if hasattr(self, "_video_player") and self._video_player:
            self._video_player.set_overlay_draggable(False)
            self._video_player.set_overlay_preview_visible(True)

            # Setup multi-track audio for preview if video loaded
            if self._job_id:
                from dubstudio.paths import resolve_job_workspace
                ws_dir = resolve_job_workspace(self._job_id)
                self._video_player.setup_job_audio(workspace_dir=ws_dir)

            self._on_player_pos_changed(self._video_player.get_position())

        self._on_scale_config_changed()

    def load_video_path(self, path_str: str, job_id: str = ""):
        """Load video path passed from previous workflow tabs."""
        if job_id:
            self._job_id = job_id
            if hasattr(self, "_txt_edit_out_name"):
                self._txt_edit_out_name.setText(f"{job_id}.mp4")
        if hasattr(self, "_txt_src_video") and path_str:
            self._txt_src_video.setText(path_str)
        if self._job_id:
            self._load_project_subtitles(self._job_id)
        if hasattr(self, "_video_player") and self._video_player:
            self._video_player.set_overlay_draggable(False)
        self._on_scale_config_changed()

    def _load_project_subtitles(self, job_id: str):
        """Load subtitles and styling from project workspace to enable 1:1 live preview and export."""
        from dubstudio.paths import resolve_job_workspace, get_out_dir
        ws_job = resolve_job_workspace(job_id)
        seg_file = ws_job / "segments.json"
        if not seg_file.exists():
            seg_file = ws_job / "raw_segments.json"
        style_file = ws_job / "style.json"
        ass_file = ws_job / "subtitles.ass"
        if not ass_file.exists():
            out_ass = get_out_dir() / f"{job_id}_vi.ass"
            if out_ass.exists():
                ass_file = out_ass

        self._segments = []
        if seg_file.exists():
            try:
                raw_segs = json.loads(seg_file.read_text(encoding="utf-8"))
                if isinstance(raw_segs, dict):
                    self._segments = raw_segs.get("segments", [])
                elif isinstance(raw_segs, list):
                    self._segments = raw_segs
                else:
                    self._segments = []
            except Exception:
                self._segments = []

        self._style = {}
        if style_file.exists():
            try:
                self._style = json.loads(style_file.read_text(encoding="utf-8"))
            except Exception:
                self._style = {}

        if ass_file.exists():
            self._subtitles_path = str(ass_file.resolve())
        elif self._segments:
            try:
                from dubstudio.subtitles.ass import generate_ass_subtitles
                vw = getattr(self, "_video_w", 1280) or 1280
                vh = getattr(self, "_video_h", 720) or 720
                ass_out = ws_job / "subtitles.ass"
                generate_ass_subtitles(self._segments, ass_out, style=self._style, video_width=vw, video_height=vh)
                self._subtitles_path = str(ass_out.resolve())
            except Exception:
                self._subtitles_path = ""

        has_subs = bool(self._segments or self._subtitles_path)
        if hasattr(self, "_chk_subtitles"):
            self._chk_subtitles.blockSignals(True)
            self._chk_subtitles.setEnabled(has_subs)
            self._chk_subtitles.setChecked(has_subs)
            if has_subs:
                self._chk_subtitles.setText(f"Nhúng phụ đề tiếng Việt (Dự án: {job_id})")
            else:
                self._chk_subtitles.setText("Nhúng phụ đề tiếng Việt (Không tìm thấy phụ đề)")
            self._chk_subtitles.blockSignals(False)

        if has_subs:
            self._video_player.set_overlay_preview_visible(True)
            self._on_player_pos_changed(self._video_player.get_position())
        else:
            self._video_player.set_overlay_preview_visible(False)
            self._video_player.update_subtitle_overlay("", {}, visible=False)

        self._update_status_pills()

    def _clear_subtitles(self):
        self._segments = []
        self._style = {}
        self._subtitles_path = ""
        if hasattr(self, "_chk_subtitles"):
            self._chk_subtitles.blockSignals(True)
            self._chk_subtitles.setChecked(False)
            self._chk_subtitles.setEnabled(False)
            self._chk_subtitles.setText("Nhúng phụ đề tiếng Việt (Chưa chọn dự án)")
            self._chk_subtitles.blockSignals(False)
        self._video_player.set_overlay_preview_visible(False)
        self._video_player.update_subtitle_overlay("", {}, visible=False)
        self._update_status_pills()

    def _on_subtitles_toggled(self, checked: bool):
        self._update_status_pills()
        if checked and getattr(self, "_segments", []):
            self._video_player.set_overlay_preview_visible(True)
            self._on_player_pos_changed(self._video_player.get_position())
        else:
            self._video_player.set_overlay_preview_visible(False)
            self._video_player.update_subtitle_overlay("", {}, visible=False)

    def _on_player_pos_changed(self, sec: float):
        if not hasattr(self, "_video_player") or not self._video_player:
            return
        if not hasattr(self, "_chk_subtitles") or not self._chk_subtitles.isChecked():
            self._video_player.update_subtitle_overlay("", {}, visible=False)
            return

        segments = getattr(self, "_segments", [])
        if not segments:
            self._video_player.update_subtitle_overlay("", {}, visible=False)
            return

        from dubstudio.subtitles.ass import get_segment_slices
        current_text = None

        for i, seg in enumerate(segments):
            if not isinstance(seg, dict):
                continue
            st = float(seg.get("start", 0.0))
            en = float(seg.get("end", 0.0))
            if i + 1 < len(segments) and isinstance(segments[i + 1], dict):
                next_st = float(segments[i + 1].get("start", 0.0))
                if en > next_st:
                    en = next_st

            if st <= sec <= en:
                slices = get_segment_slices(seg)
                for sl_idx, sl in enumerate(slices):
                    sl_st = sl["start"]
                    sl_en = sl["end"]
                    if sl_idx + 1 < len(slices):
                        sl_en = min(sl_en, slices[sl_idx + 1]["start"])
                    if sl_st <= sec <= sl_en:
                        current_text = sl["text"]
                        break
                if not current_text and slices:
                    current_text = slices[-1]["text"]
                break

        style = getattr(self, "_style", {}) or {}
        if not current_text:
            is_playing = False
            if hasattr(self._video_player, "_player"):
                from PyQt6.QtMultimedia import QMediaPlayer
                is_playing = (self._video_player._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
            if not is_playing:
                first_seg_text = segments[0].get("text_vi") if (segments and isinstance(segments[0], dict)) else None
                current_text = first_seg_text or "Xin chào! Đây là phụ đề mẫu tiếng Việt."

        if current_text:
            self._video_player.update_subtitle_overlay(current_text, style, visible=True)
        else:
            self._video_player.update_subtitle_overlay("", style, visible=False)

    def _pick_canvas_color(self):
        c = QColorDialog.getColor(QColor(self._canvas_color), self, "Chọn màu nền Canvas")
        if c.isValid():
            self._canvas_color = c.name().upper()
            self._btn_canvas_color.setText(f"  {self._canvas_color}")
            is_light = c.lightness() > 128
            self._btn_canvas_color.setStyleSheet(
                f"background-color: {self._canvas_color}; color: {'#000000' if is_light else '#FFFFFF'}; font-weight: bold; border: 1px solid #374151; border-radius: 4px; padding: 0 10px;"
            )
            self._on_scale_config_changed()

    def _on_scale_config_changed(self):
        """Update live aspect ratio padding preview in real time."""
        aspect = "original"
        if hasattr(self, "_combo_aspect"):
            aspect = self._combo_aspect.currentData() or "original"
        enabled = hasattr(self, "_chk_enable_scale") and self._chk_enable_scale.isChecked() and (aspect != "original")
        c_color = getattr(self, "_canvas_color", "#000000")
        self._video_player.set_canvas_aspect_ratio(aspect, c_color, enabled)
        self._update_status_pills()

    def _update_status_pills(self):
        """Update the status pill badges above the video player."""
        if not hasattr(self, "_lbl_pill_aspect"):
            return
        aspect = "original"
        if hasattr(self, "_combo_aspect"):
            aspect = self._combo_aspect.currentData() or "original"
        enabled = hasattr(self, "_chk_enable_scale") and self._chk_enable_scale.isChecked() and (aspect != "original")
        vw = getattr(self, "_video_w", 1280) or 1280
        vh = getattr(self, "_video_h", 720) or 720

        if enabled and aspect != "original":
            self._lbl_pill_aspect.setText(f"{aspect}")
            self._lbl_pill_aspect.setStyleSheet(
                "background: #0c2a4d; color: #38bdf8; border: 1px solid #0284c7; border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: 600;"
            )
            target_r = 9/16 if aspect == "9:16" else (1.0 if aspect == "1:1" else (16/9 if aspect == "16:9" else (4/5 if aspect == "4:5" else 4/3)))
            if (vw / vh) > target_r:
                cw = vw
                ch = int(round(vw / target_r))
            else:
                ch = vh
                cw = int(round(vh * target_r))
            cw += cw % 2
            ch += ch % 2
            self._lbl_pill_dim.setText(f"{cw} × {ch}")
        else:
            self._lbl_pill_aspect.setText("Gốc")
            self._lbl_pill_aspect.setStyleSheet(
                "background: #14161f; color: #9ca3af; border: 1px solid #1e2230; border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: 500;"
            )
            self._lbl_pill_dim.setText(f"{vw} × {vh}")

        has_sub = hasattr(self, "_chk_subtitles") and self._chk_subtitles.isChecked()
        if has_sub:
            self._lbl_pill_subs.setText("Phụ đề: Có")
            self._lbl_pill_subs.setStyleSheet(
                "background: #0f2e22; color: #22c55e; border: 1px solid #14532d; border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 500;"
            )
        else:
            self._lbl_pill_subs.setText("Phụ đề: Không")
            self._lbl_pill_subs.setStyleSheet(
                "background: #1e293b; color: #64748b; border: 1px solid #334155; border-radius: 4px; padding: 2px 8px; font-size: 11px;"
            )

    def _browse_source_video(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Chọn video cần chỉnh sửa", "", "Video files (*.mp4 *.mkv *.avi *.mov *.flv *.webm);;All files (*)"
        )
        if f:
            self._txt_src_video.setText(f)

    def _on_src_video_changed(self, path_str: str):
        p = Path(path_str.strip())
        if p.exists() and p.is_file():
            self._input_video_path = str(p.resolve())
            self._video_player.load_video(self._input_video_path)

            self._video_w = getattr(self._video_player, "_video_native_w", 1280) or 1280
            self._video_h = getattr(self._video_player, "_video_native_h", 720) or 720
            self._lbl_video_dims.setText(f"Độ phân giải: {self._video_w} x {self._video_h}")

            # If job_id not set or mismatch, try to infer from video path
            from dubstudio.paths import resolve_job_workspace, open_in_file_manager
            if not self._job_id or not resolve_job_workspace(self._job_id).exists():
                inferred_jid = ""
                if p.parent.parent.name == "workspace" and p.parent.exists():
                    inferred_jid = p.parent.name
                elif p.parent.name == "out" and "_vi" in p.name:
                    inferred_jid = p.stem.replace("_vi", "")
                if inferred_jid:
                    self._job_id = inferred_jid
                    self._load_project_subtitles(self._job_id)
            elif self._job_id:
                self._load_project_subtitles(self._job_id)

            # Reset default values matching video
            self._spin_crop_x.setValue(0)
            self._spin_crop_y.setValue(0)
            self._spin_crop_w.setValue(self._video_w)
            self._spin_crop_h.setValue(self._video_h)

            self._spin_box_x.setValue(0)
            self._spin_box_y.setValue(max(0, self._video_h - 140))
            self._spin_box_w.setValue(self._video_w)
            self._spin_box_h.setValue(min(140, self._video_h))

            self._editor_overlay.set_video_dimensions(
                self._video_w, self._video_h, self._video_player._get_active_video_rect
            )
            self._refresh_box_combo(select_idx=0)
            self._sync_ui_to_overlay()
            self._on_scale_config_changed()
        else:
            self._lbl_video_dims.setText("Độ phân giải: Chưa tải")

    def _apply_crop_preset(self, preset: str):
        w = getattr(self, "_video_w", 1280) or 1280
        h = getattr(self, "_video_h", 720) or 720
        self._chk_enable_crop.setChecked(True)

        if preset == "16:9":
            target_h = int(w * 9 / 16)
            if target_h <= h:
                self._spin_crop_x.setValue(0)
                self._spin_crop_y.setValue((h - target_h) // 2)
                self._spin_crop_w.setValue(w)
                self._spin_crop_h.setValue(target_h)
            else:
                target_w = int(h * 16 / 9)
                self._spin_crop_x.setValue((w - target_w) // 2)
                self._spin_crop_y.setValue(0)
                self._spin_crop_w.setValue(target_w)
                self._spin_crop_h.setValue(h)
        elif preset == "9:16":
            target_w = int(h * 9 / 16)
            self._spin_crop_x.setValue((w - target_w) // 2)
            self._spin_crop_y.setValue(0)
            self._spin_crop_w.setValue(target_w)
            self._spin_crop_h.setValue(h)
        elif preset == "1:1":
            side = min(w, h)
            self._spin_crop_x.setValue((w - side) // 2)
            self._spin_crop_y.setValue((h - side) // 2)
            self._spin_crop_w.setValue(side)
            self._spin_crop_h.setValue(side)
        elif preset == "4:3":
            target_w = int(h * 4 / 3)
            self._spin_crop_x.setValue((w - target_w) // 2)
            self._spin_crop_y.setValue(0)
            self._spin_crop_w.setValue(target_w)
            self._spin_crop_h.setValue(h)
        elif preset == "full":
            self._spin_crop_x.setValue(0)
            self._spin_crop_y.setValue(0)
            self._spin_crop_w.setValue(w)
            self._spin_crop_h.setValue(h)

        self._sync_ui_to_overlay()

    def _pick_box_color(self):
        c = QColorDialog.getColor(QColor(self._color_box_hex), self, "Chọn màu khối che")
        if c.isValid():
            self._color_box_hex = c.name().upper()
            self._btn_box_color.setStyleSheet(
                f"background-color: {self._color_box_hex}; color: #FFFFFF; font-weight: bold;"
            )
            self._sync_ui_to_overlay()

    def _browse_overlay_image(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Chọn hình ảnh logo / lớp phủ", "", "Image files (*.png *.jpg *.jpeg *.webp *.bmp);;All files (*)"
        )
        if f:
            self._overlay_image_path = f
            self._txt_img_path.setText(f)
            self._chk_enable_img.setChecked(True)
            try:
                pix = QPixmap(f)
                if not pix.isNull():
                    self._overlay_pixmap = pix
                    self._img_orig_w = max(1, pix.width())
                    self._img_orig_h = max(1, pix.height())
                    self._spin_img_w.setValue(min(300, self._img_orig_w))
                    self._on_img_w_changed(self._spin_img_w.value())
            except Exception:
                pass
            self._sync_ui_to_overlay()

    def _on_img_w_changed(self, new_w: int):
        if self._chk_fix_scale.isChecked() and self._img_orig_w > 0:
            ratio = self._img_orig_h / self._img_orig_w
            self._spin_img_h.blockSignals(True)
            self._spin_img_h.setValue(max(10, int(new_w * ratio)))
            self._spin_img_h.blockSignals(False)
        self._sync_ui_to_overlay()

    def _apply_logo_corner(self, corner: str):
        w = getattr(self, "_video_w", 1280) or 1280
        h = getattr(self, "_video_h", 720) or 720
        lw = self._spin_img_w.value()
        lh = self._spin_img_h.value()
        margin = 25
        self._chk_enable_img.setChecked(True)

        if corner == "tl":
            self._spin_img_x.setValue(margin)
            self._spin_img_y.setValue(margin)
        elif corner == "tr":
            self._spin_img_x.setValue(max(0, w - lw - margin))
            self._spin_img_y.setValue(margin)
        elif corner == "bl":
            self._spin_img_x.setValue(margin)
            self._spin_img_y.setValue(max(0, h - lh - margin))
        elif corner == "br":
            self._spin_img_x.setValue(max(0, w - lw - margin))
            self._spin_img_y.setValue(max(0, h - lh - margin))

        self._sync_ui_to_overlay()

    def _start_edit_video(self):
        v_path = self._txt_src_video.text().strip()
        if not v_path or not Path(v_path).exists():
            QMessageBox.warning(self, "Chưa chọn video", "Vui lòng chọn một tệp video hợp lệ để chỉnh sửa!")
            return

        enable_crop = self._chk_enable_crop.isChecked()
        enabled_boxes = [b for b in self._editor_overlay.get_boxes() if b.get("enabled", False)]
        enable_img = self._chk_enable_img.isChecked()
        enable_scale = hasattr(self, "_chk_enable_scale") and self._chk_enable_scale.isChecked()
        enable_subs = hasattr(self, "_chk_subtitles") and self._chk_subtitles.isChecked()

        out_name = self._txt_edit_out_name.text().strip()
        if not out_name or out_name == "edited_video.mp4":
            if self._job_id:
                out_name = f"{self._job_id}.mp4"
            else:
                out_name = "edited_video.mp4"
        if not out_name.endswith(".mp4"):
            out_name += ".mp4"

        payload: dict = {
            "video_path": v_path,
            "output_name": out_name,
            "job_id": self._job_id or None,
            "subtitles_enabled": enable_subs,
            "subtitles_path": getattr(self, "_subtitles_path", "") or None,
        }

        if enable_scale and hasattr(self, "_combo_aspect"):
            aspect = self._combo_aspect.currentData() or "original"
            if aspect != "original":
                payload["aspect_ratio"] = aspect
                payload["canvas_color"] = getattr(self, "_canvas_color", "000000").lstrip("#")

        if enable_crop:
            payload["crop_box"] = {
                "x": self._spin_crop_x.value(),
                "y": self._spin_crop_y.value(),
                "w": self._spin_crop_w.value(),
                "h": self._spin_crop_h.value(),
            }

        if enabled_boxes:
            payload["color_boxes"] = enabled_boxes

        if enable_img:
            img_p = self._txt_img_path.text().strip()
            if not img_p or not Path(img_p).exists():
                QMessageBox.warning(self, "Chưa chọn ảnh", "Vui lòng chọn tệp hình ảnh hợp lệ để chèn logo!")
                return
            payload["image_overlay"] = {
                "image_path": img_p,
                "x": self._spin_img_x.value(),
                "y": self._spin_img_y.value(),
                "w": self._spin_img_w.value(),
                "h": self._spin_img_h.value(),
                "fix_scale": self._chk_fix_scale.isChecked(),
            }

        # Unload video in player before export to avoid file locking on Windows
        self._video_player.unload()

        self._btn_run_edit.setEnabled(False)
        self._progress_edit.setVisible(True)
        self._lbl_edit_status.setText("Đang xử lý video bằng ffmpeg...")

        self._edit_worker = EditVideoWorker(payload)

        def _on_done(res: dict):
            self._btn_run_edit.setEnabled(True)
            self._progress_edit.setVisible(False)
            out_file = res.get("file") or out_name
            out_path = res.get("path", "")
            self._lbl_edit_status.setText(f"✓ Xử lý thành công: {out_file}")

            # Terminate TTS worker process to free all RAM & VRAM
            w_stop = StopTTSWorker()
            self._workers.append(w_stop)
            w_stop.start()

            from dubstudio.paths import get_out_dir, open_in_file_manager
            target_p = Path(out_path).resolve() if (out_path and Path(out_path).exists()) else (get_out_dir() / out_file)

            if self._job_id and target_p.exists():
                try:
                    import shutil
                    from dubstudio.paths import resolve_job_workspace
                    ws_dest = resolve_job_workspace(self._job_id) / target_p.name
                    if target_p.resolve() != ws_dest.resolve():
                        shutil.copy2(target_p, ws_dest)
                except Exception:
                    pass

            # Reload output video into player so user can view results immediately!
            if target_p.exists():
                self._txt_src_video.setText(str(target_p))
                if hasattr(self, "_video_player") and self._video_player:
                    self._video_player.load_video(str(target_p))

            msg = QMessageBox(self)
            msg.setWindowTitle("Xuất video thành công")
            msg.setText(
                f"Đã xuất thành công video:\n\n"
                f"📹 Tập tin: {target_p.name}\n"
                f"📂 Thư mục: {target_p.parent}"
            )
            btn_play = msg.addButton("Xem video ngay", QMessageBox.ButtonRole.AcceptRole)
            btn_folder = msg.addButton("Mở thư mục video", QMessageBox.ButtonRole.ActionRole)
            msg.addButton("Đóng", QMessageBox.ButtonRole.RejectRole)

            msg.exec()
            if msg.clickedButton() == btn_play:
                if target_p.exists():
                    open_in_file_manager(target_p)
                elif hasattr(self, "_video_player") and self._video_player:
                    self._video_player.play()
            elif msg.clickedButton() == btn_folder:
                open_in_file_manager(target_p)

        def _on_err(err: str):
            self._btn_run_edit.setEnabled(True)
            self._progress_edit.setVisible(False)
            self._lbl_edit_status.setText(f"Lỗi: {err}")
            QMessageBox.critical(self, "Lỗi chỉnh sửa video", f"Không thể xử lý video: {err}")

        self._edit_worker.finished.connect(_on_done)
        self._edit_worker.error.connect(_on_err)
        self._workers.append(self._edit_worker)
        self._edit_worker.start()

    # ─── Tab 2 Implementation (Merge Videos) ─────────────────────────────────

    def _setup_tab_merge(self, parent: QWidget):
        box_layout = QVBoxLayout(parent)
        box_layout.setContentsMargins(10, 10, 10, 10)
        box_layout.setSpacing(10)

        card_merge = BentoCard("Ghép nối danh sách video", "link")

        lbl_instruct = QLabel("Chọn video theo thứ tự cần ghép nối:")
        lbl_instruct.setStyleSheet("color: #9ca3af; font-size: 12px;")
        card_merge.add_widget(lbl_instruct)

        self._list_videos = QListWidget()
        card_merge.add_widget(self._list_videos)

        btn_bar = QHBoxLayout()
        btn_add = QPushButton(" Thêm video...")
        btn_add.setIcon(get_icon("plus", "#9ca3af", "#f0f2f5", 14))
        btn_add.clicked.connect(self._add_videos)
        btn_bar.addWidget(btn_add)

        btn_remove = QPushButton(" Xóa")
        btn_remove.setIcon(get_icon("trash", "#ef4444", "#fca5a5", 14))
        btn_remove.setObjectName("danger")
        btn_remove.clicked.connect(self._remove_selected)
        btn_bar.addWidget(btn_remove)

        btn_up = QPushButton(" Lên")
        btn_up.setIcon(get_icon("arrow_up", "#9ca3af", "#f0f2f5", 14))
        btn_up.clicked.connect(self._move_up)
        btn_bar.addWidget(btn_up)

        btn_down = QPushButton(" Xuống")
        btn_down.setIcon(get_icon("arrow_down", "#9ca3af", "#f0f2f5", 14))
        btn_down.clicked.connect(self._move_down)
        btn_bar.addWidget(btn_down)

        btn_bar.addStretch(1)
        card_merge.add_layout(btn_bar)

        card_merge.add_divider()

        opt_layout = QHBoxLayout()
        opt_layout.addWidget(QLabel("Tên tệp:"))
        self._txt_output = QLineEdit("merged_output.mp4")
        opt_layout.addWidget(self._txt_output, 1)

        self._chk_reencode = SwitchToggle("Encode lại")
        opt_layout.addWidget(self._chk_reencode)
        card_merge.add_layout(opt_layout)

        self._btn_merge = QPushButton(" Ghép video")
        self._btn_merge.setIcon(get_icon("link", "#ffffff", "#ffffff", 14))
        self._btn_merge.setObjectName("primary")
        self._btn_merge.setFixedHeight(36)
        self._btn_merge.clicked.connect(self._start_merge)
        card_merge.add_widget(self._btn_merge)

        self._progress_merge = QProgressBar()
        self._progress_merge.setVisible(False)
        self._progress_merge.setRange(0, 0)
        card_merge.add_widget(self._progress_merge)

        self._lbl_merge_status = QLabel("")
        self._lbl_merge_status.setStyleSheet("color: #4f9cf9;")
        card_merge.add_widget(self._lbl_merge_status)

        box_layout.addWidget(card_merge, 1)

    def _add_videos(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Chọn các file video", "", "Video files (*.mp4 *.mkv *.avi *.mov *.flv)"
        )
        for f in files:
            self._list_videos.addItem(f)

    def _remove_selected(self):
        for item in self._list_videos.selectedItems():
            self._list_videos.takeItem(self._list_videos.row(item))

    def _move_up(self):
        row = self._list_videos.currentRow()
        if row > 0:
            item = self._list_videos.takeItem(row)
            self._list_videos.insertItem(row - 1, item)
            self._list_videos.setCurrentRow(row - 1)

    def _move_down(self):
        row = self._list_videos.currentRow()
        if 0 <= row < self._list_videos.count() - 1:
            item = self._list_videos.takeItem(row)
            self._list_videos.insertItem(row + 1, item)
            self._list_videos.setCurrentRow(row + 1)

    def _start_merge(self):
        count = self._list_videos.count()
        if count < 2:
            QMessageBox.warning(self, "Chưa đủ video", "Vui lòng chọn ít nhất 2 video để ghép nối!")
            return

        videos = [self._list_videos.item(i).text() for i in range(count)]
        output_name = self._txt_output.text().strip() or "merged_output.mp4"

        self._btn_merge.setEnabled(False)
        self._progress_merge.setVisible(True)
        self._lbl_merge_status.setText("Đang ghép các đoạn video...")

        self._merge_worker = MergeVideosWorker(
            videos=videos,
            output_name=output_name,
            force_reencode=self._chk_reencode.isChecked(),
        )

        def _on_done(res: dict):
            self._btn_merge.setEnabled(True)
            self._progress_merge.setVisible(False)
            path = res.get("path", "")
            self._lbl_merge_status.setText(f"✓ Ghép video hoàn tất: {output_name}")
            QMessageBox.information(
                self,
                "Ghép thành công",
                f"Video đã ghép được lưu tại:\n{path}",
            )

        def _on_err(err: str):
            self._btn_merge.setEnabled(True)
            self._progress_merge.setVisible(False)
            self._lbl_merge_status.setText(f"Lỗi: {err}")
            QMessageBox.critical(self, "Lỗi ghép video", f"Không thể ghép video: {err}")

        self._merge_worker.finished.connect(_on_done)
        self._merge_worker.error.connect(_on_err)
        self._workers.append(self._merge_worker)
        self._merge_worker.start()

    # ─── Tab 3 Implementation (Video Trimmer / Clipper) ──────────────────────

    def _setup_tab_trim(self, parent: QWidget):
        split_layout = QHBoxLayout(parent)
        split_layout.setContentsMargins(4, 4, 4, 4)
        split_layout.setSpacing(12)

        # ── LEFT PANE: Video Player + Range Timeline Slider ──
        left_box = QWidget()
        v_left = QVBoxLayout(left_box)
        v_left.setContentsMargins(0, 0, 0, 0)
        v_left.setSpacing(8)

        # Top bar with Video file path and Browse button
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        lbl_video = QLabel("Video nguồn:")
        lbl_video.setStyleSheet("font-weight: 600; font-size: 12px; color: #f1f3f7;")
        top_bar.addWidget(lbl_video)

        self._txt_trim_video = QLineEdit()
        self._txt_trim_video.setPlaceholderText("Chọn video cần cắt (MP4, MKV, MOV, WebM)...")
        self._txt_trim_video.setFixedHeight(30)
        self._txt_trim_video.setReadOnly(True)
        top_bar.addWidget(self._txt_trim_video, 1)

        btn_browse = QPushButton("  Chọn video...")
        btn_browse.setIcon(get_icon("folder", "#9ca3af", "#f0f2f5", 13))
        btn_browse.setFixedHeight(30)
        btn_browse.clicked.connect(self._browse_trim_video)
        top_bar.addWidget(btn_browse)

        v_left.addLayout(top_bar)

        # Video Player Widget
        self._trim_player = VideoPlayerWidget()
        self._trim_player.position_changed.connect(self._on_trim_player_pos_changed)
        self._trim_player.duration_known.connect(self._on_trim_player_duration_known)
        v_left.addWidget(self._trim_player, 1)

        # Dual-handle Range Timeline Slider
        slider_card = QFrame()
        slider_card.setStyleSheet("background-color: #0b1320; border: 1px solid #1e293b; border-radius: 8px; padding: 6px;")
        sc_layout = QVBoxLayout(slider_card)
        sc_layout.setContentsMargins(6, 4, 6, 4)
        sc_layout.setSpacing(4)

        slider_hdr = QHBoxLayout()
        lbl_timeline_hint = QLabel("Khoanh vùng đoạn video (Kéo thả 2 chốt để chọn điểm đầu và cuối):")
        lbl_timeline_hint.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: 500;")
        slider_hdr.addWidget(lbl_timeline_hint)
        slider_hdr.addStretch(1)

        self._lbl_trim_cur_time = QLabel("00:00.00 / 00:00.00")
        self._lbl_trim_cur_time.setStyleSheet("font-size: 11px; color: #f59e0b; font-weight: 600;")
        slider_hdr.addWidget(self._lbl_trim_cur_time)
        sc_layout.addLayout(slider_hdr)

        self._range_slider = RangeSlider()
        self._range_slider.range_changed.connect(self._on_range_slider_changed)
        self._range_slider.seek_requested.connect(self._on_range_slider_seek)
        sc_layout.addWidget(self._range_slider)

        v_left.addWidget(slider_card)
        split_layout.addWidget(left_box, 3)

        # ── RIGHT PANE: Precise Parameter Controls ──
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_scroll.setFixedWidth(330)

        right_container = QWidget()
        v_right = QVBoxLayout(right_container)
        v_right.setContentsMargins(4, 0, 6, 4)
        v_right.setSpacing(12)

        # Card 1: Precise Time Boundaries
        box_time = QGroupBox("Mốc thời gian cắt chính xác (giây)")
        time_lay = QVBoxLayout(box_time)
        time_lay.setSpacing(8)

        # Start time row
        time_lay.addWidget(QLabel("Thời điểm BẮT ĐẦU [ (giây):"))
        h_start = QHBoxLayout()
        self._spin_trim_start = QDoubleSpinBox()
        self._spin_trim_start.setRange(0.0, 99999.0)
        self._spin_trim_start.setDecimals(2)
        self._spin_trim_start.setSingleStep(0.1)
        self._spin_trim_start.setFixedHeight(30)
        self._spin_trim_start.valueChanged.connect(self._on_spin_times_changed)
        h_start.addWidget(self._spin_trim_start, 1)

        btn_mark_in = QPushButton("  Lấy vị trí [")
        btn_mark_in.setIcon(get_icon("clock", "#38bdf8", "#38bdf8", 12))
        btn_mark_in.setFixedHeight(30)
        btn_mark_in.setToolTip("Lấy vị trí hiện tại của con trỏ phát làm mốc bắt đầu")
        btn_mark_in.clicked.connect(self._mark_trim_start)
        h_start.addWidget(btn_mark_in)
        time_lay.addLayout(h_start)

        # End time row
        time_lay.addWidget(QLabel("Thời điểm KẾT THÚC ] (giây):"))
        h_end = QHBoxLayout()
        self._spin_trim_end = QDoubleSpinBox()
        self._spin_trim_end.setRange(0.0, 99999.0)
        self._spin_trim_end.setDecimals(2)
        self._spin_trim_end.setSingleStep(0.1)
        self._spin_trim_end.setFixedHeight(30)
        self._spin_trim_end.valueChanged.connect(self._on_spin_times_changed)
        h_end.addWidget(self._spin_trim_end, 1)

        btn_mark_out = QPushButton("  Lấy vị trí ]")
        btn_mark_out.setIcon(get_icon("clock", "#38bdf8", "#38bdf8", 12))
        btn_mark_out.setFixedHeight(30)
        btn_mark_out.setToolTip("Lấy vị trí hiện tại của con trỏ phát làm mốc kết thúc")
        btn_mark_out.clicked.connect(self._mark_trim_end)
        h_end.addWidget(btn_mark_out)
        time_lay.addLayout(h_end)

        # Duration & preview button
        self._lbl_trim_duration = QLabel("Độ dài đoạn cắt: 00:00.00")
        self._lbl_trim_duration.setStyleSheet("font-size: 12px; font-weight: 700; color: #38bdf8; margin: 4px 0;")
        time_lay.addWidget(self._lbl_trim_duration)

        self._btn_preview_cut = QPushButton("  Phát thử đoạn đã chọn")
        self._btn_preview_cut.setIcon(get_icon("play", "#ffffff", "#ffffff", 13))
        self._btn_preview_cut.setFixedHeight(32)
        self._btn_preview_cut.clicked.connect(self._toggle_preview_cut)
        time_lay.addWidget(self._btn_preview_cut)

        v_right.addWidget(box_time)

        # Card 2: Export Options
        box_export = QGroupBox("Tùy chọn xuất video")
        exp_lay = QVBoxLayout(box_export)
        exp_lay.setSpacing(8)

        self._chk_fast_trim = QCheckBox("Cắt nhanh không nén (Lossless Stream Copy)")
        self._chk_fast_trim.setChecked(True)
        self._chk_fast_trim.setStyleSheet("font-size: 11.5px; color: #f1f3f7;")
        self._chk_fast_trim.setToolTip("Cắt tức thì trong 1 giây, giữ nguyên 100% chất lượng video và âm thanh gốc")
        exp_lay.addWidget(self._chk_fast_trim)

        exp_lay.addWidget(QLabel("Tên file xuất:"))
        self._txt_trim_out_name = QLineEdit("trimmed_clip.mp4")
        self._txt_trim_out_name.setFixedHeight(30)
        exp_lay.addWidget(self._txt_trim_out_name)

        self._btn_run_trim = QPushButton("  Cắt và Xuất video")
        self._btn_run_trim.setIcon(get_icon("scissors", "#ffffff", "#ffffff", 14))
        self._btn_run_trim.setObjectName("primary")
        self._btn_run_trim.setFixedHeight(36)
        self._btn_run_trim.setStyleSheet("font-weight: 700; font-size: 13px;")
        self._btn_run_trim.clicked.connect(self._run_trim_video)
        exp_lay.addWidget(self._btn_run_trim)

        self._progress_trim = QProgressBar()
        self._progress_trim.setRange(0, 0)
        self._progress_trim.setVisible(False)
        self._progress_trim.setFixedHeight(4)
        exp_lay.addWidget(self._progress_trim)

        self._lbl_trim_status = QLabel("")
        self._lbl_trim_status.setStyleSheet("font-size: 11px; color: #38bdf8;")
        self._lbl_trim_status.setWordWrap(True)
        exp_lay.addWidget(self._lbl_trim_status)

        v_right.addWidget(box_export)
        v_right.addStretch(1)

        right_scroll.setWidget(right_container)
        split_layout.addWidget(right_scroll, 1)

    def _browse_trim_video(self):
        """Select a video file to trim."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn video cần cắt",
            "",
            "Video Files (*.mp4 *.mkv *.mov *.webm *.avi);;All Files (*.*)",
        )
        if not path:
            return
        self.load_trim_video_path(path)

    def load_trim_video_path(self, path: str):
        """Load a video path into the trimmer tab."""
        p = Path(path)
        if not p.exists():
            return
        self._trim_video_path = str(p.resolve())
        self._txt_trim_video.setText(self._trim_video_path)
        stem = p.stem
        self._txt_trim_out_name.setText(f"{stem}_cut.mp4")
        self._lbl_trim_status.setText("")
        self._trim_player.load_video(self._trim_video_path)

    def _on_trim_player_duration_known(self, dur: float):
        """Update timeline range when video length is detected."""
        dur = max(0.1, float(dur))
        self._range_slider.set_duration(dur)
        self._spin_trim_start.blockSignals(True)
        self._spin_trim_end.blockSignals(True)
        self._spin_trim_start.setRange(0.0, dur)
        self._spin_trim_end.setRange(0.0, dur)
        self._spin_trim_start.setValue(0.0)
        self._spin_trim_end.setValue(dur)
        self._spin_trim_start.blockSignals(False)
        self._spin_trim_end.blockSignals(False)
        self._update_trim_duration_label()

    def _on_trim_player_pos_changed(self, pos: float):
        """Track playhead on the range slider."""
        self._range_slider.set_current_position(pos)
        dur = self._range_slider.duration
        self._lbl_trim_cur_time.setText(f"{self._fmt_dur(pos)} / {self._fmt_dur(dur)}")

        # If in preview cut mode, stop playback when reaching end marker
        if self._is_previewing_cut and pos >= self._spin_trim_end.value():
            self._trim_player.pause()
            self._is_previewing_cut = False
            self._btn_preview_cut.setText("  Phát thử đoạn đã chọn")
            self._btn_preview_cut.setIcon(get_icon("play", "#ffffff", "#ffffff", 13))

    def _on_range_slider_changed(self, start_s: float, end_s: float):
        """Update spinboxes when range slider handles are moved."""
        self._spin_trim_start.blockSignals(True)
        self._spin_trim_end.blockSignals(True)
        self._spin_trim_start.setValue(round(start_s, 2))
        self._spin_trim_end.setValue(round(end_s, 2))
        self._spin_trim_start.blockSignals(False)
        self._spin_trim_end.blockSignals(False)
        self._update_trim_duration_label()

    def _on_range_slider_seek(self, seek_s: float):
        """Seek player when clicking on range timeline."""
        self._trim_player.seek(seek_s)

    def _on_spin_times_changed(self):
        """Update range slider when spinbox values change."""
        s = self._spin_trim_start.value()
        e = self._spin_trim_end.value()
        if s > e:
            e = s + 0.1
            self._spin_trim_end.blockSignals(True)
            self._spin_trim_end.setValue(e)
            self._spin_trim_end.blockSignals(False)
        self._range_slider.set_range(s, e)
        self._update_trim_duration_label()

    def _mark_trim_start(self):
        """Set start time to current player position."""
        pos = round(self._trim_player.get_position(), 2)
        self._spin_trim_start.setValue(pos)

    def _mark_trim_end(self):
        """Set end time to current player position."""
        pos = round(self._trim_player.get_position(), 2)
        self._spin_trim_end.setValue(pos)

    def _update_trim_duration_label(self):
        s = self._spin_trim_start.value()
        e = self._spin_trim_end.value()
        span = max(0.0, e - s)
        self._lbl_trim_duration.setText(f"Độ dài đoạn cắt: {span:.2f}s ({self._fmt_dur(span)})")

    def _toggle_preview_cut(self):
        """Play only the selected span from start to end."""
        s = self._spin_trim_start.value()
        e = self._spin_trim_end.value()
        if e <= s:
            return

        if self._is_previewing_cut:
            self._trim_player.pause()
            self._is_previewing_cut = False
            self._btn_preview_cut.setText("  Phát thử đoạn đã chọn")
            self._btn_preview_cut.setIcon(get_icon("play", "#ffffff", "#ffffff", 13))
        else:
            self._trim_player.seek(s)
            self._trim_player.play()
            self._is_previewing_cut = True
            self._btn_preview_cut.setText("  Dừng phát thử")
            self._btn_preview_cut.setIcon(get_icon("pause", "#ffffff", "#ffffff", 13))

    def _run_trim_video(self):
        """Execute video cut and export via TrimVideoWorker."""
        v_path = self._txt_trim_video.text().strip()
        if not v_path or not Path(v_path).exists():
            QMessageBox.warning(self, "Chưa chọn video", "Vui lòng chọn video nguồn trước khi cắt.")
            return

        start_s = self._spin_trim_start.value()
        end_s = self._spin_trim_end.value()
        if end_s <= start_s:
            QMessageBox.warning(self, "Thời gian không hợp lệ", "Thời điểm kết thúc phải lớn hơn thời điểm bắt đầu.")
            return

        out_name = self._txt_trim_out_name.text().strip() or "trimmed_clip.mp4"
        if not out_name.endswith((".mp4", ".mkv", ".mov", ".webm")):
            out_name += ".mp4"

        payload = {
            "video_path": v_path,
            "start_s": start_s,
            "end_s": end_s,
            "output_name": out_name,
            "fast_copy": self._chk_fast_trim.isChecked(),
        }

        self._btn_run_trim.setEnabled(False)
        self._progress_trim.setVisible(True)
        self._lbl_trim_status.setText("Đang cắt video...")

        # Terminate any TTS worker to free RAM/VRAM
        try:
            w_stop = StopTTSWorker()
            self._workers.append(w_stop)
            w_stop.start()
        except Exception:
            pass

        self._trim_worker = TrimVideoWorker(payload)

        def _on_done(res: dict):
            self._btn_run_trim.setEnabled(True)
            self._progress_trim.setVisible(False)
            out_path = res.get("path", "")
            out_file = res.get("file", out_name)
            dur = res.get("duration", 0)
            self._lbl_trim_status.setText(f"✓ Cắt video thành công: {out_file} ({dur}s)")

            reply = QMessageBox.information(
                self,
                "Cắt video thành công",
                f"Đã cắt và xuất video thành công ({dur}s) tại:\n{out_path}\n\nBạn có muốn mở thư mục chứa video này không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                from dubstudio.paths import open_in_file_manager
                open_in_file_manager(Path(out_path) if out_path else get_out_dir())

        def _on_err(err: str):
            self._btn_run_trim.setEnabled(True)
            self._progress_trim.setVisible(False)
            self._lbl_trim_status.setText(f"Lỗi: {err}")
            QMessageBox.critical(self, "Lỗi cắt video", f"Không thể cắt video: {err}")

        self._trim_worker.finished.connect(_on_done)
        self._trim_worker.error.connect(_on_err)
        self._workers.append(self._trim_worker)
        self._trim_worker.start()

    @staticmethod
    def _fmt_dur(seconds: float) -> str:
        if seconds < 0:
            seconds = 0
        m = int(seconds) // 60
        s = seconds % 60
        return f"{m:02d}:{s:05.2f}"

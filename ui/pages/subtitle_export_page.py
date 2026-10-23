"""Subtitle & Video Export Page: Detailed subtitle styling, live preview box, and final rendering."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtCore import QTimer, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ui.icons import get_icon
from ui.theme import COLORS
from ui.widgets.bento_card import BentoCard
from ui.widgets.switch import SwitchToggle
from ui.widgets.video_player import VideoPlayerWidget
from ui.workers import ListJobsWorker, LoadJobWorker, RenderVideoWorker, StopTTSWorker


VIETNAMESE_FONTS = [
    "Arial",
    "Segoe UI",
    "Tahoma",
    "Calibri",
    "Verdana",
    "Times New Roman",
]


FACTORY_STYLE = {
    "font_name": "Arial",
    "font_size": 22,
    "primary_color": "#FFFFFF",
    "outline_color": "#000000",
    "outline_width": 2,
    "has_box": True,
    "box_color": "#000000",
    "box_opacity": 0.6,
    "box_radius": 6,
    "box_mode": "full_width",
    "box_padding": 8,
    "box_padding_x": 14,
    "box_padding_y": 8,
    "pos_y_pct": 82.0,
    "position": "bottom",
    "margin_v": 35,
    "text_align": "center",
    "vi_voice_volume": 1.00,
    "orig_bgm_volume": 0.80,
    "bgm_volume": 0.80,
    "custom_bgm_path": None,
    "custom_bgm_volume": 0.50,
    "box_width_pct": 85,
    "include_orig_voice": False,
    "orig_voice_volume": 0.00,
}
GLOBAL_PRESET_FILE = Path("config/subtitle_preset.json")


class SubtitleExportPage(QWidget):
    """Page 3: Detailed subtitle styling, live preview, and final video rendering."""

    open_folder_requested = pyqtSignal(str)
    goto_merge_requested = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_job_id: Optional[str] = None
        self._jobs: List[dict] = []
        self._segments: List[dict] = []
        self._workers: List[any] = []
        self._preview_sub_visible = True

        self._style = dict(FACTORY_STYLE)
        if GLOBAL_PRESET_FILE.exists():
            try:
                loaded_preset = json.loads(GLOBAL_PRESET_FILE.read_text(encoding="utf-8"))
                self._style.update(loaded_preset)
            except Exception:
                pass

        self._pending_vi_vol = 1.0
        self._vi_boost_timer = QTimer(self)
        self._vi_boost_timer.setSingleShot(True)
        self._vi_boost_timer.setInterval(120)
        self._vi_boost_timer.timeout.connect(self._apply_vi_boost)

        self._save_debounce_timer = QTimer(self)
        self._save_debounce_timer.setSingleShot(True)
        self._save_debounce_timer.setInterval(300)
        self._save_debounce_timer.timeout.connect(self._do_async_save_style)

        self._setup_ui()


    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(10)

        # ─── Top Control Bar: Job Selector & Actions ───
        top_frame = QFrame()
        top_frame.setObjectName("toolbar_card")
        top_bar = QHBoxLayout(top_frame)
        top_bar.setContentsMargins(10, 8, 10, 8)
        top_bar.setSpacing(8)

        lbl_select = QLabel("Dự án:")
        lbl_select.setObjectName("toolbar_label")
        top_bar.addWidget(lbl_select)

        self._combo_jobs = QComboBox()
        self._combo_jobs.setMinimumWidth(220)
        self._combo_jobs.setFixedHeight(28)
        self._combo_jobs.currentIndexChanged.connect(self._on_job_selected)
        top_bar.addWidget(self._combo_jobs)

        btn_refresh = QPushButton()
        btn_refresh.setIcon(get_icon("refresh", "#9ca3af", "#f0f2f5", 12))
        btn_refresh.setObjectName("compact")
        btn_refresh.setFixedSize(28, 28)
        btn_refresh.setToolTip("Làm mới danh sách dự án")
        btn_refresh.clicked.connect(self.refresh_jobs)
        top_bar.addWidget(btn_refresh)

        top_bar.addStretch(1)

        # Status & Progress indicator
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setFixedWidth(140)
        self._progress_bar.setFixedHeight(4)
        top_bar.addWidget(self._progress_bar)

        self._lbl_status = QLabel("")
        self._lbl_status.setObjectName("status_label")
        top_bar.addWidget(self._lbl_status)

        # Action Buttons
        self._btn_render = QPushButton("  Xuất video")
        self._btn_render.setIcon(get_icon("film", "#ffffff", "#ffffff", 13))
        self._btn_render.setObjectName("primary")
        self._btn_render.setFixedHeight(30)
        self._btn_render.setToolTip("Khắc phụ đề và xuất video hoàn thiện trực tiếp tại đây")
        self._btn_render.clicked.connect(self._start_render)
        top_bar.addWidget(self._btn_render)

        self._btn_goto_merge = QPushButton("  Chỉnh sửa video ➔")
        self._btn_goto_merge.setIcon(get_icon("scissors", "#9ca3af", "#38bdf8", 13))
        self._btn_goto_merge.setFixedHeight(30)
        self._btn_goto_merge.setToolTip("Chuyển sang Tab Chỉnh sửa video (Crop, Canvas 9:16, Khối che, Logo)")
        self._btn_goto_merge.clicked.connect(self._on_goto_merge)
        top_bar.addWidget(self._btn_goto_merge)

        main_layout.addWidget(top_frame)

        # ─── Central Splitter: Left (Video Player & Live Subtitle Box) vs Right (Styling Controls) ───
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Left Column: Video Preview + Live Subtitle Preview
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        left_header = QHBoxLayout()
        lbl_vid_title = QLabel("Xem trước")
        lbl_vid_title.setObjectName("section_title")
        left_header.addWidget(lbl_vid_title, 1)

        self._btn_toggle_preview_sub = QPushButton("  Ẩn phụ đề mẫu")
        self._btn_toggle_preview_sub.setIcon(get_icon("eye", "#9ca3af", "#f0f2f5", 14))
        self._btn_toggle_preview_sub.setToolTip("Bật hoặc tắt hiển thị khung phụ đề mẫu xem trước trên video")
        self._btn_toggle_preview_sub.setFixedHeight(28)
        self._btn_toggle_preview_sub.clicked.connect(self._toggle_preview_sub)
        left_header.addWidget(self._btn_toggle_preview_sub)
        left_layout.addLayout(left_header)

        self._video_player = VideoPlayerWidget()
        self._video_player.position_changed.connect(self._on_player_pos_changed)
        self._video_player.subtitle_dragged.connect(self._on_subtitle_dragged)
        self._video_player.set_overlay_draggable(True)
        left_layout.addWidget(self._video_player, 1)

        splitter.addWidget(left_widget)

        # Right Column: Subtitle Formatting Controls
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 0, 4, 0)
        right_layout.setSpacing(12)

        btn_reset_style = QPushButton("  Đặt lại")
        btn_reset_style.setIcon(get_icon("rotate-ccw", "#9ca3af", "#f0f2f5", 13))
        btn_reset_style.setToolTip("Khôi phục toàn bộ kiểu dáng về mặc định ban đầu")
        btn_reset_style.setFixedHeight(26)
        btn_reset_style.clicked.connect(self._reset_style_to_default)

        # ── Bento Card 1: Subtitle Typography, Colors & Positioning ──
        card_style = BentoCard("Kiểu dáng phụ đề", "type", header_widget=btn_reset_style)

        grid_font = QGridLayout()
        grid_font.setVerticalSpacing(8)

        grid_font.addWidget(QLabel("Phông:"), 0, 0)
        self._combo_font = QComboBox()
        self._combo_font.addItems(VIETNAMESE_FONTS)
        self._combo_font.currentTextChanged.connect(self._on_style_changed)
        grid_font.addWidget(self._combo_font, 0, 1)

        grid_font.addWidget(QLabel("Cỡ chữ:"), 1, 0)
        self._spin_size = QSpinBox()
        self._spin_size.setRange(14, 80)
        self._spin_size.setValue(26)
        self._spin_size.valueChanged.connect(self._on_style_changed)
        grid_font.addWidget(self._spin_size, 1, 1)

        grid_font.addWidget(QLabel("Căn lề:"), 2, 0)
        self._combo_align = QComboBox()
        self._combo_align.addItem("Căn giữa", "center")
        self._combo_align.addItem("Căn trái", "left")
        self._combo_align.addItem("Căn phải", "right")
        self._combo_align.currentIndexChanged.connect(self._on_style_changed)
        grid_font.addWidget(self._combo_align, 2, 1)

        grid_font.addWidget(QLabel("Màu chữ:"), 3, 0)
        self._btn_text_color = QPushButton(" Màu chữ")
        self._btn_text_color.setIcon(get_icon("palette", "#000000", "#000000", 14))
        self._btn_text_color.setStyleSheet("background-color: #FFFFFF; color: #000000; font-weight: bold;")
        self._btn_text_color.clicked.connect(self._pick_text_color)
        grid_font.addWidget(self._btn_text_color, 3, 1)

        grid_font.addWidget(QLabel("Màu viền:"), 4, 0)
        self._btn_outline_color = QPushButton(" Màu viền")
        self._btn_outline_color.setIcon(get_icon("palette", "#ffffff", "#ffffff", 14))
        self._btn_outline_color.setStyleSheet("background-color: #000000; color: #FFFFFF; font-weight: bold;")
        self._btn_outline_color.clicked.connect(self._pick_outline_color)
        grid_font.addWidget(self._btn_outline_color, 4, 1)

        grid_font.addWidget(QLabel("Độ dày viền:"), 5, 0)
        self._spin_outline_width = QSpinBox()
        self._spin_outline_width.setRange(0, 8)
        self._spin_outline_width.setValue(2)
        self._spin_outline_width.valueChanged.connect(self._on_style_changed)
        grid_font.addWidget(self._spin_outline_width, 5, 1)

        card_style.add_layout(grid_font)



        # Background Box Settings
        grid_box = QGridLayout()
        grid_box.setVerticalSpacing(8)

        self._chk_has_box = SwitchToggle("Bật hộp nền phụ đề", checked=True)
        self._chk_has_box.stateChanged.connect(self._on_style_changed)
        grid_box.addWidget(self._chk_has_box, 0, 0, 1, 2)

        grid_box.addWidget(QLabel("Kiểu dáng:"), 1, 0)
        h_mode = QHBoxLayout()
        self._radio_box_full = QRadioButton("Khung ngang")
        self._radio_box_full.setToolTip("Khung chữ nhật bao trọn bề ngang")
        self._radio_box_wrap = QRadioButton("Ôm chữ")
        self._radio_box_wrap.setToolTip("Hộp nền chỉ bao quanh từng dòng chữ")
        self._radio_box_full.setChecked(True)
        self._radio_box_full.toggled.connect(self._on_box_mode_radio_toggled)
        self._radio_box_wrap.toggled.connect(self._on_box_mode_radio_toggled)
        h_mode.addWidget(self._radio_box_full)
        h_mode.addWidget(self._radio_box_wrap)
        grid_box.addLayout(h_mode, 1, 1)

        grid_box.addWidget(QLabel("Màu nền:"), 2, 0)
        self._btn_box_color = QPushButton(" Màu nền")
        self._btn_box_color.setIcon(get_icon("palette", "#ffffff", "#ffffff", 14))
        self._btn_box_color.setStyleSheet("background-color: #000000; color: #FFFFFF; font-weight: bold;")
        self._btn_box_color.clicked.connect(self._pick_box_color)
        grid_box.addWidget(self._btn_box_color, 2, 1)

        grid_box.addWidget(QLabel("Độ mờ:"), 3, 0)
        h_op = QHBoxLayout()
        self._slider_box_opacity = QSlider(Qt.Orientation.Horizontal)
        self._slider_box_opacity.setRange(0, 100)
        self._slider_box_opacity.setValue(60)
        self._slider_box_opacity.valueChanged.connect(self._on_style_changed)
        h_op.addWidget(self._slider_box_opacity, 1)
        self._lbl_box_opacity_val = QLabel("60%")
        self._lbl_box_opacity_val.setStyleSheet("font-weight: bold; min-width: 40px;")
        h_op.addWidget(self._lbl_box_opacity_val)
        grid_box.addLayout(h_op, 3, 1)

        grid_box.addWidget(QLabel("Bo góc:"), 4, 0)
        h_rad = QHBoxLayout()
        self._slider_box_radius = QSlider(Qt.Orientation.Horizontal)
        self._slider_box_radius.setRange(0, 30)
        self._slider_box_radius.setValue(6)
        self._slider_box_radius.valueChanged.connect(self._on_style_changed)
        h_rad.addWidget(self._slider_box_radius, 1)
        self._lbl_box_radius_val = QLabel("6px")
        self._lbl_box_radius_val.setStyleSheet("font-weight: bold; min-width: 40px;")
        h_rad.addWidget(self._lbl_box_radius_val)
        grid_box.addLayout(h_rad, 4, 1)

        grid_box.addWidget(QLabel("Lề ngang:"), 5, 0)
        h_padx = QHBoxLayout()
        self._slider_pad_x = QSlider(Qt.Orientation.Horizontal)
        self._slider_pad_x.setRange(4, 50)
        self._slider_pad_x.setValue(14)
        self._slider_pad_x.valueChanged.connect(self._on_style_changed)
        h_padx.addWidget(self._slider_pad_x, 1)
        self._lbl_pad_x_val = QLabel("14px")
        self._lbl_pad_x_val.setStyleSheet("font-weight: bold; min-width: 40px;")
        h_padx.addWidget(self._lbl_pad_x_val)
        grid_box.addLayout(h_padx, 5, 1)

        grid_box.addWidget(QLabel("Lề dọc:"), 6, 0)
        h_pady = QHBoxLayout()
        self._slider_pad_y = QSlider(Qt.Orientation.Horizontal)
        self._slider_pad_y.setRange(2, 40)
        self._slider_pad_y.setValue(8)
        self._slider_pad_y.valueChanged.connect(self._on_style_changed)
        h_pady.addWidget(self._slider_pad_y, 1)
        self._lbl_pad_y_val = QLabel("8px")
        self._lbl_pad_y_val.setStyleSheet("font-weight: bold; min-width: 40px;")
        h_pady.addWidget(self._lbl_pad_y_val)
        grid_box.addLayout(h_pady, 6, 1)

        card_style.add_layout(grid_box)

        card_style.add_divider()

        # Position & Width Settings
        grid_pos = QGridLayout()
        grid_pos.setVerticalSpacing(8)

        grid_pos.addWidget(QLabel("Độ rộng:"), 0, 0)
        h_box_w = QHBoxLayout()
        self._slider_box_width = QSlider(Qt.Orientation.Horizontal)
        self._slider_box_width.setRange(40, 95)
        self._slider_box_width.setValue(85)
        self._slider_box_width.valueChanged.connect(self._on_style_changed)
        h_box_w.addWidget(self._slider_box_width, 1)
        self._lbl_box_width_val = QLabel("85%")
        self._lbl_box_width_val.setStyleSheet("font-weight: bold; min-width: 40px;")
        h_box_w.addWidget(self._lbl_box_width_val)
        grid_pos.addLayout(h_box_w, 0, 1)

        lbl_drag_hint = QLabel("💡 <i>Kéo thả trực tiếp khung phụ đề trên màn hình video để đặt vị trí tùy ý.</i>")
        lbl_drag_hint.setStyleSheet("color: #38bdf8; font-size: 11px;")
        lbl_drag_hint.setWordWrap(True)
        grid_pos.addWidget(lbl_drag_hint, 1, 0, 1, 2)

        card_style.add_layout(grid_pos)
        right_layout.addWidget(card_style)

        # ── Bento Card 2: 4-Track Audio Volume & Export Folder ──
        card_audio = BentoCard("Hòa âm & Xuất bản", "sliders")

        grid_audio = QGridLayout()
        grid_audio.setVerticalSpacing(10)

        # 1. Giọng thuyết minh tiếng Việt
        grid_audio.addWidget(QLabel("Thuyết minh:"), 0, 0)
        h_vi = QHBoxLayout()
        self._slider_vi_voice = QSlider(Qt.Orientation.Horizontal)
        self._slider_vi_voice.setRange(0, 200)
        self._slider_vi_voice.setValue(100)
        self._slider_vi_voice.valueChanged.connect(self._on_vi_voice_slider_changed)
        self._slider_vi_voice.sliderReleased.connect(self._apply_vi_boost)
        h_vi.addWidget(self._slider_vi_voice, 1)

        self._lbl_vi_voice_val = QLabel("100%")
        self._lbl_vi_voice_val.setStyleSheet("font-weight: bold; min-width: 45px;")
        h_vi.addWidget(self._lbl_vi_voice_val)
        grid_audio.addLayout(h_vi, 0, 1)

        # 2. Nhạc nền video gốc
        grid_audio.addWidget(QLabel("Nhạc nền:"), 1, 0)
        h_bgm = QHBoxLayout()
        self._slider_orig_bgm = QSlider(Qt.Orientation.Horizontal)
        self._slider_orig_bgm.setRange(0, 100)
        self._slider_orig_bgm.setValue(80)
        self._slider_orig_bgm.valueChanged.connect(self._on_orig_bgm_slider_changed)
        h_bgm.addWidget(self._slider_orig_bgm, 1)

        self._lbl_orig_bgm_val = QLabel("80%")
        self._lbl_orig_bgm_val.setStyleSheet("font-weight: bold; min-width: 45px;")
        h_bgm.addWidget(self._lbl_orig_bgm_val)
        grid_audio.addLayout(h_bgm, 1, 1)

        # 3. Nhạc nền tự chèn
        grid_audio.addWidget(QLabel("Nhạc thêm:"), 2, 0)
        h_bgm_file = QHBoxLayout()
        self._lbl_custom_bgm_name = QLabel("Chưa chọn (dùng nhạc video)")
        self._lbl_custom_bgm_name.setStyleSheet("color: #AAAAAA; font-style: italic;")
        self._lbl_custom_bgm_name.setWordWrap(True)
        h_bgm_file.addWidget(self._lbl_custom_bgm_name, 1)

        self._btn_select_bgm = QPushButton(" Chọn nhạc")
        self._btn_select_bgm.setIcon(get_icon("music", "#9ca3af", "#f0f2f5", 14))
        self._btn_select_bgm.clicked.connect(self._pick_custom_bgm)
        h_bgm_file.addWidget(self._btn_select_bgm)

        self._btn_clear_bgm = QPushButton()
        self._btn_clear_bgm.setIcon(get_icon("close", "#ef4444", "#fca5a5", 13))
        self._btn_clear_bgm.setFixedSize(28, 28)
        self._btn_clear_bgm.setToolTip("Xóa nhạc tự chèn")
        self._btn_clear_bgm.clicked.connect(self._clear_custom_bgm)
        self._btn_clear_bgm.setVisible(False)
        h_bgm_file.addWidget(self._btn_clear_bgm)
        grid_audio.addLayout(h_bgm_file, 2, 1)

        self._lbl_custom_bgm_vol_title = QLabel("Âm lượng nhạc:")
        grid_audio.addWidget(self._lbl_custom_bgm_vol_title, 3, 0)
        h_custom_bgm_vol = QHBoxLayout()
        self._slider_custom_bgm = QSlider(Qt.Orientation.Horizontal)
        self._slider_custom_bgm.setRange(0, 100)
        self._slider_custom_bgm.setValue(50)
        self._slider_custom_bgm.setEnabled(False)
        self._slider_custom_bgm.valueChanged.connect(self._on_custom_bgm_slider_changed)
        h_custom_bgm_vol.addWidget(self._slider_custom_bgm, 1)

        self._lbl_custom_bgm_val = QLabel("50%")
        self._lbl_custom_bgm_val.setStyleSheet("font-weight: bold; min-width: 45px;")
        self._lbl_custom_bgm_val.setEnabled(False)
        h_custom_bgm_vol.addWidget(self._lbl_custom_bgm_val)
        grid_audio.addLayout(h_custom_bgm_vol, 3, 1)

        # 4. Giọng gốc video
        self._chk_orig_voice = SwitchToggle("Chèn giọng gốc", checked=False)
        self._chk_orig_voice.stateChanged.connect(self._on_orig_voice_toggled)
        grid_audio.addWidget(self._chk_orig_voice, 4, 0, 1, 2)

        self._lbl_orig_voice_title = QLabel("Âm lượng giọng:")
        grid_audio.addWidget(self._lbl_orig_voice_title, 5, 0)
        h_orig = QHBoxLayout()
        self._slider_orig_voice = QSlider(Qt.Orientation.Horizontal)
        self._slider_orig_voice.setRange(0, 100)
        self._slider_orig_voice.setValue(0)
        self._slider_orig_voice.setEnabled(False)
        self._slider_orig_voice.valueChanged.connect(self._on_orig_voice_slider_changed)
        h_orig.addWidget(self._slider_orig_voice, 1)

        self._lbl_orig_voice_val = QLabel("0%")
        self._lbl_orig_voice_val.setStyleSheet("font-weight: bold; min-width: 45px;")
        self._lbl_orig_voice_val.setEnabled(False)
        h_orig.addWidget(self._lbl_orig_voice_val)
        grid_audio.addLayout(h_orig, 5, 1)

        card_audio.add_layout(grid_audio)

        card_audio.add_divider()

        # Output Folder row
        h_out_row = QHBoxLayout()
        self._lbl_out_path = QLabel("out/")
        self._lbl_out_path.setStyleSheet("color: #888888; font-size: 11px;")
        h_out_row.addWidget(self._lbl_out_path, 1)

        btn_open_out = QPushButton(" Mở thư mục")
        btn_open_out.setIcon(get_icon("folder", "#9ca3af", "#f0f2f5", 14))
        btn_open_out.clicked.connect(self._open_output_folder)
        h_out_row.addWidget(btn_open_out)

        card_audio.add_layout(h_out_row)

        right_layout.addWidget(card_audio)

        right_layout.addStretch(1)
        right_scroll.setWidget(right_widget)

        splitter.addWidget(right_scroll)
        splitter.setSizes([650, 450])

        main_layout.addWidget(splitter, 1)

        # Initial live preview update
        self._update_overlay()

    # ─── Logic & Slots ────────────────────────────────────────────────────────

    def refresh_jobs(self):
        w = ListJobsWorker()

        def _on_done(jobs: List[dict]):
            self._jobs = jobs
            self._combo_jobs.blockSignals(True)
            self._combo_jobs.clear()
            if not jobs:
                self._combo_jobs.addItem("Không có tác vụ nào", "")
                self._current_job_id = None
            else:
                for j in jobs:
                    jid = j.get("id") or j.get("job_id", "")
                    name = j.get("video_name") or jid
                    self._combo_jobs.addItem(f"{name} ({jid})", jid)

                if self._current_job_id:
                    idx = self._combo_jobs.findData(self._current_job_id)
                    if idx >= 0:
                        self._combo_jobs.setCurrentIndex(idx)
                    else:
                        self._combo_jobs.setCurrentIndex(0)
                else:
                    self._combo_jobs.setCurrentIndex(0)
                self._current_job_id = self._combo_jobs.currentData()
            self._combo_jobs.blockSignals(False)

            if self._current_job_id:
                self._load_job(self._current_job_id)

        w.finished.connect(_on_done)
        self._workers.append(w)
        w.start()

    def set_active_job(self, job_id: str):
        """Externally switch active job and reload."""
        self._current_job_id = job_id
        self.refresh_jobs()

    def _on_job_selected(self, idx: int):
        jid = self._combo_jobs.currentData()
        if jid and jid != self._current_job_id:
            self._current_job_id = jid
            self._load_job(jid)

    def _load_job(self, job_id: str):
        if not job_id:
            return
        w = LoadJobWorker(job_id)

        def _on_loaded(job: dict, segs: list):
            self._segments = segs or []
            # Prioritize: ws_input (clean video for styling & live multi-track preview) > job["video_path"] > ws_preview > rendered
            from dubstudio.paths import resolve_job_workspace, get_out_dir
            ws_dir = resolve_job_workspace(job_id)
            rendered = get_out_dir() / f"{job_id}_vi.mp4"
            ws_preview = ws_dir / "preview_dubbed.mp4"
            ws_input = ws_dir / "input.mp4"
            target_vid = None
            if ws_input.exists():
                target_vid = str(ws_input.resolve())
            elif job.get("video_path") and Path(job["video_path"]).exists():
                target_vid = str(Path(job["video_path"]).resolve())
            elif ws_preview.exists():
                target_vid = str(ws_preview.resolve())
            elif rendered.exists():
                target_vid = str(rendered.resolve())

            if target_vid:
                self._video_player.load_video(target_vid)
                self._preview_sub_visible = True
                self._btn_toggle_preview_sub.setText("  Ẩn phụ đề mẫu")
                self._video_player.set_overlay_preview_visible(True)

            # Load saved style if exists
            style_file = ws_dir / "style.json"
            if style_file.exists():
                try:
                    loaded_style = json.loads(style_file.read_text(encoding="utf-8"))
                    self._apply_style_to_ui(loaded_style)
                except Exception:
                    pass
            # Also load saved mix settings (4 audio stems)
            mix_file = ws_dir / "mix_settings.json"
            if mix_file.exists():
                try:
                    loaded_mix = json.loads(mix_file.read_text(encoding="utf-8"))
                    self._apply_style_to_ui(loaded_mix)
                except Exception:
                    pass

            self._sync_audio_tracks_to_player(is_rendered_video=False)

        w.finished.connect(_on_loaded)
        self._workers.append(w)
        w.start()

    def _sync_audio_tracks_to_player(self, is_rendered_video: bool = False):
        """Prepare video player with 4 multi-track audio stems."""
        if not self._current_job_id:
            return
        from dubstudio.paths import resolve_job_workspace, get_out_dir
        ws_dir = resolve_job_workspace(self._current_job_id)
        if not is_rendered_video:
            ws_input = ws_dir / "input.mp4"
            rendered = get_out_dir() / f"{self._current_job_id}_vi.mp4"
            curr_src = getattr(self._video_player, "_video_path", None)
            if ws_input.exists() and curr_src and rendered.exists():
                try:
                    if Path(curr_src).resolve() == rendered.resolve():
                        pos = self._video_player.get_position()
                        self._video_player.load_video(str(ws_input.resolve()), target_pos=pos)
                except Exception:
                    pass

        vi_vol = float(self._style.get("vi_voice_volume", 1.00))
        orig_bgm_vol = float(self._style.get("orig_bgm_volume", self._style.get("bgm_volume", 0.80)))
        custom_bgm_path = self._style.get("custom_bgm_path")
        custom_bgm_vol = float(self._style.get("custom_bgm_volume", 0.50))
        include_orig = bool(self._style.get("include_orig_voice", False))
        orig_voice_vol = float(self._style.get("orig_voice_volume", 0.00))

        self._video_player.setup_job_audio(
            workspace_dir=ws_dir,
            orig_bgm_vol=orig_bgm_vol,
            custom_bgm_path=custom_bgm_path,
            custom_bgm_vol=custom_bgm_vol,
            include_orig_voice=include_orig,
            orig_voice_vol=orig_voice_vol,
            vi_voice_vol=vi_vol,
            is_rendered_video=is_rendered_video,
        )

    def _apply_style_to_ui(self, st: dict):
        self._style.update(st)
        self._combo_font.blockSignals(True)
        if self._combo_font.findText(self._style["font_name"]) >= 0:
            self._combo_font.setCurrentText(self._style["font_name"])
        self._combo_font.blockSignals(False)

        self._spin_size.blockSignals(True)
        self._spin_size.setValue(int(self._style.get("font_size", 22)))
        self._spin_size.blockSignals(False)

        self._btn_text_color.setStyleSheet(
            f"background-color: {self._style['primary_color']}; color: #000000; font-weight: bold;"
        )
        self._btn_outline_color.setStyleSheet(
            f"background-color: {self._style['outline_color']}; color: #FFFFFF; font-weight: bold;"
        )
        self._spin_outline_width.setValue(int(self._style.get("outline_width", 2)))

        self._chk_has_box.setChecked(bool(self._style.get("has_box", True)))
        self._btn_box_color.setStyleSheet(
            f"background-color: {self._style['box_color']}; color: #FFFFFF; font-weight: bold;"
        )
        if hasattr(self, "_slider_box_opacity"):
            op_pct = int(float(self._style.get("box_opacity", 0.6)) * 100)
            self._slider_box_opacity.blockSignals(True)
            self._slider_box_opacity.setValue(op_pct)
            self._lbl_box_opacity_val.setText(f"{op_pct}%")
            self._slider_box_opacity.blockSignals(False)

        if hasattr(self, "_slider_box_radius"):
            rad = int(self._style.get("box_radius", 6))
            self._slider_box_radius.blockSignals(True)
            self._slider_box_radius.setValue(rad)
            self._lbl_box_radius_val.setText(f"{rad}px")
            self._slider_box_radius.blockSignals(False)

        if hasattr(self, "_slider_pad_x"):
            px = int(self._style.get("box_padding_x", 14))
            self._slider_pad_x.blockSignals(True)
            self._slider_pad_x.setValue(px)
            self._lbl_pad_x_val.setText(f"{px}px")
            self._slider_pad_x.blockSignals(False)

        if hasattr(self, "_slider_pad_y"):
            py = int(self._style.get("box_padding_y", 8))
            self._slider_pad_y.blockSignals(True)
            self._slider_pad_y.setValue(py)
            self._lbl_pad_y_val.setText(f"{py}px")
            self._slider_pad_y.blockSignals(False)

        if hasattr(self, "_radio_box_full") and hasattr(self, "_radio_box_wrap"):
            b_mode = self._style.get("box_mode", "full_width")
            self._radio_box_full.blockSignals(True)
            self._radio_box_wrap.blockSignals(True)
            if b_mode == "wrap_text":
                self._radio_box_wrap.setChecked(True)
                self._radio_box_full.setChecked(False)
            else:
                self._radio_box_full.setChecked(True)
                self._radio_box_wrap.setChecked(False)
            self._radio_box_full.blockSignals(False)
            self._radio_box_wrap.blockSignals(False)

        if hasattr(self, "_slider_box_width"):
            w_val = int(self._style.get("box_width_pct", 85))
            self._slider_box_width.blockSignals(True)
            self._slider_box_width.setValue(w_val)
            self._lbl_box_width_val.setText(f"{w_val}%")
            self._slider_box_width.blockSignals(False)

        # 1. Vi Voice Volume
        if hasattr(self, "_slider_vi_voice"):
            vi_pct = int(float(self._style.get("vi_voice_volume", 1.00)) * 100)
            self._slider_vi_voice.blockSignals(True)
            self._slider_vi_voice.setValue(vi_pct)
            self._lbl_vi_voice_val.setText(f"{vi_pct}%")
            self._slider_vi_voice.blockSignals(False)
            if hasattr(self, "_video_player") and self._video_player:
                self._video_player.set_vi_voice_volume(vi_pct / 100.0)

        # 2. Original Video BGM Volume
        if hasattr(self, "_slider_orig_bgm"):
            bgm_pct = int(float(self._style.get("orig_bgm_volume", self._style.get("bgm_volume", 0.80))) * 100)
            self._slider_orig_bgm.blockSignals(True)
            self._slider_orig_bgm.setValue(bgm_pct)
            self._lbl_orig_bgm_val.setText(f"{bgm_pct}%")
            self._slider_orig_bgm.blockSignals(False)
            if hasattr(self, "_video_player") and self._video_player:
                self._video_player.set_orig_bgm_volume(bgm_pct / 100.0)

        # 3. Custom BGM & Volume
        c_bgm = self._style.get("custom_bgm_path")
        has_custom = bool(c_bgm and Path(c_bgm).exists())
        if hasattr(self, "_lbl_custom_bgm_name"):
            if has_custom:
                self._lbl_custom_bgm_name.setText(Path(c_bgm).name)
                self._lbl_custom_bgm_name.setStyleSheet("color: #4cd964; font-weight: bold;")
                self._btn_clear_bgm.setVisible(True)
                self._slider_custom_bgm.setEnabled(True)
                self._lbl_custom_bgm_val.setEnabled(True)
                if hasattr(self, "_video_player") and self._video_player:
                    self._video_player.set_custom_bgm(c_bgm, float(self._style.get("custom_bgm_volume", 0.50)))
            else:
                self._lbl_custom_bgm_name.setText("Chưa chọn (dùng nhạc video)")
                self._lbl_custom_bgm_name.setStyleSheet("color: #AAAAAA; font-style: italic;")
                self._btn_clear_bgm.setVisible(False)
                self._slider_custom_bgm.setEnabled(False)
                self._lbl_custom_bgm_val.setEnabled(False)
                if hasattr(self, "_video_player") and self._video_player:
                    self._video_player.set_custom_bgm(None, float(self._style.get("custom_bgm_volume", 0.50)))

        if hasattr(self, "_slider_custom_bgm"):
            c_bgm_pct = int(float(self._style.get("custom_bgm_volume", 0.50)) * 100)
            self._slider_custom_bgm.blockSignals(True)
            self._slider_custom_bgm.setValue(c_bgm_pct)
            self._lbl_custom_bgm_val.setText(f"{c_bgm_pct}%")
            self._slider_custom_bgm.blockSignals(False)

        # 4. Original Voice (Vocals)
        if hasattr(self, "_chk_orig_voice"):
            inc_orig = bool(self._style.get("include_orig_voice", False))
            self._chk_orig_voice.blockSignals(True)
            self._chk_orig_voice.setChecked(inc_orig)
            self._chk_orig_voice.blockSignals(False)
            self._slider_orig_voice.setEnabled(inc_orig)
            self._lbl_orig_voice_val.setEnabled(inc_orig)
            self._lbl_orig_voice_title.setEnabled(inc_orig)

        if hasattr(self, "_slider_orig_voice"):
            orig_pct = int(float(self._style.get("orig_voice_volume", 0.00)) * 100)
            self._slider_orig_voice.blockSignals(True)
            self._slider_orig_voice.setValue(orig_pct)
            self._lbl_orig_voice_val.setText(f"{orig_pct}%")
            self._slider_orig_voice.blockSignals(False)
            if hasattr(self, "_video_player") and self._video_player:
                self._video_player.set_orig_voice_volume(orig_pct / 100.0, bool(self._style.get("include_orig_voice", False)))

        self._update_overlay()

    def _toggle_preview_sub(self):
        """Toggle sample subtitle overlay visibility on video preview."""
        self._preview_sub_visible = not self._preview_sub_visible
        if self._preview_sub_visible:
            self._btn_toggle_preview_sub.setText("  Ẩn phụ đề mẫu")
        else:
            self._btn_toggle_preview_sub.setText("  Hiện phụ đề mẫu")
        if hasattr(self, "_video_player") and self._video_player:
            self._video_player.set_overlay_preview_visible(self._preview_sub_visible)

    def _on_vi_voice_slider_changed(self, val: int):
        self._lbl_vi_voice_val.setText(f"{val}%")
        vol = val / 100.0
        self._style["vi_voice_volume"] = vol
        if hasattr(self, "_video_player") and self._video_player:
            if not getattr(self._video_player, "_multi_track_active", False) and self._current_job_id:
                self._sync_audio_tracks_to_player(is_rendered_video=False)
            self._video_player.set_vi_voice_volume(vol)
        self._save_style_to_job()

    def _apply_vi_boost(self):
        if hasattr(self, "_slider_vi_voice") and hasattr(self, "_video_player") and self._video_player:
            self._video_player.set_vi_voice_volume(self._slider_vi_voice.value() / 100.0)

    def _on_orig_bgm_slider_changed(self, val: int):
        self._lbl_orig_bgm_val.setText(f"{val}%")
        vol = val / 100.0
        self._style["orig_bgm_volume"] = vol
        self._style["bgm_volume"] = vol
        if hasattr(self, "_video_player") and self._video_player:
            if not getattr(self._video_player, "_multi_track_active", False) and self._current_job_id:
                self._sync_audio_tracks_to_player(is_rendered_video=False)
            self._video_player.set_orig_bgm_volume(vol)
        self._save_style_to_job()

    def _pick_custom_bgm(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn tệp âm thanh / nhạc nền",
            "",
            "Audio Files (*.mp3 *.wav *.m4a *.aac *.flac *.ogg);;All Files (*)",
        )
        if file_path:
            self._style["custom_bgm_path"] = file_path
            self._lbl_custom_bgm_name.setText(Path(file_path).name)
            self._lbl_custom_bgm_name.setStyleSheet("color: #4cd964; font-weight: bold;")
            self._btn_clear_bgm.setVisible(True)
            self._slider_custom_bgm.setEnabled(True)
            self._lbl_custom_bgm_val.setEnabled(True)
            vol = float(self._style.get("custom_bgm_volume", 0.50))
            if hasattr(self, "_video_player") and self._video_player:
                if not getattr(self._video_player, "_multi_track_active", False) and self._current_job_id:
                    self._sync_audio_tracks_to_player(is_rendered_video=False)
                self._video_player.set_custom_bgm(file_path, vol)
            self._save_style_to_job()

    def _clear_custom_bgm(self):
        self._style["custom_bgm_path"] = None
        self._lbl_custom_bgm_name.setText("Chưa chọn (dùng nhạc video)")
        self._lbl_custom_bgm_name.setStyleSheet("color: #AAAAAA; font-style: italic;")
        self._btn_clear_bgm.setVisible(False)
        self._slider_custom_bgm.setEnabled(False)
        self._lbl_custom_bgm_val.setEnabled(False)
        if hasattr(self, "_video_player") and self._video_player:
            self._video_player.set_custom_bgm(None, float(self._style.get("custom_bgm_volume", 0.50)))
        self._save_style_to_job()

    def _on_custom_bgm_slider_changed(self, val: int):
        self._lbl_custom_bgm_val.setText(f"{val}%")
        vol = val / 100.0
        self._style["custom_bgm_volume"] = vol
        if hasattr(self, "_video_player") and self._video_player:
            if not getattr(self._video_player, "_multi_track_active", False) and self._current_job_id:
                self._sync_audio_tracks_to_player(is_rendered_video=False)
            self._video_player.set_custom_bgm_volume(vol)
        self._save_style_to_job()

    def _on_orig_voice_toggled(self, state: int):
        checked = self._chk_orig_voice.isChecked()
        self._slider_orig_voice.setEnabled(checked)
        self._lbl_orig_voice_val.setEnabled(checked)
        self._lbl_orig_voice_title.setEnabled(checked)
        self._style["include_orig_voice"] = checked
        vol = float(self._style.get("orig_voice_volume", 0.00))
        if hasattr(self, "_video_player") and self._video_player:
            if not getattr(self._video_player, "_multi_track_active", False) and self._current_job_id:
                self._sync_audio_tracks_to_player(is_rendered_video=False)
            self._video_player.set_orig_voice_volume(vol, checked)
        self._save_style_to_job()

    def _on_orig_voice_slider_changed(self, val: int):
        self._lbl_orig_voice_val.setText(f"{val}%")
        vol = val / 100.0
        self._style["orig_voice_volume"] = vol
        if hasattr(self, "_video_player") and self._video_player:
            if not getattr(self._video_player, "_multi_track_active", False) and self._current_job_id:
                self._sync_audio_tracks_to_player(is_rendered_video=False)
            self._video_player.set_orig_voice_volume(vol, self._chk_orig_voice.isChecked())
        self._save_style_to_job()

    def _on_box_mode_radio_toggled(self):
        if hasattr(self, "_radio_box_wrap") and self._radio_box_wrap.isChecked():
            self._style["box_mode"] = "wrap_text"
        else:
            self._style["box_mode"] = "full_width"
        self._update_overlay()

    def _on_style_changed(self):
        self._style["font_name"] = self._combo_font.currentText()
        self._style["font_size"] = self._spin_size.value()
        self._style["outline_width"] = self._spin_outline_width.value()
        self._style["has_box"] = self._chk_has_box.isChecked()
        if hasattr(self, "_slider_box_opacity"):
            op_pct = self._slider_box_opacity.value()
            self._style["box_opacity"] = op_pct / 100.0
            self._lbl_box_opacity_val.setText(f"{op_pct}%")
        if hasattr(self, "_slider_box_radius"):
            rad = self._slider_box_radius.value()
            self._style["box_radius"] = rad
            self._lbl_box_radius_val.setText(f"{rad}px")
        if hasattr(self, "_slider_pad_x"):
            px = self._slider_pad_x.value()
            self._style["box_padding_x"] = px
            self._lbl_pad_x_val.setText(f"{px}px")
        if hasattr(self, "_slider_pad_y"):
            py = self._slider_pad_y.value()
            self._style["box_padding_y"] = py
            self._lbl_pad_y_val.setText(f"{py}px")
        if hasattr(self, "_radio_box_wrap") and self._radio_box_wrap.isChecked():
            self._style["box_mode"] = "wrap_text"
        else:
            self._style["box_mode"] = "full_width"
        self._style["text_align"] = self._combo_align.currentData() or "center"
        if hasattr(self, "_slider_box_width"):
            self._style["box_width_pct"] = self._slider_box_width.value()
            self._lbl_box_width_val.setText(f"{self._slider_box_width.value()}%")

        self._update_overlay()
        self._save_style_to_job()

    def _update_overlay(self):
        sample_text = "Xin chào! Đây là phụ đề mẫu tiếng Việt."
        if hasattr(self, "_video_player") and self._video_player:
            # Preserve currently displayed segment text to prevent height change and vertical position jumps
            cur_text = getattr(self._video_player, "_overlay_text", None)
            text_to_show = cur_text if (cur_text and cur_text.strip()) else sample_text
            self._video_player.update_subtitle_overlay(
                text_to_show, self._style, visible=self._preview_sub_visible
            )

    def showEvent(self, event):
        super().showEvent(event)
        self._update_overlay()

    def _on_subtitle_dragged(self, data: dict):
        """Handle subtitle repositioning dragged by user directly on the video screen."""
        if "pos_y_pct" in data:
            self._style["pos_y_pct"] = float(data["pos_y_pct"])
        if "position" in data:
            self._style["position"] = data["position"]
        if "margin_v" in data:
            self._style["margin_v"] = int(data["margin_v"])

        if "box_width_pct" in data:
            w_val = int(round(float(data["box_width_pct"])))
            self._style["box_width_pct"] = w_val
            if hasattr(self, "_slider_box_width"):
                self._slider_box_width.blockSignals(True)
                self._slider_box_width.setValue(w_val)
                self._lbl_box_width_val.setText(f"{w_val}%")
                self._slider_box_width.blockSignals(False)

        self._update_overlay()
        self._save_style_to_job()

    def _on_player_pos_changed(self, sec: float):
        if not hasattr(self, "_video_player") or not self._video_player:
            return
        from dubstudio.subtitles.ass import get_segment_slices
        current_text = None

        # Prioritize later segment over earlier segment so upcoming subtitle strictly overrides overlapping previous subtitle
        segments = getattr(self, "_segments", [])
        for i, seg in enumerate(segments):
            st = float(seg.get("start", 0.0))
            en = float(seg.get("end", 0.0))
            # Bound end with next segment start to prevent overlapping text display
            if i + 1 < len(segments):
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

        display_text = current_text if current_text else "Xin chào! Đây là phụ đề mẫu tiếng Việt."
        self._video_player.update_subtitle_overlay(
            display_text, self._style, visible=self._preview_sub_visible
        )

    def _save_style_to_job(self):
        # Debounce high-frequency slider movements; UI visual preview updates immediately
        if hasattr(self, "_save_debounce_timer"):
            self._save_debounce_timer.start()
        else:
            self._do_async_save_style()

    def _do_async_save_style(self):
        if not hasattr(self, "_style"):
            return
        style_copy = dict(self._style)
        job_id = self._current_job_id

        def _bg_save():
            # 1. Global preset write
            try:
                GLOBAL_PRESET_FILE.parent.mkdir(parents=True, exist_ok=True)
                GLOBAL_PRESET_FILE.write_text(json.dumps(style_copy, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

            if not job_id:
                return

            # 2. Workspace style and mix_settings
            try:
                from dubstudio.paths import resolve_job_workspace
                ws_dir = resolve_job_workspace(job_id)
                ws_dir.mkdir(parents=True, exist_ok=True)

                ws_style = ws_dir / "style.json"
                ws_style.write_text(json.dumps(style_copy, ensure_ascii=False, indent=2), encoding="utf-8")

                mix_file = ws_dir / "mix_settings.json"
                orig_bgm_vol = float(style_copy.get("orig_bgm_volume", style_copy.get("bgm_volume", 0.80)))
                existing_ranges = []
                if mix_file.exists():
                    try:
                        old_mix = json.loads(mix_file.read_text(encoding="utf-8"))
                        existing_ranges = old_mix.get("keep_original_ranges", [])
                    except Exception:
                        pass
                ranges_file = ws_dir / "orig_audio_ranges.json"
                if not existing_ranges and ranges_file.exists():
                    try:
                        r_raw = json.loads(ranges_file.read_text(encoding="utf-8"))
                        existing_ranges = [[float(r["start"]), float(r["end"])] for r in r_raw if "start" in r and "end" in r]
                    except Exception:
                        pass

                mix_file.write_text(
                    json.dumps(
                        {
                            "orig_bgm_volume": orig_bgm_vol,
                            "bgm_volume": orig_bgm_vol,
                            "custom_bgm_path": style_copy.get("custom_bgm_path"),
                            "custom_bgm_volume": float(style_copy.get("custom_bgm_volume", 0.50)),
                            "include_orig_voice": bool(style_copy.get("include_orig_voice", False)),
                            "orig_voice_volume": float(style_copy.get("orig_voice_volume", 0.00)),
                            "vi_voice_volume": float(style_copy.get("vi_voice_volume", 1.00)),
                            "keep_original_ranges": existing_ranges,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            except Exception:
                pass

            # 3. Notify API server via shared pooled session
            try:
                from ui.workers import get_shared_session, get_base_url
                sess = get_shared_session()
                sess.post(
                    f"{get_base_url()}/api/jobs/{job_id}/style",
                    json=style_copy,
                    timeout=2,
                )
            except Exception:
                pass

        import threading
        threading.Thread(target=_bg_save, daemon=True).start()

    def _reset_style_to_default(self):
        """Reset subtitle formatting to factory default settings."""
        self._style = dict(FACTORY_STYLE)
        self._apply_style_to_ui(self._style)
        self._save_style_to_job()


    def _pick_text_color(self):
        c = QColorDialog.getColor(QColor(self._style["primary_color"]), self, "Chọn màu chữ chính")
        if c.isValid():
            hex_color = c.name().upper()
            self._style["primary_color"] = hex_color
            self._btn_text_color.setStyleSheet(
                f"background-color: {hex_color}; color: #000000; font-weight: bold;"
            )
            self._on_style_changed()

    def _pick_outline_color(self):
        c = QColorDialog.getColor(QColor(self._style["outline_color"]), self, "Chọn màu viền chữ")
        if c.isValid():
            hex_color = c.name().upper()
            self._style["outline_color"] = hex_color
            self._btn_outline_color.setStyleSheet(
                f"background-color: {hex_color}; color: #FFFFFF; font-weight: bold;"
            )
            self._on_style_changed()

    def _pick_box_color(self):
        c = QColorDialog.getColor(QColor(self._style["box_color"]), self, "Chọn màu hộp nền")
        if c.isValid():
            hex_color = c.name().upper()
            self._style["box_color"] = hex_color
            self._btn_box_color.setStyleSheet(
                f"background-color: {hex_color}; color: #FFFFFF; font-weight: bold;"
            )
            self._on_style_changed()

    def _on_goto_merge(self):
        """Save subtitle style preset, generate fresh ASS file, and transition to Tab 4 (Xuất video)."""
        if not self._current_job_id:
            QMessageBox.warning(self, "Chưa chọn tác vụ", "Vui lòng chọn một tác vụ trước!")
            return

        self._save_style_to_job()

        # Find best candidate video to send to merge page
        from dubstudio.paths import resolve_job_workspace, get_out_dir
        ws_dir = resolve_job_workspace(self._current_job_id)
        rendered_mp4 = get_out_dir() / f"{self._current_job_id}_vi.mp4"

        prev_dub = ws_dir / "preview_dubbed.mp4"
        in_mp4 = ws_dir / "input.mp4"

        # Generate and save fresh ASS subtitles so downstream render in Tab 4 has exact styling
        try:
            from dubstudio.subtitles.ass import generate_ass_subtitles
            from dubstudio.ffmpeg_utils import probe_file
            seg_file = ws_dir / "segments.json"
            if seg_file.exists():
                segs = json.loads(seg_file.read_text(encoding="utf-8")).get("segments", [])
                ass_file = ws_dir / "subtitles.ass"
                vid_w, vid_h = 1280, 720
                ref_vid = in_mp4 if in_mp4.exists() else (prev_dub if prev_dub.exists() else None)
                if ref_vid and ref_vid.exists():
                    try:
                        pinfo = probe_file(ref_vid)
                        for s in pinfo.get("streams", []):
                            if s.get("codec_type") == "video":
                                vid_w = int(s.get("width") or 1280)
                                vid_h = int(s.get("height") or 720)
                                break
                    except Exception:
                        pass
                generate_ass_subtitles(segs, ass_file, style=self._style, video_width=vid_w, video_height=vid_h)
        except Exception:
            pass

        target_vid = ""
        if rendered_mp4.exists():
            target_vid = str(rendered_mp4.resolve())
        elif prev_dub.exists():
            target_vid = str(prev_dub.resolve())
        elif in_mp4.exists():
            target_vid = str(in_mp4.resolve())

        self.goto_merge_requested.emit(target_vid, self._current_job_id)

    def _start_render(self):
        if not self._current_job_id:
            QMessageBox.warning(self, "Chưa chọn tác vụ", "Vui lòng chọn một tác vụ để xuất video!")
            return

        # Check if any segments are missing TTS audio and confirm with user
        from dubstudio.paths import resolve_job_workspace
        ws_dir = resolve_job_workspace(self._current_job_id)
        seg_file = ws_dir / "segments.json"
        if seg_file.exists():
            try:
                segs = json.loads(seg_file.read_text(encoding="utf-8")).get("segments", [])
                missing_tts_ids = []
                for s in segs:
                    sid = s.get("id")
                    if sid is None:
                        continue
                    if s.get("mute_tts") or s.get("keep_original"):
                        continue
                    # Check candidate locations
                    w_file = ws_dir / f"tts/{sid:04d}.wav"
                    w_stretched = ws_dir / f"tts_stretched/{sid:04d}.wav"
                    w_custom = ws_dir / str(s.get("tts_file", "")) if s.get("tts_file") else None

                    has_audio = (
                        (w_file.exists() and w_file.stat().st_size > 500) or
                        (w_stretched.exists() and w_stretched.stat().st_size > 500) or
                        (w_custom and w_custom.exists() and w_custom.stat().st_size > 500)
                    )
                    if not has_audio:
                        missing_tts_ids.append(str(sid))
                if missing_tts_ids:
                    msg = (
                        f"Phát hiện các lời thoại số: {', '.join(missing_tts_ids)} chưa được tạo âm thanh lồng tiếng (TTS).\n\n"
                        f"Phụ đề vẫn sẽ xuất hiện đầy đủ trên video nhưng không có âm thanh lồng tiếng cho các câu này.\n\n"
                        f"Bạn có muốn tiếp tục xuất video không?"
                    )
                    reply = QMessageBox.question(
                        self,
                        "Cảnh báo lời thoại chưa có TTS",
                        msg,
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        return
            except Exception:
                pass

        # Ensure latest style is saved
        self._save_style_to_job()

        # Invalidate old render stage and mix stage in state.json so it always re-mixes & re-renders with new style/audio
        try:
            ws_state = ws_dir / "state.json"
            if ws_state.exists():
                st_data = json.loads(ws_state.read_text(encoding="utf-8"))
                if "stages" in st_data:
                    st_data["stages"].pop("render", None)
                    st_data["stages"].pop("mix", None)
                    ws_state.write_text(json.dumps(st_data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

        # Unload video player so ffmpeg can overwrite the output video without Windows lock
        self._video_player.unload()

        self._btn_render.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setRange(0, 0)  # indeterminate pulse
        self._lbl_status.setText("Đang kết xuất video và khắc phụ đề ASS...")

        w = RenderVideoWorker(self._current_job_id)

        def _on_done(res: dict):
            self._btn_render.setEnabled(True)
            self._progress_bar.setVisible(False)
            self._lbl_status.setText("✓ Xuất video hoàn tất thành công!")

            # Terminate TTS worker process to free all RAM & VRAM
            w_stop = StopTTSWorker()
            self._workers.append(w_stop)
            w_stop.start()

            # Automatically hide sample subtitle overlay after render finishes
            self._preview_sub_visible = False
            self._btn_toggle_preview_sub.setText("  Hiện phụ đề mẫu")
            if hasattr(self, "_video_player") and self._video_player:
                self._video_player.set_overlay_preview_visible(False)

            vid_path = res.get("video_path")
            if vid_path and Path(vid_path).exists():
                self._video_player.load_video(vid_path)

            msg = QMessageBox(self)
            msg.setWindowTitle("Xuất video thành công")
            msg.setText(f"Đã xuất thành công video có phụ đề và lồng tiếng:\n\n{res.get('filename')}")
            btn_play = msg.addButton("Xem video", QMessageBox.ButtonRole.AcceptRole)
            btn_folder = msg.addButton("Mở thư mục", QMessageBox.ButtonRole.ActionRole)
            msg.addButton(QMessageBox.StandardButton.Close)

            msg.exec()
            if msg.clickedButton() == btn_play:
                if vid_path and Path(vid_path).exists():
                    self._video_player.play()
            elif msg.clickedButton() == btn_folder:
                self._open_output_folder()

        def _on_err(err: str):
            self._btn_render.setEnabled(True)
            self._progress_bar.setVisible(False)
            self._lbl_status.setText("Lỗi xuất video")
            QMessageBox.critical(self, "Lỗi xuất video", f"Không thể xuất video: {err}")

        w.finished.connect(_on_done)
        w.error.connect(_on_err)
        self._workers.append(w)
        w.start()

    def _open_output_folder(self):
        out_path = Path("out").resolve()
        out_path.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(out_path))
        else:
            subprocess.run(["xdg-open", str(out_path)])

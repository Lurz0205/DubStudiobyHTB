"""Studio Page: Splitter with top (Video preview + Subtitle table) and bottom (Timeline drag/drop)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QPoint, Qt, QUrl, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtGui import QKeySequence, QShortcut

from dubstudio.config import AppConfig
from ui.icons import get_icon
from ui.theme import COLORS
from ui.widgets.switch import SwitchToggle
from ui.widgets.subtitle_editor import FindReplaceBar, SubtitleEditorWidget, ALL_VOICES, MALE_VOICES, FEMALE_VOICES
from ui.widgets.timeline_ruler import TimelineWidget
from ui.widgets.video_player import VideoPlayerWidget
from ui.workers import (
    BatchDeleteSegmentsWorker,
    BatchUpdateSegmentsWorker,
    CreateJobWorker,
    CreateSegmentWorker,
    DeleteSegmentWorker,
    ListJobsWorker,
    LoadJobWorker,
    MergeSegmentsWorker,
    RegenTTSWorker,
    RunPipelineWorker,
    SplitSegmentWorker,
    UpdateSegmentWorker,
    WarmTTSWorker,
)


class EditSegmentDialog(QDialog):
    """
    Comprehensive Popup Dialog for Editing a Subtitle & Dubbing Segment:
    - Timeline: Start & End time spinboxes with duration display.
    - Chinese Source (ZH): Read-only selectable text + 1-click 'Sao chép' button.
    - Vietnamese Translation (VI): Editable text with Enter line-breaking for slice subdivision.
    - Speed Rate (TTS): Spinbox to fine-tune playback tempo (0.5x - 2.0x).
    """
    def __init__(self, segment: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Chỉnh sửa câu thoại #{segment.get('id', '')}")
        self.setMinimumWidth(640)
        self._segment = segment
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 16, 18, 16)

        start = float(self._segment.get("start", 0.0))
        end = float(self._segment.get("end", 0.0))
        total_dur = max(0.1, round(end - start, 3))
        zh_text = str(self._segment.get("src_text") or self._segment.get("zh") or self._segment.get("zh_text") or "").strip()
        vi_text = str(self._segment.get("vi_text") or "").strip()
        fit_info = self._segment.get("fit") if isinstance(self._segment.get("fit"), dict) else {}
        speed_val = self._segment.get("speed")
        if speed_val is None:
            speed_val = fit_info.get("rate", 1.0)
        speed = float(speed_val or 1.0)

        # 1. Header with title
        hdr = QHBoxLayout()
        lbl_title = QLabel(f"<b>Chỉnh sửa câu thoại #{self._segment.get('id', '')}</b>")
        lbl_title.setStyleSheet("font-size: 14px; color: #38bdf8; font-weight: 700;")
        hdr.addWidget(lbl_title)
        hdr.addStretch(1)
        layout.addLayout(hdr)

        # 2. Timeline & Speed row (Card-style)
        time_card = QFrame()
        time_card.setObjectName("card")
        time_layout = QHBoxLayout(time_card)
        time_layout.setContentsMargins(12, 8, 12, 8)
        time_layout.setSpacing(12)

        time_layout.addWidget(QLabel("<b>Bắt đầu (s):</b>"))
        self._spin_start = QDoubleSpinBox()
        self._spin_start.setRange(0.0, 99999.0)
        self._spin_start.setDecimals(2)
        self._spin_start.setSingleStep(0.1)
        self._spin_start.setValue(start)
        self._spin_start.setFixedHeight(28)
        self._spin_start.setFixedWidth(85)
        self._spin_start.valueChanged.connect(self._on_time_changed)
        time_layout.addWidget(self._spin_start)

        time_layout.addWidget(QLabel("<b>Kết thúc (s):</b>"))
        self._spin_end = QDoubleSpinBox()
        self._spin_end.setRange(0.0, 99999.0)
        self._spin_end.setDecimals(2)
        self._spin_end.setSingleStep(0.1)
        self._spin_end.setValue(end)
        self._spin_end.setFixedHeight(28)
        self._spin_end.setFixedWidth(85)
        self._spin_end.valueChanged.connect(self._on_time_changed)
        time_layout.addWidget(self._spin_end)

        self._lbl_dur = QLabel(f"Độ dài: {total_dur:.2f}s")
        self._lbl_dur.setStyleSheet(f"color: {COLORS['accent']}; font-size: 12px; font-weight: 600;")
        time_layout.addWidget(self._lbl_dur)

        time_layout.addStretch(1)

        time_layout.addWidget(QLabel("<b>Tốc độ đọc:</b>"))
        self._spin_speed = QDoubleSpinBox()
        self._spin_speed.setRange(0.5, 2.0)
        self._spin_speed.setDecimals(2)
        self._spin_speed.setSingleStep(0.05)
        self._spin_speed.setValue(speed)
        self._spin_speed.setFixedHeight(28)
        self._spin_speed.setFixedWidth(75)
        self._spin_speed.setSuffix("x")
        time_layout.addWidget(self._spin_speed)

        layout.addWidget(time_card)

        # 3. Chinese Source Text (Readonly + Copiable)
        zh_hdr = QHBoxLayout()
        lbl_zh = QLabel("<b>Nguồn tiếng Trung (chỉ đọc, cho phép chọn sao chép):</b>")
        lbl_zh.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11.5px;")
        zh_hdr.addWidget(lbl_zh)
        zh_hdr.addStretch(1)

        btn_copy_zh = QPushButton(" Sao chép")
        btn_copy_zh.setIcon(get_icon("copy", "#9ca3af", "#f0f2f5", 13))
        btn_copy_zh.setObjectName("compact")
        btn_copy_zh.setFixedHeight(26)
        btn_copy_zh.setToolTip("Sao chép câu tiếng Trung vào Clipboard")
        btn_copy_zh.clicked.connect(self._copy_zh_text)
        zh_hdr.addWidget(btn_copy_zh)
        layout.addLayout(zh_hdr)

        self._txt_zh = QTextEdit()
        self._txt_zh.setPlainText(zh_text)
        self._txt_zh.setReadOnly(True)
        self._txt_zh.setFixedHeight(50)
        layout.addWidget(self._txt_zh)

        # 4. Vietnamese Translation & Line-splitting
        cues = self._segment.get("cues")
        sub_slices = self._segment.get("sub_slices")
        combined_cues_text = " ".join(c.get("text", "").strip() for c in cues if isinstance(c, dict)) if (cues and isinstance(cues, list)) else ""
        combined_vi_text = " ".join(vi_text.split())
        if cues and isinstance(cues, list) and len(cues) > 1 and combined_cues_text == combined_vi_text:
            initial_text = "\n".join(c.get("text", "").strip() for c in cues if c.get("text", "").strip())
        elif sub_slices and isinstance(sub_slices, list) and len(sub_slices) > 1:
            initial_text = "\n".join(s.get("text", "").strip() for s in sub_slices if s.get("text", "").strip())
        elif "\n" in vi_text and len(vi_text.splitlines()) > 1:
            initial_text = vi_text
        else:
            initial_text = vi_text

        vi_hdr_box = QHBoxLayout()
        lbl_vi_hdr = QLabel("<b>Bản dịch tiếng Việt (Nhấn Enter để tách dòng nhịp câu):</b>")
        lbl_vi_hdr.setStyleSheet(f"color: {COLORS['text']}; font-size: 11.5px;")
        vi_hdr_box.addWidget(lbl_vi_hdr)
        vi_hdr_box.addStretch(1)

        btn_auto_break = QPushButton(" Tự động ngắt dòng")
        btn_auto_break.setIcon(get_icon("scissors", "#9ca3af", "#f0f2f5", 12))
        btn_auto_break.setObjectName("compact")
        btn_auto_break.setFixedHeight(26)
        btn_auto_break.setToolTip("Tự động ngắt câu này thành các dòng theo quy tắc độ dài từ")
        btn_auto_break.clicked.connect(self._auto_split_this_sentence)
        vi_hdr_box.addWidget(btn_auto_break)
        layout.addLayout(vi_hdr_box)

        self._txt_vi = QTextEdit()
        self._txt_vi.setPlainText(initial_text)
        self._txt_vi.setMinimumHeight(100)
        self._txt_vi.textChanged.connect(self._update_calculation)
        layout.addWidget(self._txt_vi)

        # 5. Calculation Banner
        self._lbl_calc = QLabel()
        self._lbl_calc.setStyleSheet(
            f"background-color: {COLORS['accent_dim']}; "
            f"border: 1px solid {COLORS['accent_border']}; "
            f"border-radius: 8px; padding: 8px 12px; color: {COLORS['accent']}; font-size: 11.5px;"
        )
        self._lbl_calc.setWordWrap(True)
        layout.addWidget(self._lbl_calc)

        # 6. Action buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch(1)

        btn_cancel = QPushButton("Hủy")
        btn_cancel.setFixedHeight(30)
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        self._btn_ok = QPushButton(" Lưu thay đổi")
        self._btn_ok.setIcon(get_icon("check", "#ffffff", "#ffffff", 14))
        self._btn_ok.setObjectName("primary")
        self._btn_ok.setFixedHeight(30)
        self._btn_ok.clicked.connect(self.accept)
        btn_box.addWidget(self._btn_ok)

        layout.addLayout(btn_box)
        self._update_calculation()

    def _copy_zh_text(self):
        text = self._txt_zh.toPlainText().strip()
        if text:
            from PyQt6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText(text)

    def _on_time_changed(self):
        st = self._spin_start.value()
        en = self._spin_end.value()
        dur = max(0.1, round(en - st, 2))
        self._lbl_dur.setText(f"Độ dài: {dur:.2f}s")
        self._update_calculation()

    def _auto_split_this_sentence(self):
        full_text = self._txt_vi.toPlainText().replace("\n", " ").strip()
        if not full_text:
            return
        st = self._spin_start.value()
        en = self._spin_end.value()
        from dubstudio.subtitles.cue_split import split_sentence_cues
        cues = split_sentence_cues(full_text, st, en, target_n=6)
        if cues and len(cues) > 1:
            self._txt_vi.setPlainText("\n".join(c["text"] for c in cues))

    def _update_calculation(self):
        text = self._txt_vi.toPlainText()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        start = self._spin_start.value()
        end = self._spin_end.value()
        total_dur = max(0.1, end - start)

        if len(lines) == 0:
            self._lbl_calc.setText("<i>Vui lòng nhập nội dung câu phụ đề.</i>")
            self._btn_ok.setEnabled(False)
            return

        self._btn_ok.setEnabled(True)
        if len(lines) == 1:
            self._lbl_calc.setText(
                "<b>Trạng thái:</b> Câu đang ở dạng 1 dòng nguyên vẹn.<br>"
                "<i>Gợi ý: Đặt con trỏ và nhấn <b>Enter</b> để chia thành các lát cắt ngắn hiển thị lần lượt trên màn hình và timeline.</i>"
            )
            self._btn_ok.setText("Lưu thay đổi (1 dòng)")
            return

        self._btn_ok.setText(f"Lưu thay đổi ({len(lines)} lát cắt)")
        word_counts = [max(1, len(l.split())) for l in lines]
        total_words = sum(word_counts)

        parts_desc = []
        curr_t = start
        for idx, (l, wc) in enumerate(zip(lines, word_counts), start=1):
            if idx == len(lines):
                seg_end = end
            else:
                dur = round(total_dur * (wc / total_words), 2)
                seg_end = round(curr_t + dur, 2)
                seg_end = max(curr_t + 0.1, min(end - 0.1 * (len(lines) - idx), seg_end))

            parts_desc.append(
                f"• <b>Lát cắt {idx}:</b> {wc} từ (~{seg_end - curr_t:.2f}s: <code>{curr_t:.2f}s ➔ {seg_end:.2f}s</code>) — <i>\"{l}\"</i>"
            )
            curr_t = seg_end

        self._lbl_calc.setText(
            f"<b>Ước tính thời lượng của {len(lines)} lát cắt trên màn hình:</b><br>"
            + "<br>".join(parts_desc)
        )

    def get_times(self) -> Tuple[float, float]:
        st = round(self._spin_start.value(), 2)
        en = round(max(st + 0.1, self._spin_end.value()), 2)
        return st, en

    def get_speed(self) -> float:
        return round(self._spin_speed.value(), 2)

    def get_parts(self) -> list[str]:
        text = self._txt_vi.toPlainText()
        return [line.strip() for line in text.splitlines() if line.strip()]

    def get_slices(self) -> list[dict]:
        text = self._txt_vi.toPlainText()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return []
        start, end = self.get_times()
        total_dur = max(0.1, end - start)
        word_counts = [max(1, len(l.split())) for l in lines]
        total_words = sum(word_counts)
        slices = []
        curr_t = start
        for idx, (l, wc) in enumerate(zip(lines, word_counts), start=1):
            if idx == len(lines):
                seg_end = end
            else:
                dur = round(total_dur * (wc / total_words), 2)
                seg_end = round(curr_t + dur, 2)
                seg_end = max(curr_t + 0.1, min(end - 0.1 * (len(lines) - idx), seg_end))
            slices.append({"text": l, "start": curr_t, "end": seg_end})
            curr_t = seg_end
        return slices


# Backward-compatible alias
SplitSegmentDialog = EditSegmentDialog


class AddOrigRangeDialog(QDialog):
    """Dialog to define an independent original audio passthrough range."""
    def __init__(self, current_time: float, max_duration: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Khoanh vùng giữ âm thanh gốc")
        self.setFixedWidth(420)
        self.setStyleSheet("background-color: #121418; color: #f0f2f5;")

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 16, 18, 16)

        hdr = QLabel("<b>Khoanh vùng giữ 100% âm thanh gốc</b>")
        hdr.setStyleSheet("font-size: 13px; color: #f59e0b;")
        layout.addWidget(hdr)

        desc = QLabel(
            "Đoạn video được khoanh vùng sẽ phát trọn vẹn 100% âm thanh gốc (nhạc nền, lời bài hát gốc). "
            "Hệ thống sẽ tự động tắt giọng đọc TTS và duck BGM tách lọc trong khoảng này (hoàn toàn tách biệt với phụ đề)."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(desc)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(10)

        # Mặc định lấy vị trí hiện tại của video làm mốc bắt đầu
        cur_start = round(max(0.0, current_time), 2)
        # Mặc định kéo dài ra 5 giây sau làm mốc kết thúc
        cur_end = round(cur_start + 5.0, 2)
        max_limit = max(cur_end + 60.0, max_duration, 10.0)

        # Start time
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Bắt đầu (giây):"))
        self._spn_start = QDoubleSpinBox()
        self._spn_start.setRange(0.0, max_limit)
        self._spn_start.setValue(cur_start)
        self._spn_start.setSingleStep(0.5)
        self._spn_start.setDecimals(2)
        self._spn_start.setFixedHeight(28)
        self._spn_start.valueChanged.connect(self._on_start_changed)
        r1.addWidget(self._spn_start)

        btn_get_start = QPushButton("Lấy vị trí video")
        btn_get_start.setFixedHeight(28)
        btn_get_start.setToolTip("Lấy vị trí hiện tại của con trỏ video và kéo dài 5s")
        btn_get_start.clicked.connect(self._set_start_from_video)
        r1.addWidget(btn_get_start)
        card_layout.addLayout(r1)

        # End time
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Kết thúc (giây):"))
        self._spn_end = QDoubleSpinBox()
        self._spn_end.setRange(0.0, max_limit)
        self._spn_end.setValue(cur_end)
        self._spn_end.setSingleStep(0.5)
        self._spn_end.setDecimals(2)
        self._spn_end.setFixedHeight(28)
        r2.addWidget(self._spn_end)

        btn_get_end = QPushButton("Lấy vị trí video")
        btn_get_end.setFixedHeight(28)
        btn_get_end.setToolTip("Lấy mốc thời gian hiện tại của con trỏ video")
        btn_get_end.clicked.connect(lambda: self._spn_end.setValue(round(self._get_parent_pos(), 2)))
        r2.addWidget(btn_get_end)
        card_layout.addLayout(r2)

        layout.addWidget(card)

        # Buttons
        btns = QHBoxLayout()
        btns.addStretch(1)
        btn_cancel = QPushButton("Hủy")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)

        btn_ok = QPushButton(" Xác nhận khoanh vùng")
        btn_ok.setIcon(get_icon("music", "#1c1917", "#1c1917", 13))
        btn_ok.setStyleSheet("background-color: #f59e0b; color: #1c1917; font-weight: bold; padding: 6px 14px; border-radius: 4px;")
        btn_ok.clicked.connect(self._on_ok)
        btns.addWidget(btn_ok)
        layout.addLayout(btns)

    def _set_start_from_video(self):
        pos = round(max(0.0, self._get_parent_pos()), 2)
        self._spn_start.setValue(pos)
        self._spn_end.setValue(round(pos + 5.0, 2))

    def _on_start_changed(self, new_val: float):
        if self._spn_end.value() <= new_val:
            self._spn_end.setValue(round(new_val + 5.0, 2))

    def _get_parent_pos(self) -> float:
        p = self.parent()
        if p and hasattr(p, "_video_player") and p._video_player:
            return p._video_player.get_position()
        if p and hasattr(p, "_timeline") and p._timeline:
            return getattr(p._timeline._canvas, "_playhead", 0.0)
        return 0.0

    def _on_ok(self):
        if self._spn_end.value() <= self._spn_start.value():
            QMessageBox.warning(self, "Lỗi thời gian", "Thời gian kết thúc phải lớn hơn thời gian bắt đầu!")
            return
        self.accept()

    def get_range(self) -> tuple[float, float]:
        return float(self._spn_start.value()), float(self._spn_end.value())


class StudioPage(QWidget):
    """
    Main Studio Editing Page:
    - Top half:
        * Left: Video Preview Player (Expanded large view)
        * Right: Subtitle Table (with inline voice selection & TTS regen)
    - Bottom half:
        * Timeline Ruler (drag & drop subtitle/audio segments horizontally)
    """

    goto_export_requested = pyqtSignal(str)  # job_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_job_id: Optional[str] = None
        self._jobs: List[dict] = []
        self._current_segments: List[dict] = []
        self._orig_ranges: List[dict] = []
        self._workers: List[object] = []

        self._setup_ui()
        self.refresh_jobs()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # ─── Top Control Toolbar (Clean 2-Row Card) ───
        top_frame = QFrame()
        top_frame.setObjectName("toolbar_card")
        top_vbox = QVBoxLayout(top_frame)
        top_vbox.setContentsMargins(10, 8, 10, 8)
        top_vbox.setSpacing(7)

        def _make_sep() -> QFrame:
            s = QFrame()
            s.setFrameShape(QFrame.Shape.VLine)
            s.setStyleSheet(
                f"background-color: {COLORS['border']}; "
                "max-width: 1px; min-width: 1px; margin: 3px 3px;"
            )
            return s

        def _lbl(text: str) -> QLabel:
            lb = QLabel(text)
            lb.setObjectName("toolbar_label")
            return lb

        # ── Row 1: Project | Văn phong | Giọng ──
        row1_layout = QHBoxLayout()
        row1_layout.setContentsMargins(0, 0, 0, 0)
        row1_layout.setSpacing(6)
        row1_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        row1_layout.addWidget(_lbl("Tác vụ:"))

        self._job_combo = QComboBox()
        self._job_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._job_combo.setMinimumWidth(110)
        self._job_combo.setMaximumWidth(200)
        self._job_combo.setFixedHeight(28)
        self._job_combo.currentIndexChanged.connect(self._on_job_changed)
        row1_layout.addWidget(self._job_combo)

        btn_new_job = QPushButton(" Thêm")
        btn_new_job.setIcon(get_icon("plus", "#9ca3af", "#f0f2f5", 12))
        btn_new_job.setObjectName("compact")
        btn_new_job.setFixedHeight(28)
        btn_new_job.setToolTip("Thêm tệp video mới để lồng tiếng")
        btn_new_job.clicked.connect(self._create_new_job)
        row1_layout.addWidget(btn_new_job)

        btn_refresh = QPushButton()
        btn_refresh.setIcon(get_icon("refresh", "#9ca3af", "#f0f2f5", 12))
        btn_refresh.setObjectName("compact")
        btn_refresh.setFixedSize(28, 28)
        btn_refresh.setToolTip("Làm mới danh sách tác vụ")
        btn_refresh.clicked.connect(self.refresh_jobs)
        row1_layout.addWidget(btn_refresh)

        row1_layout.addWidget(_make_sep())
        row1_layout.addWidget(_lbl("Văn phong:"))

        self._style_combo = QComboBox()
        self._style_combo.addItems([
            "Tự nhiên, đời thường",
            "Hài hước, hóm hỉnh",
            "Trang trọng, tài liệu",
            "Kiếm hiệp, cổ trang",
            "Trẻ trung, hiện đại (Gen Z)",
        ])
        self._style_combo.setFixedHeight(28)
        self._style_combo.setMinimumWidth(135)
        self._style_combo.setMaximumWidth(170)
        row1_layout.addWidget(self._style_combo)

        row1_layout.addWidget(_make_sep())

        self._chk_detect_gender = SwitchToggle("Chia Nam/Nữ", checked=False)
        self._chk_detect_gender.setToolTip("Tích chọn nếu video có nhiều nhân vật Nam & Nữ (giọng lấy cố định từ Cài đặt)")
        row1_layout.addWidget(self._chk_detect_gender)

        self._lbl_single_gender = _lbl("Giọng:")
        row1_layout.addWidget(self._lbl_single_gender)

        self._combo_single_gender = QComboBox()
        self._combo_single_gender.addItem("Giọng Nam", "male")
        self._combo_single_gender.addItem("Giọng Nữ", "female")
        self._combo_single_gender.setFixedHeight(28)
        self._combo_single_gender.setMinimumWidth(95)
        self._combo_single_gender.setMaximumWidth(115)
        row1_layout.addWidget(self._combo_single_gender)

        def _on_chk_gender(state):
            is_multi = self._chk_detect_gender.isChecked()
            self._combo_single_gender.setVisible(not is_multi)
            self._lbl_single_gender.setText("(Tự động phân biệt Nam/Nữ)" if is_multi else "Giọng:")
            self._on_gender_mode_toggled(is_multi)

        self._chk_detect_gender.stateChanged.connect(_on_chk_gender)
        self._combo_single_gender.currentIndexChanged.connect(self._on_single_gender_changed)
        row1_layout.addStretch(1)
        top_vbox.addLayout(row1_layout)

        # ── Row 2: Từ/dòng + Tách tự động | Pipeline ──
        row2_layout = QHBoxLayout()
        row2_layout.setContentsMargins(0, 0, 0, 0)
        row2_layout.setSpacing(6)
        row2_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        row2_layout.addWidget(_lbl("Từ/dòng:"))

        self._spin_words_per_line = QSpinBox()
        self._spin_words_per_line.setObjectName("accent_spin")
        self._spin_words_per_line.setRange(3, 25)
        self._spin_words_per_line.setValue(6)
        self._spin_words_per_line.setFixedHeight(28)
        self._spin_words_per_line.setFixedWidth(84)
        self._spin_words_per_line.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._spin_words_per_line.setToolTip("Số từ mục tiêu trên mỗi dòng phụ đề (9:16 -> 5, 1:1 -> 6, 16:9 -> 9)")
        row2_layout.addWidget(self._spin_words_per_line)

        self._btn_auto_split = QPushButton(" Tách tự động")
        self._btn_auto_split.setIcon(get_icon("scissors", "#9ca3af", "#f0f2f5", 12))
        self._btn_auto_split.setFixedHeight(28)
        self._btn_auto_split.setToolTip("Tự động ngắt nhịp toàn bộ câu thành các dòng nhỏ theo số từ chỉ định")
        self._btn_auto_split.clicked.connect(self._on_auto_split_cues_clicked)
        row2_layout.addWidget(self._btn_auto_split)

        row2_layout.addWidget(_make_sep())
        row2_layout.addWidget(_lbl("Quy trình:"))

        self._btn_run = QPushButton("  1. Tạo phụ đề")
        self._btn_run.setIcon(get_icon("subtitles", "#ffffff", "#ffffff", 13))
        self._btn_run.setObjectName("primary")
        self._btn_run.setFixedHeight(28)
        self._btn_run.setToolTip("Bước 1: Nhận dạng tiếng Trung và dịch phụ đề tiếng Việt")
        self._btn_run.clicked.connect(self._run_subtitles_pipeline)
        row2_layout.addWidget(self._btn_run)

        self._btn_create_dub = QPushButton("  2. Tạo lồng tiếng")
        self._btn_create_dub.setIcon(get_icon("zap", "#ffffff", "#ffffff", 13))
        self._btn_create_dub.setObjectName("success")
        self._btn_create_dub.setFixedHeight(28)
        self._btn_create_dub.setToolTip("Bước 2: Tổng hợp giọng đọc tiếng Việt và khớp timeline (TTS -> Fit -> Mix)")
        self._btn_create_dub.clicked.connect(self._run_dub_pipeline)
        row2_layout.addWidget(self._btn_create_dub)

        self._btn_goto_export = QPushButton("  3. Phụ đề")
        self._btn_goto_export.setIcon(get_icon("arrow_right", "#ffffff", "#ffffff", 13))
        self._btn_goto_export.setFixedHeight(28)
        self._btn_goto_export.setToolTip("Bước 3: Chuyển sang tab Phụ đề để tùy biến phong cách chữ và cách khắc vào video")
        self._btn_goto_export.clicked.connect(self._on_goto_export)
        row2_layout.addWidget(self._btn_goto_export)

        row2_layout.addStretch(1)
        top_vbox.addLayout(row2_layout)
        main_layout.addWidget(top_frame)

        # ─── Progress Bar & Status (hidden when idle) ───
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setFixedHeight(18)
        self._progress_bar.setTextVisible(True)
        main_layout.addWidget(self._progress_bar)

        self._lbl_status = QLabel("")
        self._lbl_status.setObjectName("status_label")
        self._lbl_status.setVisible(False)
        main_layout.addWidget(self._lbl_status)

        # ─── Vertical Splitter (Top vs Bottom) ───
        v_splitter = QSplitter(Qt.Orientation.Vertical)
        v_splitter.setChildrenCollapsible(False)

        # ─── Top Panel (Horizontal Splitter: Left Large Preview, Right Subtitle Editor) ───
        h_splitter = QSplitter(Qt.Orientation.Horizontal)
        h_splitter.setChildrenCollapsible(False)

        # Left: Video Player (Expanded)
        left_box = QWidget()
        left_layout = QVBoxLayout(left_box)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        lbl_preview = QLabel("Xem trước")
        lbl_preview.setObjectName("section_title")
        left_layout.addWidget(lbl_preview)

        self._video_player = VideoPlayerWidget()
        self._video_player.position_changed.connect(self._on_player_pos_changed)
        self._video_player.duration_known.connect(self._on_video_duration_known)
        left_layout.addWidget(self._video_player, 1)

        h_splitter.addWidget(left_box)

        # Right: Subtitle Table
        right_box = QWidget()
        right_box.setMinimumWidth(380)
        right_layout = QVBoxLayout(right_box)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        # Unified Subtitle Header & Action Toolbar
        sub_hdr = QHBoxLayout()
        sub_hdr.setContentsMargins(0, 2, 0, 2)
        sub_hdr.setSpacing(6)

        lbl_subs = QLabel("Phụ đề")
        lbl_subs.setObjectName("section_title")
        sub_hdr.addWidget(lbl_subs)

        self._lbl_seg_count = QLabel("0 câu")
        self._lbl_seg_count.setStyleSheet(
            "color: #9ca3af; font-size: 11px; font-weight: 500; "
            "background-color: #14161e; border: 1px solid #1e222e; "
            "border-radius: 9px; padding: 2px 7px;"
        )
        sub_hdr.addWidget(self._lbl_seg_count)

        sub_hdr.addStretch(1)

        btn_add = QPushButton(" Thêm lời")
        btn_add.setIcon(get_icon("plus", "#9ca3af", "#f0f2f5", 12))
        btn_add.setFixedHeight(26)
        btn_add.setToolTip("Thêm lời thoại phụ đề thủ công tại vị trí phát hiện tại (ngay cả khi chưa bấm tạo phụ đề)")
        btn_add.clicked.connect(self._on_add_segment)
        sub_hdr.addWidget(btn_add)

        btn_split = QPushButton(" Tách")
        btn_split.setIcon(get_icon("scissors", "#9ca3af", "#f0f2f5", 12))
        btn_split.setFixedHeight(26)
        btn_split.setToolTip("Chỉnh sửa câu hoặc tách các dòng hiển thị (Enter để xuống dòng)")
        btn_split.clicked.connect(self._on_split_segment)
        sub_hdr.addWidget(btn_split)

        btn_merge = QPushButton(" Gộp")
        btn_merge.setIcon(get_icon("combine", "#9ca3af", "#f0f2f5", 12))
        btn_merge.setFixedHeight(26)
        btn_merge.setToolTip("Gộp các đoạn phụ đề đang chọn thành 1 câu")
        btn_merge.clicked.connect(self._on_merge_segments)
        sub_hdr.addWidget(btn_merge)

        btn_del = QPushButton(" Xóa")
        btn_del.setIcon(get_icon("trash", "#ef4444", "#fca5a5", 12))
        btn_del.setObjectName("danger")
        btn_del.setFixedHeight(26)
        btn_del.setToolTip("Xóa đoạn phụ đề đang chọn")
        btn_del.clicked.connect(self._on_delete_segment)
        sub_hdr.addWidget(btn_del)

        btn_find = QPushButton(" Tìm / Thay thế")
        btn_find.setIcon(get_icon("search", "#9ca3af", "#f0f2f5", 12))
        btn_find.setFixedHeight(26)
        btn_find.setToolTip("Tìm kiếm, thay thế nhanh và xóa hàng loạt trong phụ đề (Ctrl + F)")
        btn_find.clicked.connect(self._toggle_find_replace)
        sub_hdr.addWidget(btn_find)

        right_layout.addLayout(sub_hdr)

        self._sub_editor = SubtitleEditorWidget()
        self._find_replace_bar = FindReplaceBar(self._sub_editor)
        right_layout.addWidget(self._find_replace_bar)

        self._shortcut_find = QShortcut(QKeySequence("Ctrl+F"), self)
        self._shortcut_find.activated.connect(self._toggle_find_replace)

        self._sub_editor.regen_requested.connect(self._on_regen_tts)
        self._sub_editor.play_audio_requested.connect(self._on_play_segment_audio)
        self._sub_editor.segment_selected.connect(self._on_segment_selected)
        self._sub_editor.segment_voice_changed.connect(self._on_segment_voice_changed)
        self._sub_editor.segment_text_changed.connect(self._on_segment_text_edited)
        self._sub_editor.segments_batch_changed.connect(self._on_segments_batch_changed)
        self._sub_editor.add_segment_requested.connect(self._on_add_segment)
        self._sub_editor.split_segment_requested.connect(self._on_split_segment_by_id)
        self._sub_editor.delete_segment_requested.connect(self._on_delete_segment_by_id)
        self._sub_editor.delete_segments_requested.connect(self._on_delete_segments_batch)
        self._sub_editor.toggle_tts_requested.connect(self._on_toggle_tts_batch)
        self._sub_editor.toggle_sub_requested.connect(self._on_toggle_sub_batch)
        self._sub_editor.merge_segments_requested.connect(self._on_merge_segments_by_ids)
        right_layout.addWidget(self._sub_editor, 1)

        left_box.setMinimumWidth(320)
        h_splitter.setHandleWidth(8)
        h_splitter.addWidget(right_box)
        h_splitter.setStretchFactor(0, 3)
        h_splitter.setStretchFactor(1, 2)
        h_splitter.setSizes([720, 480])

        v_splitter.addWidget(h_splitter)

        # ─── Bottom Panel: Timeline ───
        bottom_box = QWidget()
        bottom_layout = QVBoxLayout(bottom_box)
        bottom_layout.setContentsMargins(0, 4, 0, 0)
        bottom_layout.setSpacing(4)

        self._timeline = TimelineWidget()
        self._timeline.seek_requested.connect(self._on_timeline_seek)
        self._timeline.subtitle_moved.connect(self._on_segment_moved)
        self._timeline.voice_moved.connect(self._on_voice_moved)
        self._timeline.segment_selected.connect(self._on_timeline_seg_selected)
        self._timeline.segment_context_menu_requested.connect(self._on_timeline_segment_context_menu)
        self._timeline.add_orig_range_requested.connect(self._on_add_orig_range)
        self._timeline.orig_range_created.connect(self._on_orig_range_created)
        self._timeline.orig_range_changed.connect(self._on_orig_range_changed)
        self._timeline.orig_range_deleted.connect(self._on_orig_range_deleted)
        bottom_layout.addWidget(self._timeline)

        v_splitter.addWidget(bottom_box)
        v_splitter.setStretchFactor(0, 4)
        v_splitter.setStretchFactor(1, 1)
        v_splitter.setSizes([540, 160])

        main_layout.addWidget(v_splitter, 1)

    # ─── Logic & Slots ────────────────────────────────────────────────────────

    def refresh_jobs(self):
        w = ListJobsWorker()
        w.finished.connect(self._on_jobs_loaded)
        w.error.connect(lambda err: None)
        self._workers.append(w)
        w.start()

    def _on_jobs_loaded(self, jobs: List[dict]):
        self._jobs = jobs
        self._job_combo.blockSignals(True)
        self._job_combo.clear()
        if not jobs:
            self._job_combo.addItem("Không có tác vụ nào", "")
            self._current_job_id = None
        else:
            for j in jobs:
                if isinstance(j, dict):
                    jid = j.get("id") or j.get("job_id", "")
                    name = j.get("video_name") or jid
                else:
                    jid = str(j)
                    name = jid
                if jid:
                    self._job_combo.addItem(f"{name} ({jid})", jid)
            if self._current_job_id:
                idx = self._job_combo.findData(self._current_job_id)
                if idx >= 0:
                    self._job_combo.setCurrentIndex(idx)
                else:
                    self._job_combo.setCurrentIndex(0)
            else:
                self._job_combo.setCurrentIndex(0)
            self._current_job_id = self._job_combo.currentData()
        self._job_combo.blockSignals(False)

        if self._current_job_id:
            self._load_current_job()

    def _on_job_changed(self, idx: int):
        jid = self._job_combo.currentData()
        if jid and jid != self._current_job_id:
            self._current_job_id = jid
            self._load_current_job()

    def _load_current_job(self, restore_pos: Optional[float] = None):
        if not self._current_job_id:
            return
        self._pending_restore_pos = restore_pos
        w = LoadJobWorker(self._current_job_id)
        w.finished.connect(self._on_job_data_loaded)
        w.error.connect(lambda err: QMessageBox.warning(self, "Lỗi tải tác vụ", err))
        self._workers.append(w)
        w.start()

    def _on_job_data_loaded(self, job: dict, segments: List[dict]):
        self._current_segments = segments

        # Load video into player:
        # 1. Prioritize preview_dubbed.mp4 (fresh video with Vietnamese dubbed audio)
        # 2. Rendered video if available
        # 3. Fallback to original input.mp4 if not yet dubbed
        jid = self._current_job_id or ""
        video_path = None
        ws_preview = Path("workspace") / jid / "preview_dubbed.mp4"
        rendered_mp4 = Path("out") / f"{jid}_vi.mp4"
        ws_input = Path("workspace") / jid / "input.mp4"
        orig_src = Path(job.get("video_path", "")) if job.get("video_path") else None

        is_rendered = False
        if ws_preview.exists():
            video_path = str(ws_preview.resolve())
            is_rendered = True
        elif rendered_mp4.exists():
            video_path = str(rendered_mp4.resolve())
            is_rendered = True
        elif ws_input.exists():
            video_path = str(ws_input.resolve())
        elif orig_src and orig_src.exists():
            video_path = str(orig_src.resolve())

        if video_path:
            self._video_player.load_video(video_path)
            # Sync audio stems (Vietnamese voice, BGM, vocals) if available
            ws_dir = Path("workspace") / jid if jid else None
            self._video_player.setup_job_audio(
                workspace_dir=ws_dir,
                is_rendered_video=is_rendered,
            )

        # Auto-synchronize subtitle timestamps and cues with voice audio if TTS has been generated
        for s in segments:
            if s.get("tts_dur") or s.get("tts_file"):
                orig_s_start = float(s.get("start", 0))
                orig_s_dur = max(0.05, float(s.get("dur") or (float(s.get("end", 0)) - orig_s_start)))
                fit_info = s.get("fit") or {}
                rate = float(fit_info.get("rate", 1.0) or 1.0)
                dur = float(s.get("tts_dur") or orig_s_dur)
                eff_dur = round(dur / rate, 3) if fit_info.get("method") in ("speedup", "slowdown") and rate > 0 else dur
                v_start = float(s.get("voice_start") if s.get("voice_start") is not None else fit_info.get("offset_start", orig_s_start))
                s["start"] = round(v_start, 3)
                s["end"] = round(v_start + eff_dur, 3)
                s["voice_start"] = round(v_start, 3)
                s["dur"] = round(eff_dur, 3)

                ratio = eff_dur / orig_s_dur
                if s.get("cues") and isinstance(s["cues"], list):
                    for cue in s["cues"]:
                        if isinstance(cue, dict):
                            rel_st = max(0.0, float(cue.get("start", orig_s_start)) - orig_s_start)
                            rel_en = max(rel_st + 0.05, float(cue.get("end", orig_s_start + orig_s_dur)) - orig_s_start)
                            cue["start"] = round(v_start + rel_st * ratio, 3)
                            cue["end"] = round(v_start + rel_en * ratio, 3)

                if s.get("sub_slices") and isinstance(s["sub_slices"], list):
                    for sl in s["sub_slices"]:
                        if isinstance(sl, dict):
                            rel_st = max(0.0, float(sl.get("start", orig_s_start)) - orig_s_start)
                            rel_en = max(rel_st + 0.05, float(sl.get("end", orig_s_start + orig_s_dur)) - orig_s_start)
                            sl["start"] = round(v_start + rel_st * ratio, 3)
                            sl["end"] = round(v_start + rel_en * ratio, 3)

        # Update words_per_line default from probe.json / job_config.json
        if hasattr(self, "_spin_words_per_line") and jid:
            ws_dir = Path("workspace") / jid
            conf_file = ws_dir / "job_config.json"
            set_val = False
            if conf_file.exists():
                try:
                    import json
                    c_data = json.loads(conf_file.read_text(encoding="utf-8"))
                    if c_data.get("words_per_line"):
                        self._spin_words_per_line.setValue(int(c_data["words_per_line"]))
                        set_val = True
                except Exception:
                    pass
            if not set_val:
                probe_file = ws_dir / "probe.json"
                if probe_file.exists():
                    try:
                        import json
                        p_data = json.loads(probe_file.read_text(encoding="utf-8"))
                        vw = p_data.get("video", {}).get("width", 1920)
                        vh = p_data.get("video", {}).get("height", 1080)
                        if vh > vw:
                            self._spin_words_per_line.setValue(5)
                        elif abs(vw - vh) < 50:
                            self._spin_words_per_line.setValue(6)
                        else:
                            self._spin_words_per_line.setValue(9)
                    except Exception:
                        pass

        # Update gender and single-voice controls from job_config.json
        if jid:
            from dubstudio.config import AppConfig
            cfg = AppConfig.load()
            conf_file = Path("workspace") / jid / "job_config.json"
            c_data = {}
            if conf_file.exists():
                try:
                    c_data = json.loads(conf_file.read_text(encoding="utf-8"))
                except Exception:
                    pass
            male_voice = c_data.get("default_male_voice") or cfg.tts.default_male_voice
            female_voice = c_data.get("default_female_voice") or cfg.tts.default_female_voice
            detect_gender = bool(c_data.get("detect_gender", False))
            single_choice = c_data.get("single_voice_gender", "male")

            if hasattr(self, "_chk_detect_gender"):
                self._chk_detect_gender.blockSignals(True)
                self._chk_detect_gender.setChecked(detect_gender)
                self._chk_detect_gender.blockSignals(False)

            if hasattr(self, "_combo_single_gender"):
                g_idx = self._combo_single_gender.findData(single_choice)
                if g_idx >= 0:
                    self._combo_single_gender.blockSignals(True)
                    self._combo_single_gender.setCurrentIndex(g_idx)
                    self._combo_single_gender.blockSignals(False)
                self._combo_single_gender.setVisible(not detect_gender)

            if hasattr(self, "_lbl_single_gender"):
                self._lbl_single_gender.setText("(Tự động phân biệt Nam/Nữ)" if detect_gender else "Giọng:")

            cur_default_voice = female_voice if single_choice == "female" else male_voice
            self._sub_editor.set_default_voice(cur_default_voice)

        # Populate tables & timeline
        self._sub_editor.load_segments(segments)
        self._timeline.set_segments(segments)
        self._load_orig_ranges()
        if hasattr(self, "_lbl_seg_count"):
            self._lbl_seg_count.setText(f"{len(segments)} câu")

        if getattr(self, "_pending_restore_pos", None) is not None:
            r_pos = self._pending_restore_pos
            self._pending_restore_pos = None
            if hasattr(self, "_video_player") and self._video_player:
                self._video_player.seek(r_pos)

    def load_job_by_id(self, job_id: str):
        """Externally switch active job and reload Studio immediately."""
        self._current_job_id = job_id
        w = ListJobsWorker()

        def _on_done(jobs: List[dict]):
            self._on_jobs_loaded(jobs)
            idx = self._job_combo.findData(job_id)
            if idx >= 0:
                self._job_combo.setCurrentIndex(idx)
            self._load_current_job()

        w.finished.connect(_on_done)
        self._workers.append(w)
        w.start()

    def _create_new_job(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn video cần lồng tiếng",
            "",
            "Video Files (*.mp4 *.mkv *.avi *.mov *.flv *.webm);;All Files (*.*)",
        )
        if not file_path:
            return

        default_name = Path(file_path).stem
        proj_name, ok = QInputDialog.getText(
            self,
            "Đặt tên dự án",
            "Nhập tên dự án (tất cả các tệp sẽ được lưu vào thư mục dự án):",
            text=default_name,
        )
        if not ok:
            return
        proj_name = proj_name.strip() or default_name

        w = CreateJobWorker(file_path, proj_name)

        def _on_done(res):
            jid = res.get("job_id")
            if jid:
                self.load_job_by_id(jid)

        w.finished.connect(_on_done)
        w.error.connect(lambda err: QMessageBox.critical(self, "Lỗi tạo tác vụ", err))
        self._workers.append(w)
        w.start()

    def _on_auto_split_cues_clicked(self):
        if not self._current_job_id or not getattr(self, "_current_segments", None):
            QMessageBox.warning(self, "Tách tự động", "Chưa có tác vụ hoặc phụ đề nào được tải.")
            return

        target_n = self._spin_words_per_line.value()
        ws_dir = Path("workspace") / self._current_job_id
        analysis_data = {}
        analysis_file = ws_dir / "analysis.json"
        if analysis_file.exists():
            try:
                import json
                analysis_data = json.loads(analysis_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        from dubstudio.subtitles.cue_split import auto_split_all_units
        self._current_segments = auto_split_all_units(self._current_segments, target_n=target_n, analysis=analysis_data, force=True)

        # Save selected target_n to job_config.json
        conf_file = ws_dir / "job_config.json"
        try:
            import json
            conf_data = json.loads(conf_file.read_text(encoding="utf-8")) if conf_file.exists() else {}
            conf_data["words_per_line"] = target_n
            conf_file.write_text(json.dumps(conf_data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

        # Persist to units.json and segments.json
        import json
        units_file = ws_dir / "units.json"
        if units_file.exists():
            try:
                units_file.write_text(json.dumps(self._current_segments, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

        segs_file = ws_dir / "segments.json"
        if segs_file.exists():
            try:
                with open(segs_file, "r", encoding="utf-8") as f:
                    s_data = json.load(f)
                s_data["segments"] = self._current_segments
                with open(segs_file, "w", encoding="utf-8") as f:
                    json.dump(s_data, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        # Update table and timeline immediately
        self._sub_editor.load_segments(self._current_segments)
        if hasattr(self, "_timeline") and self._timeline:
            total_dur = getattr(self._timeline._canvas, "_duration", 0.0)
            self._timeline.set_segments(self._current_segments, total_dur)

        if hasattr(self, "_video_player") and self._video_player:
            pos_sec = getattr(self._video_player, "_current_pos_sec", 0.0)
            self._on_player_pos_changed(pos_sec)

        QMessageBox.information(
            self,
            "Tách phụ đề tự động",
            f"Đã hoàn thành tách phụ đề theo {target_n} từ/dòng cho toàn bộ {len(self._current_segments)} câu thoại (bảo toàn các dòng đã khóa)."
        )

    def _run_subtitles_pipeline(self):
        """Run stages 1 to 8: ingest up to translation to generate subtitles for review."""
        if self._current_job_id and hasattr(self, "_spin_words_per_line"):
            ws_dir = Path("workspace") / self._current_job_id
            conf_file = ws_dir / "job_config.json"
            conf_data = {}
            if conf_file.exists():
                try:
                    import json
                    conf_data = json.loads(conf_file.read_text(encoding="utf-8"))
                except Exception:
                    pass
            conf_data["words_per_line"] = self._spin_words_per_line.value()
            try:
                import json
                conf_file.write_text(json.dumps(conf_data, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
        self._start_pipeline(subtitles_only=True)

    def _run_dub_pipeline(self):
        """Run stages 9 to 11: TTS -> Fit -> Mix to produce dubbed audio from review subtitles."""
        if hasattr(self, "_sub_editor") and self._current_job_id:
            all_data = self._sub_editor.get_all_segments_data()
            if all_data:
                # Synchronize all current table values (text/voice/speed) atomically before running
                sync_w = BatchUpdateSegmentsWorker(self._current_job_id, all_data)
                def _start_after_sync(res):
                    self._start_pipeline(dub_only=True)
                sync_w.finished.connect(_start_after_sync)
                sync_w.error.connect(lambda e: self._start_pipeline(dub_only=True))
                self._workers.append(sync_w)
                sync_w.start()
                return
        self._start_pipeline(dub_only=True)

    def _run_pipeline(self):
        """Full pipeline run (fallback)."""
        self._start_pipeline()

    def _start_pipeline(self, subtitles_only: bool = False, dub_only: bool = False):
        if not self._current_job_id:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn hoặc thêm một tác vụ video!")
            return

        # Check system prerequisites (ffmpeg/ffprobe, dependencies)
        task = "subtitles" if subtitles_only else ("dub" if dub_only else "all")
        from dubstudio.diagnostics import check_system_prerequisites
        ok, title, msg = check_system_prerequisites(task=task)
        if not ok:
            QMessageBox.critical(self, title, msg)
            return

        # Validate workspace input file
        from dubstudio.config import AppConfig
        cfg = AppConfig.load()
        ws_dir = cfg.general.workspace_dir / self._current_job_id
        in_vid = ws_dir / "input.mp4"
        if not in_vid.exists():
            QMessageBox.critical(
                self,
                "Tác vụ chưa sẵn sàng",
                f"Không tìm thấy tệp video đã nạp (input.mp4) trong thư mục tác vụ '{self._current_job_id}'.\n"
                "Vui lòng thêm lại video để khởi tạo dự án hợp lệ.",
            )
            return

        self._video_player.unload()

        if subtitles_only:
            try:
                from ui.workers import StopTTSWorker
                stop_w = StopTTSWorker()
                self._workers.append(stop_w)
                stop_w.start()
            except Exception:
                pass
        elif dub_only:
            try:
                warm_w = WarmTTSWorker()
                self._workers.append(warm_w)
                warm_w.start()
            except Exception:
                pass

        self._btn_run.setEnabled(False)
        if hasattr(self, "_btn_create_dub"):
            self._btn_create_dub.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._lbl_status.setVisible(True)
        self._lbl_status.setText("Đang khởi động tiến trình...")

        detect_gender = self._chk_detect_gender.isChecked()
        single_voice_gender = self._combo_single_gender.currentData() or "male"
        style = self._style_combo.currentText()

        w = RunPipelineWorker(
            job_id=self._current_job_id,
            style=style,
            detect_gender=detect_gender,
            single_voice_gender=single_voice_gender,
            subtitles_only=subtitles_only,
            dub_only=dub_only,
        )

        def _on_progress(evt: dict):
            if evt.get("level") == "manual_input_required":
                self._open_manual_translate_dialog(evt)
                return
            pct = int(evt.get("pct", 0) or 0)
            self._progress_bar.setValue(pct)
            stage = evt.get("stage", "")
            msg = evt.get("msg", "")
            self._lbl_status.setText(f"[{stage}] {msg}")

        def _on_finished(result: dict):
            self._btn_run.setEnabled(True)
            if hasattr(self, "_btn_create_dub"):
                self._btn_create_dub.setEnabled(True)
            self._progress_bar.setVisible(False)
            self._lbl_status.setVisible(False)

            # Load job immediately so table & video are populated BEFORE modal popup appears
            self._load_current_job()

            if subtitles_only:
                QMessageBox.information(
                    self, "Hoàn tất tạo phụ đề",
                    "Đã nhận dạng và dịch phụ đề tiếng Việt thành công!\nBạn có thể kiểm tra, dùng Ctrl + F để tìm/thay thế hoặc sửa trực tiếp trên bảng.\nKhi sẵn sàng, hãy bấm '2. Tạo lồng tiếng' ở thanh công cụ phía trên."
                )
            else:
                QMessageBox.information(self, "Hoàn tất lồng tiếng", "Quy trình lồng tiếng đã hoàn tất thành công! Bạn có thể xem thử video ở khung bên trái.")

        def _on_error(err: str):
            self._btn_run.setEnabled(True)
            if hasattr(self, "_btn_create_dub"):
                self._btn_create_dub.setEnabled(True)
            self._progress_bar.setVisible(False)
            self._lbl_status.setVisible(False)
            err_lower = str(err).lower()
            if any(k in err_lower for k in ("dịch", "translate", "gemini", "api", "cdp", "từ điển")):
                QMessageBox.warning(
                    self,
                    "Cảnh báo dịch thuật",
                    f"Quá trình dịch thuật chưa thành công:\n{err}\n\n"
                    "👉 Bạn hãy chuyển sang tab 'Cài đặt' để chọn phương thức dịch phù hợp (Gemini Web hoặc Tự dịch thủ công), sau đó bấm '1. Tạo phụ đề' lại."
                )
            else:
                from dubstudio.paths import get_logs_dir
                logs_dir = get_logs_dir()
                msg_box = QMessageBox(self)
                msg_box.setIcon(QMessageBox.Icon.Critical)
                msg_box.setWindowTitle("Lỗi xử lý quy trình")
                msg_box.setText(f"Đã xảy ra sự cố trong quá trình xử lý:\n\n{err}")
                btn_open_logs = msg_box.addButton("Mở thư mục nhật ký", QMessageBox.ButtonRole.ActionRole)
                msg_box.addButton("Đóng", QMessageBox.ButtonRole.RejectRole)
                msg_box.exec()
                if msg_box.clickedButton() == btn_open_logs:
                    try:
                        import os
                        os.startfile(str(logs_dir.resolve()))
                    except Exception:
                        pass

        w.progress.connect(_on_progress)
        w.finished.connect(_on_finished)
        w.error.connect(_on_error)
        self._workers.append(w)
        w.start()

    def _open_manual_translate_dialog(self, evt: dict):
        """Open the interactive copy/paste manual translation dialog."""
        from ui.dialogs.manual_translate_dialog import ManualTranslateDialog
        data = evt.get("data") or {}
        prompt_text = data.get("prompt") or evt.get("msg", "")
        job_id = data.get("job_id") or self._current_job_id
        total_items = data.get("total_items") or len(getattr(self, "_current_segments", []))
        dlg = ManualTranslateDialog(prompt_text=prompt_text, job_id=job_id, total_items=total_items, parent=self)
        dlg.exec()

    def _toggle_find_replace(self):
        if hasattr(self, "_find_replace_bar"):
            if self._find_replace_bar.isVisible():
                self._find_replace_bar.hide_bar()
            else:
                self._find_replace_bar.show_bar()

    def _on_segment_text_edited(self, seg_id: int, new_text: str):
        """Persist manual subtitle text edit from table cell directly to backend."""
        if not self._current_job_id:
            return
        payload = {"vi_text": new_text, "tts_text": new_text}
        for s in self._current_segments:
            if s.get("id") == seg_id or s.get("index") == seg_id:
                s["vi_text"] = new_text
                s["tts_text"] = new_text
                if s.get("cues"):
                    if len(s["cues"]) == 1:
                        s["cues"][0]["text"] = new_text
                    elif "\n" in new_text:
                        parts = [p.strip() for p in new_text.splitlines() if p.strip()]
                        if len(parts) == len(s["cues"]):
                            for c, p in zip(s["cues"], parts):
                                c["text"] = p
                        else:
                            s["cues"] = None
                    payload["cues"] = s.get("cues")
                if s.get("sub_slices"):
                    if len(s["sub_slices"]) == 1:
                        s["sub_slices"][0]["text"] = new_text
                    elif "\n" in new_text:
                        parts = [p.strip() for p in new_text.splitlines() if p.strip()]
                        if len(parts) == len(s["sub_slices"]):
                            for sl, p in zip(s["sub_slices"], parts):
                                sl["text"] = p
                        else:
                            s["sub_slices"] = None
                    payload["sub_slices"] = s.get("sub_slices")
                break
        if hasattr(self, "_timeline") and self._timeline:
            total_dur = getattr(self._timeline._canvas, "_duration", 0.0)
            self._timeline.set_segments(self._current_segments, total_dur)
        w = UpdateSegmentWorker(self._current_job_id, seg_id, payload)
        self._workers.append(w)
        w.start()

    def _on_play_segment_audio(self, seg_idx: int):
        if not self._current_job_id:
            return
        wav_file = Path("workspace") / self._current_job_id / "tts" / f"{seg_idx:04d}.wav"
        if not wav_file.exists():
            QMessageBox.information(
                self, "Chưa có âm thanh", f"Chưa có tệp âm thanh cho câu #{seg_idx}.\nVui lòng bấm '2. Tạo lồng tiếng' ở thanh công cụ để tổng hợp giọng đọc!"
            )
            return

        from PyQt6.QtCore import QUrl
        from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer

        if not hasattr(self, "_seg_player") or self._seg_player is None:
            self._seg_player = QMediaPlayer(self)
            self._seg_audio_out = QAudioOutput(self)
            self._seg_player.setAudioOutput(self._seg_audio_out)
            self._seg_audio_out.setVolume(1.0)

        self._seg_player.setSource(QUrl.fromLocalFile(str(wav_file.resolve())))
        self._seg_player.play()

    def _on_regen_tts(self, seg_idx: int, text: str, voice: str, speed: float):
        if not self._current_job_id:
            return

        self._sub_editor.set_row_busy(seg_idx, True)
        w = RegenTTSWorker(self._current_job_id, seg_idx, voice, speed, text=text)

        def _on_done(idx, res):
            self._sub_editor.set_row_busy(idx, False)
            # Update local segments
            for s in self._current_segments:
                if s.get("id") == idx or s.get("index") == idx:
                    if text:
                        s["vi_text"] = text
                        s["tts_text"] = res.get("tts_text", text)
                    s["voice"] = voice
                    s["speed"] = speed
                    s["tts_dur"] = res.get("tts_dur")
                    s["tts_file"] = res.get("tts_file", f"tts/{idx:04d}.wav")
                    s["tts_hash"] = res.get("tts_hash")
                    break
            self._timeline.set_segments(self._current_segments)

            # Update video player preview voice track immediately
            if hasattr(self, "_video_player") and self._video_player:
                ws_dir = Path("workspace") / self._current_job_id
                raw_wav = ws_dir / "voice_raw.wav"
                try:
                    raw_wav.unlink(missing_ok=True)
                except Exception:
                    pass
                v_track = self._video_player._ensure_voice_raw(ws_dir)
                if v_track and v_track.exists():
                    self._video_player.load_audio_tracks(vi_voice_path=v_track)

        def _on_err(idx, err):
            self._sub_editor.set_row_busy(idx, False)
            QMessageBox.warning(self, "Lỗi tạo TTS", f"Không thể tạo âm thanh cho câu {idx}: {err}")

        w.finished.connect(_on_done)
        w.error.connect(_on_err)
        self._workers.append(w)
        w.start()

    def _on_segments_batch_changed(self, updates: list):
        """Persist batch find/replace and batch delete directly to backend."""
        if not self._current_job_id or not updates:
            return
        # 1. Update in-memory segments and timeline immediately
        update_map = {item["id"]: item for item in updates}
        for s in self._current_segments:
            sid = s.get("id")
            if sid in update_map:
                u = update_map[sid]
                s["vi_text"] = u["vi_text"]
                s["tts_text"] = u.get("tts_text", u["vi_text"])
                if "cues" in u:
                    s["cues"] = u["cues"]
                elif s.get("cues") and len(s["cues"]) == 1:
                    s["cues"][0]["text"] = u["vi_text"]
                if "sub_slices" in u:
                    s["sub_slices"] = u["sub_slices"]
                elif s.get("sub_slices") and len(s["sub_slices"]) == 1:
                    s["sub_slices"][0]["text"] = u["vi_text"]

        if hasattr(self, "_timeline") and self._timeline:
            total_dur = getattr(self._timeline._canvas, "_duration", 0.0)
            self._timeline.set_segments(self._current_segments, total_dur)

        # 2. Persist to backend asynchronously
        w = BatchUpdateSegmentsWorker(self._current_job_id, updates)
        self._workers.append(w)
        w.start()

    def _on_voice_moved(self, seg_idx: int, new_voice_start: float):
        """Update voice placement start position, sync subtitle timing, and rebuild preview voice track."""
        if not self._current_job_id:
            return
        payload = {"voice_start": round(new_voice_start, 3)}
        for s in self._current_segments:
            if s.get("id") == seg_idx or s.get("index") == seg_idx:
                s["voice_start"] = round(new_voice_start, 3)
                dur = float(s.get("dur") or s.get("tts_dur") or (float(s.get("end", 0)) - float(s.get("start", 0))))
                s["start"] = s["voice_start"]
                s["end"] = round(s["start"] + dur, 3)
                payload["start"] = s["start"]
                payload["end"] = s["end"]
                if hasattr(self, "_sub_editor") and self._sub_editor:
                    self._sub_editor.update_segment_times(seg_idx, s["start"], s["end"])
                if hasattr(self, "_timeline") and self._timeline:
                    total_dur = getattr(self._timeline._canvas, "_duration", 0.0)
                    self._timeline.set_segments(self._current_segments, total_dur)
                break
        w = UpdateSegmentWorker(
            self._current_job_id,
            seg_idx,
            payload,
        )
        def _on_done(idx, res):
            if hasattr(self, "_video_player") and self._video_player:
                ws_dir = Path("workspace") / self._current_job_id
                raw_wav = ws_dir / "voice_raw.wav"
                try:
                    raw_wav.unlink(missing_ok=True)
                except Exception:
                    pass
                v_track = self._video_player._ensure_voice_raw(ws_dir)
                if v_track and v_track.exists():
                    self._video_player.load_audio_tracks(vi_voice_path=v_track)
        w.finished.connect(_on_done)
        self._workers.append(w)
        w.start()

    def _on_single_gender_changed(self, idx: int):
        if not self._current_job_id:
            return
        from dubstudio.config import AppConfig
        cfg = AppConfig.load()
        selected_gender = self._combo_single_gender.currentData() or "male"
        conf_file = Path("workspace") / self._current_job_id / "job_config.json"
        c_data = {}
        if conf_file.exists():
            try:
                c_data = json.loads(conf_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        male_voice = c_data.get("default_male_voice") or cfg.tts.default_male_voice
        female_voice = c_data.get("default_female_voice") or cfg.tts.default_female_voice
        target_voice = female_voice if selected_gender == "female" else male_voice

        c_data["single_voice_gender"] = selected_gender
        try:
            conf_file.write_text(json.dumps(c_data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

        if not self._chk_detect_gender.isChecked() and hasattr(self, "_sub_editor") and self._sub_editor:
            self._sub_editor.update_all_voices(target_voice)
            # Sync in-memory segments and backend
            for s in self._current_segments:
                s["voice"] = target_voice
                s["gender"] = selected_gender
            batch_payload = [{"id": s.get("id", i + 1), "voice": target_voice, "gender": selected_gender} for i, s in enumerate(self._current_segments)]
            if batch_payload:
                w = BatchUpdateSegmentsWorker(self._current_job_id, batch_payload, rebuild_audio=False)
                self._workers.append(w)
                w.start()

    def _on_gender_mode_toggled(self, is_multi: bool):
        if not self._current_job_id:
            return
        conf_file = Path("workspace") / self._current_job_id / "job_config.json"
        c_data = {}
        if conf_file.exists():
            try:
                c_data = json.loads(conf_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        c_data["detect_gender"] = is_multi
        try:
            conf_file.write_text(json.dumps(c_data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        if not is_multi:
            self._on_single_gender_changed(self._combo_single_gender.currentIndex())

    def _on_segment_voice_changed(self, seg_idx: int, voice: str):
        if not self._current_job_id:
            return
        w = UpdateSegmentWorker(self._current_job_id, seg_idx, {"voice": voice})
        w.finished.connect(lambda i, r: None)
        w.error.connect(lambda i, e: None)
        self._workers.append(w)
        w.start()

    def _on_segment_moved(self, seg_idx: int, new_start: float, new_end: float):
        if not self._current_job_id:
            return
        from ui.widgets.timeline_ruler import TimelineWidget
        # 1. Update in-memory segment timing and rescale any slices
        payload = {"start": round(new_start, 3), "end": round(new_end, 3)}
        for s in self._current_segments:
            if s.get("id") == seg_idx or s.get("index") == seg_idx:
                s["start"] = round(new_start, 3)
                s["end"] = round(new_end, 3)
                if s.get("sub_slices") and len(s["sub_slices"]) > 1:
                    s["sub_slices"] = TimelineWidget._recompute_slices(s["sub_slices"], s["start"], s["end"])
                    payload["sub_slices"] = s["sub_slices"]
                break

        # 2. Update table row time display in-place without reloading video
        if hasattr(self, "_sub_editor") and self._sub_editor:
            self._sub_editor.update_segment_times(seg_idx, new_start, new_end)

        # 3. Save to backend asynchronously without resetting playhead to t=0
        w = UpdateSegmentWorker(self._current_job_id, seg_idx, payload)
        self._workers.append(w)
        w.start()

    def _on_timeline_seek(self, t: float):
        self._video_player.seek(t)

    def _on_player_pos_changed(self, pos: float):
        self._timeline.set_playhead(pos)
        if hasattr(self, "_video_player") and self._video_player:
            from ui.widgets.timeline_ruler import TimelineWidget
            current_text = None
            for seg in getattr(self, "_current_segments", []):
                st = float(seg.get("start", 0.0))
                en = float(seg.get("end", 0.0))
                if st <= pos <= en:
                    if seg.get("mute_sub"):
                        break
                    raw_text = (seg.get("vi_text") or seg.get("src_text") or "").strip()
                    if raw_text:
                        has_audio = bool(seg.get("tts_dur") or seg.get("tts_file"))

                        # 1. If explicit cues
                        if seg.get("cues") and len(seg["cues"]) > 0:
                            for cue in seg["cues"]:
                                c_st = float(cue.get("start", st))
                                c_en = float(cue.get("end", en))
                                if c_st <= pos <= c_en:
                                    current_text = cue.get("text", "")
                                    break
                            if not current_text and seg["cues"]:
                                current_text = seg["cues"][-1].get("text", "")

                        # 2. If explicit sub_slices
                        elif seg.get("sub_slices") and len(seg["sub_slices"]) > 1:
                            slices = TimelineWidget._recompute_slices(seg["sub_slices"], st, en)
                            for sl in slices:
                                if sl["start"] <= pos <= sl["end"]:
                                    current_text = sl["text"]
                                    break
                            if not current_text and slices:
                                current_text = slices[-1]["text"]

                        # 3. If text contains \n
                        elif "\n" in raw_text and len(raw_text.splitlines()) > 1:
                            lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
                            slices = TimelineWidget._build_slices_from_lines(lines, st, en)
                            for sl in slices:
                                if sl["start"] <= pos <= sl["end"]:
                                    current_text = sl["text"]
                                    break
                            if not current_text and slices:
                                current_text = slices[-1]["text"]

                        # 4. Only auto-slice long sentences (>15 words) IF TTS audio already exists
                        elif has_audio and len(raw_text.split()) > 15:
                            from dubstudio.subtitles.ass import split_subtitle_slices
                            slices = split_subtitle_slices(raw_text, st, en, target_words=12, max_words=15)
                            for sl in slices:
                                if sl["start"] <= pos <= sl["end"]:
                                    current_text = sl["text"]
                                    break
                            if not current_text and slices:
                                current_text = slices[-1]["text"]

                        # 5. Otherwise show full raw text
                        else:
                            current_text = raw_text.replace("\n", " ")
                    break
            if current_text:
                style = getattr(self, "_sub_style", None) or {
                    "position": "bottom", "margin_v": 35, "font_size": 22,
                    "has_box": True, "box_mode": "wrap_text", "font_name": "Arial",
                    "primary_color": "#ffffff", "box_color": "#000000", "box_opacity": 0.6
                }
                self._video_player.update_subtitle_overlay(current_text, style, visible=True)
            else:
                self._video_player.update_subtitle_overlay("", {}, visible=False)

    def _on_video_duration_known(self, dur: float):
        self._timeline.set_duration(dur)

    def _on_segment_selected(self, seg_idx: int):
        for i, s in enumerate(self._current_segments):
            if s.get("id") == seg_idx or s.get("index") == seg_idx or (i + 1) == seg_idx:
                start = float(s.get("start", 0.0))
                self._video_player.seek(start)
                self._timeline.set_playhead(start)
                break

    def _on_timeline_seg_selected(self, seg_idx: int):
        self._sub_editor.highlight_segment(seg_idx)
        self._on_segment_selected(seg_idx)

    def _on_add_segment(self):
        """Add a new subtitle segment at current playhead position."""
        if not self._current_job_id:
            QMessageBox.warning(self, "Chưa chọn tác vụ", "Vui lòng chọn hoặc nạp một dự án video trước!")
            return

        pos = 0.0
        if hasattr(self, "_video_player") and self._video_player:
            try:
                pos = self._video_player.get_position()
            except Exception:
                pos = 0.0
        pos = round(pos, 2)
        end_pos = round(pos + 2.0, 2)

        text, ok = QInputDialog.getText(
            self, "Thêm đoạn phụ đề mới",
            f"Nhập nội dung phụ đề tiếng Việt (bắt đầu tại {pos:.2f}s):",
            text="Lời thoại mới",
        )
        if not ok or not text.strip():
            return

        from dubstudio.config import AppConfig
        cfg = AppConfig.load()
        sel_g = self._combo_single_gender.currentData() if hasattr(self, "_combo_single_gender") else "female"
        new_voice = cfg.tts.default_female_voice if sel_g == "female" else cfg.tts.default_male_voice
        payload = {
            "start": pos,
            "end": end_pos,
            "vi_text": text.strip(),
            "voice": new_voice,
        }
        w = CreateSegmentWorker(self._current_job_id, payload)
        w.finished.connect(lambda res: self._load_current_job())
        w.error.connect(lambda err: QMessageBox.warning(self, "Lỗi thêm đoạn", f"Không thể thêm đoạn thoại: {err}"))
        self._workers.append(w)
        w.start()

    def _on_split_segment(self):
        """Split/slice currently selected segment."""
        if not self._current_job_id:
            return
        selected_ids = self._sub_editor.get_selected_segment_ids()
        if not selected_ids:
            QMessageBox.information(self, "Chọn câu phụ đề", "Vui lòng chọn hoặc nhấp đúp vào một dòng phụ đề trong bảng để chỉnh sửa / chia lát cắt!")
            return
        self._on_split_segment_by_id(selected_ids[0])

    def _on_split_segment_by_id(self, seg_id: int):
        """Open edit dialog and save times, text, speed, and slices for specific segment."""
        if not self._current_job_id:
            return
        seg = next((s for s in self._current_segments if s.get("id") == seg_id), None)
        if not seg:
            return
        dialog = EditSegmentDialog(seg, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_start, new_end = dialog.get_times()
            new_speed = dialog.get_speed()
            parts = dialog.get_parts()
            slices = dialog.get_slices()
            new_vi_text = "\n".join(parts) if len(parts) > 1 else (parts[0] if parts else "")

            # 1. Update in-memory segment
            seg["start"] = new_start
            seg["end"] = new_end
            seg["dur"] = round(new_end - new_start, 3)
            seg["vi_text"] = new_vi_text
            seg["speed"] = new_speed
            seg["sub_slices"] = slices if len(slices) > 1 else None
            cues = [{"start": s["start"], "end": s["end"], "text": s["text"], "locked": True} for s in slices] if slices else None
            seg["cues"] = cues

            # 2. Update table display in-place (keeps single row)
            if hasattr(self, "_sub_editor") and self._sub_editor:
                self._sub_editor.update_segment_times(seg_id, new_start, new_end)
                self._sub_editor.update_segment_text(seg_id, new_vi_text)

            # 3. Update timeline track 0 blocks & slices immediately
            if hasattr(self, "_timeline") and self._timeline:
                total_dur = getattr(self._timeline._canvas, "_duration", 0.0)
                self._timeline.set_segments(self._current_segments, total_dur)

            # 4. Save to backend asynchronously
            payload = {
                "start": new_start,
                "end": new_end,
                "vi_text": new_vi_text,
                "speed": new_speed,
            }
            if seg["sub_slices"]:
                payload["sub_slices"] = seg["sub_slices"]
            if seg["cues"]:
                payload["cues"] = seg["cues"]
            w = UpdateSegmentWorker(self._current_job_id, seg_id, payload)
            self._workers.append(w)
            w.start()

    def _on_delete_segment(self):
        """Delete currently selected segments (single or batch)."""
        if not self._current_job_id:
            return
        selected_ids = self._sub_editor.get_selected_segment_ids()
        if not selected_ids:
            QMessageBox.information(self, "Chọn đoạn cần xóa", "Vui lòng chọn một dòng phụ đề trong bảng để xóa!")
            return
        self._on_delete_segments_batch(selected_ids)

    def _on_delete_segment_by_id(self, seg_id: int):
        """Delete specific segment by id."""
        self._on_delete_segments_batch([seg_id])

    def _on_delete_segments_batch(self, seg_ids: list):
        """Delete multiple segments by ids."""
        if not self._current_job_id or not seg_ids:
            return
        if len(seg_ids) == 1:
            title = "Xác nhận xóa đoạn thoại"
            msg = f"Bạn có chắc muốn xóa đoạn thoại #{seg_ids[0]}?"
        else:
            title = "Xác nhận xóa nhiều đoạn thoại"
            msg = f"Bạn có chắc muốn xóa hoàn toàn {len(seg_ids)} đoạn thoại đã chọn khỏi video?"

        reply = QMessageBox.question(
            self, title, msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        cur_pos = self._video_player.get_position() if hasattr(self, "_video_player") and self._video_player else 0.0

        w = BatchDeleteSegmentsWorker(self._current_job_id, seg_ids)
        w.finished.connect(lambda res: self._load_current_job(restore_pos=cur_pos))
        w.error.connect(lambda err: QMessageBox.warning(self, "Lỗi xóa đoạn", f"Không thể xóa các đoạn thoại: {err}"))
        self._workers.append(w)
        w.start()

    def _on_toggle_tts_batch(self, seg_ids: list, mute: bool):
        """Toggle TTS mute state for selected segments."""
        if not self._current_job_id or not seg_ids:
            return
        id_set = set(seg_ids)
        updates = [{"id": sid, "mute_tts": mute} for sid in seg_ids]
        for s in self._current_segments:
            if s.get("id") in id_set:
                s["mute_tts"] = mute
        self._sub_editor.load_segments(self._current_segments)
        self._timeline.set_segments(self._current_segments)
        if hasattr(self, "_video_player") and self._video_player:
            self._on_player_pos_changed(self._video_player.get_position())

        def _on_audio_rebuilt(res):
            if hasattr(self, "_video_player") and self._video_player and self._current_job_id:
                ws_dir = Path("workspace") / self._current_job_id
                self._video_player.setup_job_audio(workspace_dir=ws_dir, is_rendered_video=False)

        w = BatchUpdateSegmentsWorker(self._current_job_id, updates, rebuild_audio=True)
        w.finished.connect(_on_audio_rebuilt)
        self._workers.append(w)
        w.start()

    def _on_toggle_sub_batch(self, seg_ids: list, mute: bool):
        """Toggle subtitle visibility for selected segments."""
        if not self._current_job_id or not seg_ids:
            return
        id_set = set(seg_ids)
        updates = [{"id": sid, "mute_sub": mute} for sid in seg_ids]
        for s in self._current_segments:
            if s.get("id") in id_set:
                s["mute_sub"] = mute
        self._sub_editor.load_segments(self._current_segments)
        self._timeline.set_segments(self._current_segments)
        if hasattr(self, "_video_player") and self._video_player:
            self._on_player_pos_changed(self._video_player.get_position())
        w = BatchUpdateSegmentsWorker(self._current_job_id, updates, rebuild_audio=False)
        self._workers.append(w)
        w.start()

    def _on_timeline_segment_context_menu(self, seg_idx: int, global_pos: QPoint):
        """Right-click on timeline block opens the minimal context menu."""
        self._sub_editor.highlight_segment(seg_idx)
        self._show_segment_context_menu([seg_idx], global_pos)

    def _show_segment_context_menu(self, seg_ids: list, global_pos: QPoint):
        """Unified minimal right-click context menu (Only Toggle Subtitle & Toggle TTS)."""
        if not seg_ids:
            return
        menu = QMenu(self)
        count_suffix = f" ({len(seg_ids)} đoạn)" if len(seg_ids) > 1 else ""

        # 1. Bật/Tắt phụ đề
        is_any_sub_muted = any(s.get("mute_sub") for s in self._current_segments if s.get("id") in seg_ids)
        if is_any_sub_muted:
            act_sub = menu.addAction(f"Bật lại phụ đề{count_suffix}")
            act_sub.setIcon(get_icon("subtitles", "#10b981", "#10b981", 15))
            act_sub.triggered.connect(lambda: self._on_toggle_sub_batch(seg_ids, False))
        else:
            act_sub = menu.addAction(f"Tắt phụ đề{count_suffix}")
            act_sub.setIcon(get_icon("subtitles", "#ef4444", "#ef4444", 15))
            act_sub.triggered.connect(lambda: self._on_toggle_sub_batch(seg_ids, True))

        menu.addSeparator()

        # 2. Bật/Tắt giọng đọc TTS
        is_any_tts_muted = any(s.get("mute_tts") for s in self._current_segments if s.get("id") in seg_ids)
        if is_any_tts_muted:
            act_tts = menu.addAction(f"Bật lại giọng đọc TTS{count_suffix}")
            act_tts.setIcon(get_icon("volume-2", "#10b981", "#10b981", 15))
            act_tts.triggered.connect(lambda: self._on_toggle_tts_batch(seg_ids, False))
        else:
            act_tts = menu.addAction(f"Tắt giọng đọc TTS{count_suffix}")
            act_tts.setIcon(get_icon("volume-x", "#ef4444", "#ef4444", 15))
            act_tts.triggered.connect(lambda: self._on_toggle_tts_batch(seg_ids, True))

        menu.exec(global_pos)

    def _load_orig_ranges(self):
        """Load independent original audio ranges for current job."""
        self._orig_ranges = []
        if not self._current_job_id:
            if hasattr(self, "_timeline") and self._timeline:
                self._timeline.set_orig_ranges([])
            return
        cfg = AppConfig.load()
        f = cfg.general.workspace_dir / self._current_job_id / "orig_audio_ranges.json"
        if f.exists():
            try:
                self._orig_ranges = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                self._orig_ranges = []
        if hasattr(self, "_timeline") and self._timeline:
            self._timeline.set_orig_ranges(self._orig_ranges)

    def _save_orig_ranges(self):
        """Persist independent original audio ranges and sync with mix_settings.json."""
        if not self._current_job_id:
            return
        cfg = AppConfig.load()
        ws = cfg.general.workspace_dir / self._current_job_id
        ws.mkdir(parents=True, exist_ok=True)
        f = ws / "orig_audio_ranges.json"
        f.write_text(json.dumps(self._orig_ranges, ensure_ascii=False, indent=2), encoding="utf-8")

        # Sync with mix_settings.json
        mix_f = ws / "mix_settings.json"
        m_data = {}
        if mix_f.exists():
            try:
                m_data = json.loads(mix_f.read_text(encoding="utf-8"))
            except Exception:
                m_data = {}
        m_data["keep_original_ranges"] = [[float(r["start"]), float(r["end"])] for r in self._orig_ranges]
        mix_f.write_text(json.dumps(m_data, ensure_ascii=False, indent=2), encoding="utf-8")

        # Immediately update preview player's BGM stem with true original audio passthrough
        if hasattr(self, "_video_player") and self._video_player:
            self._video_player.reload_bgm_track(ws)

    def _on_orig_range_created(self, st: float, en: float):
        """Handle quick creation via right-click drag on Track 2 (Âm gốc)."""
        if not self._current_job_id:
            return
        st = round(max(0.0, st), 2)
        en = round(max(st + 0.15, en), 2)
        new_id = (max([r.get("id", 0) for r in self._orig_ranges], default=0) + 1) if self._orig_ranges else 1
        self._orig_ranges.append({"id": new_id, "start": st, "end": en, "label": "Âm gốc"})
        self._save_orig_ranges()
        self._timeline.set_orig_ranges(self._orig_ranges)

    def _on_add_orig_range(self):
        """Open popup to khoanh vùng giữ âm thanh gốc directly on video."""
        if not self._current_job_id:
            QMessageBox.warning(self, "Chưa chọn video", "Vui lòng mở một video trước khi khoanh vùng âm thanh gốc!")
            return
        cur_t = 0.0
        if hasattr(self, "_video_player") and self._video_player:
            cur_t = self._video_player.get_position()
        elif hasattr(self, "_timeline") and self._timeline:
            cur_t = getattr(self._timeline._canvas, "_playhead", 0.0)

        dur = 600.0
        if hasattr(self, "_video_player") and self._video_player:
            dur = getattr(self._video_player, "_duration_sec", 600.0) or 600.0
        elif hasattr(self, "_timeline") and self._timeline:
            dur = getattr(self._timeline._canvas, "_duration", 600.0)

        dlg = AddOrigRangeDialog(cur_t, dur, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            st, en = dlg.get_range()
            new_id = (max([r.get("id", 0) for r in self._orig_ranges], default=0) + 1) if self._orig_ranges else 1
            self._orig_ranges.append({"id": new_id, "start": st, "end": en, "label": "Âm gốc"})
            self._save_orig_ranges()
            self._timeline.set_orig_ranges(self._orig_ranges)

    def _on_orig_range_changed(self, rid: int, new_st: float, new_en: float):
        """Handle drag or resize of an original audio range on timeline."""
        for r in self._orig_ranges:
            if r.get("id") == rid:
                r["start"] = new_st
                r["end"] = new_en
                break
        self._save_orig_ranges()

    def _on_orig_range_deleted(self, rid: int):
        """Delete an original audio range."""
        self._orig_ranges = [r for r in self._orig_ranges if r.get("id") != rid]
        self._save_orig_ranges()
        self._timeline.set_orig_ranges(self._orig_ranges)

    def _on_merge_segments(self):
        """Merge selected segments into one."""
        if not self._current_job_id:
            return
        selected_ids = self._sub_editor.get_selected_segment_ids()
        if len(selected_ids) < 2:
            QMessageBox.information(
                self, "Chọn đoạn cần gộp",
                "Vui lòng chọn ít nhất 2 dòng phụ đề liên tiếp để gộp (giữ phím Ctrl hoặc kéo chuột)!"
            )
            return
        self._on_merge_segments_by_ids(selected_ids)

    def _on_merge_segments_by_ids(self, seg_ids: list):
        """Merge specific segments by ids."""
        if not self._current_job_id:
            return
        w = MergeSegmentsWorker(self._current_job_id, seg_ids)
        w.finished.connect(lambda res: self._load_current_job())
        w.error.connect(lambda err: QMessageBox.warning(self, "Lỗi gộp đoạn", f"Không thể gộp các đoạn thoại: {err}"))
        self._workers.append(w)
        w.start()

    def _on_goto_export(self):
        """Navigate to Subtitle & Export Tab with current job."""
        if self._current_job_id:
            self.goto_export_requested.emit(self._current_job_id)
        else:
            QMessageBox.warning(self, "Chưa chọn tác vụ", "Vui lòng chọn hoặc thêm một tác vụ video trước!")

    def unload_job(self, job_id: Optional[str] = None):
        """Unload video and media players to release Windows file locks."""
        if job_id is None or self._current_job_id == job_id:
            try:
                self._video_player.unload()
            except Exception:
                pass
            if hasattr(self, "_seg_player") and self._seg_player:
                try:
                    self._seg_player.stop()
                    self._seg_player.setSource(QUrl())
                except Exception:
                    pass
            self._current_job_id = None
            self._current_video_path = None
            self._current_segments = []
            try:
                self._sub_editor.clear()
            except Exception:
                pass
            try:
                self._timeline.set_segments([])
            except Exception:
                pass

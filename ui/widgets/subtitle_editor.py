"""Subtitle editor table widget with per-row voice, speed, regen controls, and Find & Replace bar."""
from __future__ import annotations

import re
from typing import Callable, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QSize
from PyQt6.QtGui import QColor, QContextMenuEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.icons import get_icon


ALL_VOICES = [
    "Minh Đức", "Hải Đăng", "Quốc Tuấn", "Quang Sơn", "Thiện Minh",
    "Minh Triết", "Đức Trí", "Thái Sơn", "Xuân Vĩnh", "Thanh Bình",
    "Phạm Tuyên", "Thiền Tâm Đức", "Adam", "Adam bựa",
    "Quỳnh Anh", "Mai Anh", "Trúc Ly", "Thùy Dung", "Ngọc Huyền",
    "Ngọc Trân", "Ngọc Linh", "Đoan Trang", "Thục Đoan", "Mỹ Duyên", "Kim Thanh",
]

MALE_VOICES = [v for v in ALL_VOICES if v in {
    "Minh Đức", "Hải Đăng", "Quốc Tuấn", "Quang Sơn", "Thiện Minh",
    "Minh Triết", "Đức Trí", "Thái Sơn", "Xuân Vĩnh", "Thanh Bình",
    "Phạm Tuyên", "Thiền Tâm Đức", "Adam", "Adam bựa",
}]

FEMALE_VOICES = [v for v in ALL_VOICES if v not in set(MALE_VOICES)]


class NoScrollComboBox(QComboBox):
    """ComboBox that ignores mouse wheel scrolling when closed and prevents hover-selection."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def wheelEvent(self, e):
        if self.view() and self.view().isVisible():
            super().wheelEvent(e)
        else:
            e.ignore()

    def mouseMoveEvent(self, e):
        e.accept()


class VoiceComboDelegate(QStyledItemDelegate):
    """Zero-freeze item delegate for per-row voice dropdown selection."""
    def __init__(self, parent=None):
        super().__init__(parent)

    def createEditor(self, parent, option, index):
        combo = NoScrollComboBox(parent)
        combo.addItems(MALE_VOICES)
        combo.insertSeparator(len(MALE_VOICES))
        combo.addItems(FEMALE_VOICES)
        return combo

    def setEditorData(self, editor, index):
        current_text = index.data(Qt.ItemDataRole.DisplayRole)
        all_items = MALE_VOICES + FEMALE_VOICES
        if current_text in all_items:
            pos = all_items.index(current_text) if current_text in all_items else 0
            combo_idx = pos if pos < len(MALE_VOICES) else pos + 1
            editor.setCurrentIndex(combo_idx)

    def setModelData(self, editor, model, index):
        new_voice = editor.currentText()
        if new_voice:
            model.setData(index, new_voice, Qt.ItemDataRole.DisplayRole)
            table = self.parent()
            if table and hasattr(table, "segment_voice_changed"):
                row = index.row()
                item_idx = table.item(row, table.COL_IDX)
                if item_idx:
                    seg_idx = item_idx.data(Qt.ItemDataRole.UserRole)
                    if seg_idx is not None:
                        table.segment_voice_changed.emit(int(seg_idx), new_voice)
                        if hasattr(table, "_segments"):
                            for s in table._segments:
                                if s.get("id") == seg_idx:
                                    s["voice"] = new_voice
                                    break


class SubtitleEditorWidget(QTableWidget):
    """
    Table with columns:
    #  | Thời gian | Nguồn (ZH) | Dịch (VI) | Giọng | Nghe
    """
    regen_requested = pyqtSignal(int, str, str, float)  # idx, text, voice, speed
    play_audio_requested = pyqtSignal(int)               # idx
    segment_text_changed = pyqtSignal(int, str)          # idx, new_text
    segments_batch_changed = pyqtSignal(list)            # [{"id": int, "vi_text": str}, ...]
    segment_voice_changed = pyqtSignal(int, str)         # idx, voice
    segment_selected = pyqtSignal(int)                   # idx
    add_segment_requested = pyqtSignal()
    delete_segment_requested = pyqtSignal(int)            # seg_id
    delete_segments_requested = pyqtSignal(list)          # [seg_id, ...]
    delete_tts_requested = pyqtSignal(list)               # [seg_id, ...]
    delete_sub_requested = pyqtSignal(list)               # [seg_id, ...]
    toggle_tts_requested = pyqtSignal(list, bool)         # [seg_id, ...], mute_bool
    toggle_sub_requested = pyqtSignal(list, bool)         # [seg_id, ...], mute_sub_bool
    toggle_orig_audio_requested = pyqtSignal(list, bool)  # [seg_id, ...], enable_bool
    merge_segments_requested = pyqtSignal(list)           # list of seg_ids
    split_segment_requested = pyqtSignal(int)             # seg_id

    COL_IDX = 0
    COL_TIME = 1
    COL_ZH = 2
    COL_VI = 3
    COL_VOICE = 4
    COL_ACTION = 5
    NUM_COLS = 6

    def __init__(self, parent=None):
        super().__init__(0, self.NUM_COLS, parent)
        self._segments: List[dict] = []
        self._default_voice = "Minh Đức"
        self._busy_rows: set = set()
        self._setup_table()

    def _setup_table(self):
        self.setMinimumWidth(480)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        headers = ["#", "Thời gian", "Nguồn (ZH)", "Dịch (VI)", "Giọng", "Nghe"]
        self.setHorizontalHeaderLabels(headers)

        hh = self.horizontalHeader()
        hh.setStyleSheet("QHeaderView::section { padding: 8px 6px; background-color: #171B26; color: #94A3B8; border: none; border-bottom: 1px solid #262C3A; font-weight: 600; font-size: 11px; }")
        hh.setSectionResizeMode(self.COL_IDX, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(self.COL_TIME, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(self.COL_ZH, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(self.COL_VI, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(self.COL_VOICE, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(self.COL_ACTION, QHeaderView.ResizeMode.Fixed)

        self.setColumnWidth(self.COL_IDX, 46)
        self.setColumnWidth(self.COL_TIME, 126)
        self.setColumnWidth(self.COL_ZH, 115)
        self.setColumnWidth(self.COL_VOICE, 115)
        self.setColumnWidth(self.COL_ACTION, 58)

        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.SelectedClicked |
                             QAbstractItemView.EditTrigger.EditKeyPressed)
        self.setWordWrap(True)
        self.verticalHeader().setDefaultSectionSize(38)
        self.setShowGrid(False)
        self.setIconSize(QSize(18, 18))
        self.setMouseTracking(False)
        self.viewport().setMouseTracking(False)
        self.setItemDelegateForColumn(self.COL_VOICE, VoiceComboDelegate(self))

        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.cellClicked.connect(self._on_cell_clicked)
        self.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.itemChanged.connect(self._on_item_changed)

    def mouseMoveEvent(self, event):
        # Block mouse hover from triggering row selection without click
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            event.accept()
            return
        super().mouseMoveEvent(event)

    def _on_cell_double_clicked(self, row: int, col: int):
        item = self.item(row, self.COL_IDX)
        if item:
            idx = item.data(Qt.ItemDataRole.UserRole)
            if idx is not None:
                self.split_segment_requested.emit(int(idx))

    def _on_item_changed(self, item: QTableWidgetItem):
        if item.column() == self.COL_VI:
            seg_idx = item.data(Qt.ItemDataRole.UserRole)
            if seg_idx is not None:
                self.segment_text_changed.emit(int(seg_idx), item.text())

    def update_segment_text(self, seg_idx: int, new_text: str):
        """Update text display for a segment row without reloading entire table."""
        for r in range(self.rowCount()):
            item_idx = self.item(r, self.COL_IDX)
            if item_idx and item_idx.data(Qt.ItemDataRole.UserRole) == seg_idx:
                item_vi = self.item(r, self.COL_VI)
                if item_vi:
                    self.blockSignals(True)
                    item_vi.setText(new_text)
                    self.blockSignals(False)
                break

    def set_default_voice(self, voice: str):
        self._default_voice = voice

    def update_all_voices(self, voice: str):
        """Update voice in all table rows and in the internal segments list."""
        self._default_voice = voice
        for r in range(self.rowCount()):
            combo = self.cellWidget(r, self.COL_VOICE)
            if isinstance(combo, QComboBox):
                all_items = MALE_VOICES + FEMALE_VOICES
                pos = all_items.index(voice) if voice in all_items else -1
                if pos >= 0:
                    combo_idx = pos if pos < len(MALE_VOICES) else pos + 1
                    combo.blockSignals(True)
                    combo.setCurrentIndex(combo_idx)
                    combo.blockSignals(False)
        for s in self._segments:
            s["voice"] = voice

    def load_segments(self, segments: List[dict]):
        self._segments = segments
        self.setUpdatesEnabled(False)
        self.blockSignals(True)
        try:
            self.setRowCount(0)
            for seg in segments:
                self._add_row(seg)
        finally:
            self.blockSignals(False)
            self.setUpdatesEnabled(True)

    def set_segments(self, segments: List[dict]):
        """Alias for load_segments."""
        self.load_segments(segments)

    def clear(self):
        """Clear all subtitle rows."""
        self.load_segments([])

    def update_segment_times(self, seg_idx: int, start: float, end: float):
        """Update time display for a segment row without reloading entire table."""
        for r in range(self.rowCount()):
            item_vi = self.item(r, self.COL_VI)
            if item_vi and item_vi.data(Qt.ItemDataRole.UserRole) == seg_idx:
                time_str = f"{_fmt_time(start)} → {_fmt_time(end)}"
                item_time = self.item(r, self.COL_TIME)
                if item_time:
                    item_time.setText(time_str)
                break

    def cellWidget(self, row: int, col: int):
        w = super().cellWidget(row, col)
        if w is not None:
            return w
        if col == self.COL_VOICE:
            item_voice = self.item(row, self.COL_VOICE)
            voice = item_voice.text() if item_voice else self._default_voice
            combo = self._create_voice_combo(row, voice)
            super().setCellWidget(row, col, combo)
            return combo
        elif col == self.COL_ACTION:
            w_act = self._create_action_widget(row)
            super().setCellWidget(row, col, w_act)
            return w_act
        return None

    def _create_voice_combo(self, row: int, voice: str) -> NoScrollComboBox:
        item_idx = self.item(row, self.COL_IDX)
        idx = item_idx.data(Qt.ItemDataRole.UserRole) if item_idx else row
        combo = NoScrollComboBox(self)
        combo.addItems(MALE_VOICES)
        combo.insertSeparator(len(MALE_VOICES))
        combo.addItems(FEMALE_VOICES)
        if voice in ALL_VOICES:
            all_items = MALE_VOICES + FEMALE_VOICES
            pos = all_items.index(voice) if voice in all_items else 0
            combo_idx = pos if pos < len(MALE_VOICES) else pos + 1
            combo.setCurrentIndex(combo_idx)
        combo.setProperty("seg_idx", idx)
        combo.currentTextChanged.connect(lambda v, i=idx, r=row: self._on_voice_changed(r, i, v))
        return combo

    def _on_voice_changed(self, row: int, seg_idx: int, new_voice: str):
        it = self.item(row, self.COL_VOICE)
        if it:
            it.setText(new_voice)
        for s in self._segments:
            if s.get("id") == seg_idx:
                s["voice"] = new_voice
                break
        self.segment_voice_changed.emit(int(seg_idx), new_voice)

    def _create_action_widget(self, row: int) -> QWidget:
        item_idx = self.item(row, self.COL_IDX)
        idx = item_idx.data(Qt.ItemDataRole.UserRole) if item_idx else row
        action_widget = QWidget(self)
        action_layout = QHBoxLayout(action_widget)
        action_layout.setContentsMargins(0, 2, 0, 2)
        action_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_play = QPushButton()
        item_act = self.item(row, self.COL_ACTION)
        icon = item_act.icon() if item_act else get_icon("volume-2", "#10b981", "#10b981", 14)
        btn_play.setIcon(icon)
        btn_play.setFixedSize(30, 26)
        btn_play.setProperty("seg_idx", idx)
        btn_play.clicked.connect(lambda _, i=idx: self.play_audio_requested.emit(int(i)))
        action_layout.addWidget(btn_play)
        return action_widget

    def _add_row(self, seg: dict):
        row = self.rowCount()
        self.insertRow(row)
        idx = seg.get("id", seg.get("index", row + 1))
        start = seg.get("start", 0.0)
        end = seg.get("end", 0.0)
        zh_text = seg.get("zh") or seg.get("zh_text") or seg.get("src_text") or ""
        vi_text = seg.get("vi_text", "")
        voice = seg.get("voice", self._default_voice) or self._default_voice
        speed = float(seg.get("speed", 1.0) or 1.0)

        mute_tts = bool(seg.get("mute_tts"))
        mute_sub = bool(seg.get("mute_sub"))

        # Index (read-only)
        item_idx = QTableWidgetItem(str(row + 1))
        item_idx.setData(Qt.ItemDataRole.UserRole, idx)  # store seg idx
        item_idx.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        item_idx.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, self.COL_IDX, item_idx)

        # Time (read-only)
        time_str = f"{_fmt_time(start)} → {_fmt_time(end)}"
        item_time = QTableWidgetItem(time_str)
        item_time.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        item_time.setForeground(Qt.GlobalColor.gray)
        self.setItem(row, self.COL_TIME, item_time)

        # ZH source (read-only)
        item_zh = QTableWidgetItem(zh_text)
        item_zh.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        item_zh.setForeground(Qt.GlobalColor.gray)
        self.setItem(row, self.COL_ZH, item_zh)

        # VI text (editable)
        item_vi = QTableWidgetItem(vi_text)
        item_vi.setData(Qt.ItemDataRole.UserRole, idx)  # store seg idx
        if mute_sub:
            item_vi.setForeground(QColor("#64748b"))
            item_vi.setToolTip("Phụ đề này đang TẮT (không hiển thị trên video). Nhấp chuột phải để bật lại.")
        elif mute_tts:
            item_vi.setToolTip("Phụ đề hiển thị trên video (Giọng đọc TTS đang tắt cho câu này)")
        self.setItem(row, self.COL_VI, item_vi)

        # Voice (Zero-widget delegate-managed item)
        item_voice = QTableWidgetItem(voice)
        item_voice.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, self.COL_VOICE, item_voice)

        # Action (Zero-widget icon item)
        item_action = QTableWidgetItem()
        item_action.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item_action.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        if mute_tts:
            item_action.setIcon(get_icon("volume-x", "#ef4444", "#ef4444", 16))
            item_action.setToolTip("Giọng đọc TTS đang TẮT. Nhấp chuột vào để nghe thử hoặc bấm chuột phải để bật lại.")
        else:
            item_action.setIcon(get_icon("volume-2", "#10b981", "#10b981", 16))
            item_action.setToolTip("Nghe thử âm thanh câu này")
        self.setItem(row, self.COL_ACTION, item_action)

    def _on_regen(self, row: int, seg_idx: int):
        it_v = self.item(row, self.COL_VOICE)
        voice = it_v.text().strip() if it_v else self._default_voice
        item_vi = self.item(row, self.COL_VI)
        vi_text = item_vi.text().strip() if item_vi else ""
        speed = 1.0
        for s in self._segments:
            if s.get("id") == seg_idx:
                fit_info = s.get("fit") if isinstance(s.get("fit"), dict) else {}
                speed_val = s.get("speed")
                if speed_val is None:
                    speed_val = fit_info.get("rate", 1.0)
                speed = float(speed_val or 1.0)
                break
        self.regen_requested.emit(seg_idx, vi_text, voice, speed)

    def _on_selection_changed(self):
        rows = self.selectedItems()
        if rows:
            item = self.item(rows[0].row(), self.COL_IDX)
            if item:
                idx = item.data(Qt.ItemDataRole.UserRole)
                if idx is not None:
                    self.segment_selected.emit(int(idx))

    def _on_cell_clicked(self, row: int, col: int):
        item = self.item(row, self.COL_IDX)
        if item:
            idx = item.data(Qt.ItemDataRole.UserRole)
            if idx is not None:
                self.segment_selected.emit(int(idx))
                if col == self.COL_ACTION:
                    self.play_audio_requested.emit(int(idx))

    def set_row_busy(self, seg_idx: int, busy: bool):
        """Show/hide spinner on play button for a segment."""
        for row in range(self.rowCount()):
            item = self.item(row, self.COL_IDX)
            if item and item.data(Qt.ItemDataRole.UserRole) == seg_idx:
                item_act = self.item(row, self.COL_ACTION)
                if item_act:
                    if busy:
                        item_act.setIcon(get_icon("spinner", "#ffffff", "#ffffff", 13))
                        self._busy_rows.add(row)
                    else:
                        item_act.setIcon(get_icon("volume-2", "#10b981", "#10b981", 14))
                        self._busy_rows.discard(row)
                w = super().cellWidget(row, self.COL_ACTION)
                if w:
                    btns = w.findChildren(QPushButton)
                    if btns:
                        btns[0].setIcon(get_icon("spinner" if busy else "volume-2", "#ffffff" if busy else "#10b981", "#10b981", 13))
                        btns[0].setEnabled(not busy)
                break

    def highlight_segment(self, seg_idx: int):
        """Scroll to and highlight the row for a segment."""
        for row in range(self.rowCount()):
            item = self.item(row, self.COL_IDX)
            if item and item.data(Qt.ItemDataRole.UserRole) == seg_idx:
                self.selectRow(row)
                self.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
                break

    def get_vi_text(self, seg_idx: int) -> str:
        for row in range(self.rowCount()):
            item = self.item(row, self.COL_VI)
            if item and self.item(row, self.COL_IDX) and \
               self.item(row, self.COL_IDX).data(Qt.ItemDataRole.UserRole) == seg_idx:
                return item.text()
        return ""

    def get_selected_segment_ids(self) -> List[int]:
        """Return list of segment IDs currently selected."""
        selected_rows = sorted(set(idx.row() for idx in self.selectedIndexes()))
        selected_ids = []
        for r in selected_rows:
            item = self.item(r, self.COL_IDX)
            if item:
                s_id = item.data(Qt.ItemDataRole.UserRole)
                if s_id is not None:
                    selected_ids.append(int(s_id))
        return selected_ids

    # ─── Find & Replace Engine ───
    def count_occurrences(self, query: str) -> int:
        if not query:
            return 0
        total = 0
        q_lower = query.lower()
        for r in range(self.rowCount()):
            item = self.item(r, self.COL_VI)
            if item and q_lower in item.text().lower():
                total += item.text().lower().count(q_lower)
        return total

    def find_text(self, query: str, start_row: int = 0) -> Optional[int]:
        if not query:
            return None
        q_lower = query.lower()
        num_rows = self.rowCount()
        if num_rows == 0:
            return None
        for i in range(num_rows):
            r = (start_row + i) % num_rows
            item = self.item(r, self.COL_VI)
            if item and q_lower in item.text().lower():
                self.selectRow(r)
                self.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
                return r
        return None

    def replace_at_row(self, row: int, query: str, replacement: str) -> bool:
        item = self.item(row, self.COL_VI)
        if not item or not query:
            return False
        orig_text = item.text()
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        if pattern.search(orig_text):
            new_text = pattern.sub(replacement, orig_text)
            item.setText(new_text)
            seg_idx = item.data(Qt.ItemDataRole.UserRole)
            if seg_idx is not None:
                sid = int(seg_idx)
                up_dict = {"id": sid, "vi_text": new_text, "tts_text": new_text}
                for s in self._segments:
                    if s.get("id") == sid or s.get("index") == sid:
                        s["vi_text"] = new_text
                        s["tts_text"] = new_text
                        if s.get("cues") and isinstance(s["cues"], list):
                            for c in s["cues"]:
                                if isinstance(c, dict) and "text" in c:
                                    c["text"] = pattern.sub(replacement, c["text"])
                            up_dict["cues"] = s["cues"]
                        if s.get("sub_slices") and isinstance(s["sub_slices"], list):
                            for sl in s["sub_slices"]:
                                if isinstance(sl, dict) and "text" in sl:
                                    sl["text"] = pattern.sub(replacement, sl["text"])
                            up_dict["sub_slices"] = s["sub_slices"]
                        break
                self.segments_batch_changed.emit([up_dict])
            return True
        return False

    def replace_all(self, query: str, replacement: str) -> int:
        if not query:
            return 0
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        count = 0
        updates = []
        self.blockSignals(True)
        try:
            for r in range(self.rowCount()):
                item = self.item(r, self.COL_VI)
                if item and pattern.search(item.text()):
                    new_text, n = pattern.subn(replacement, item.text())
                    count += n
                    item.setText(new_text)
                    seg_idx = item.data(Qt.ItemDataRole.UserRole)
                    if seg_idx is not None:
                        sid = int(seg_idx)
                        up_dict = {"id": sid, "vi_text": new_text, "tts_text": new_text}
                        for s in self._segments:
                            if s.get("id") == sid or s.get("index") == sid:
                                s["vi_text"] = new_text
                                s["tts_text"] = new_text
                                if s.get("cues") and isinstance(s["cues"], list):
                                    for c in s["cues"]:
                                        if isinstance(c, dict) and "text" in c:
                                            c["text"] = pattern.sub(replacement, c["text"])
                                    up_dict["cues"] = s["cues"]
                                if s.get("sub_slices") and isinstance(s["sub_slices"], list):
                                    for sl in s["sub_slices"]:
                                        if isinstance(sl, dict) and "text" in sl:
                                            sl["text"] = pattern.sub(replacement, sl["text"])
                                    up_dict["sub_slices"] = s["sub_slices"]
                                break
                        updates.append(up_dict)
        finally:
            self.blockSignals(False)
        if updates:
            self.segments_batch_changed.emit(updates)
        return count

    def delete_all(self, query: str) -> int:
        if not query:
            return 0
        pattern = re.compile(r'\s*' + re.escape(query) + r'\s*', re.IGNORECASE)
        count = 0
        updates = []
        self.blockSignals(True)
        try:
            for r in range(self.rowCount()):
                item = self.item(r, self.COL_VI)
                if item and pattern.search(item.text()):
                    new_text, n = pattern.subn(" ", item.text())
                    new_text = " ".join(new_text.split())
                    count += n
                    item.setText(new_text)
                    seg_idx = item.data(Qt.ItemDataRole.UserRole)
                    if seg_idx is not None:
                        sid = int(seg_idx)
                        up_dict = {"id": sid, "vi_text": new_text, "tts_text": new_text}
                        for s in self._segments:
                            if s.get("id") == sid or s.get("index") == sid:
                                s["vi_text"] = new_text
                                s["tts_text"] = new_text
                                if s.get("cues") and isinstance(s["cues"], list):
                                    for c in s["cues"]:
                                        if isinstance(c, dict) and "text" in c:
                                            c["text"] = " ".join(pattern.subn(" ", c["text"])[0].split())
                                    up_dict["cues"] = s["cues"]
                                if s.get("sub_slices") and isinstance(s["sub_slices"], list):
                                    for sl in s["sub_slices"]:
                                        if isinstance(sl, dict) and "text" in sl:
                                            sl["text"] = " ".join(pattern.subn(" ", sl["text"])[0].split())
                                    up_dict["sub_slices"] = s["sub_slices"]
                                break
                        updates.append(up_dict)
        finally:
            self.blockSignals(False)
        if updates:
            self.segments_batch_changed.emit(updates)
        return count

    def get_all_segments_data(self) -> List[dict]:
        """Collect current UI values of all segments for bulk sync."""
        data = []
        seg_dict = {s["id"]: s for s in self._segments if "id" in s}
        for r in range(self.rowCount()):
            item_idx = self.item(r, self.COL_IDX)
            item_vi = self.item(r, self.COL_VI)
            combo = self.cellWidget(r, self.COL_VOICE)
            s_id = None
            if item_idx and item_idx.data(Qt.ItemDataRole.UserRole) is not None:
                s_id = item_idx.data(Qt.ItemDataRole.UserRole)
            elif item_vi and item_vi.data(Qt.ItemDataRole.UserRole) is not None:
                s_id = item_vi.data(Qt.ItemDataRole.UserRole)

            if s_id is not None:
                sid_int = int(s_id)
                s_orig = seg_dict.get(sid_int, {})
                fit_info = s_orig.get("fit") if isinstance(s_orig.get("fit"), dict) else {}
                speed_val = s_orig.get("speed")
                if speed_val is None:
                    speed_val = fit_info.get("rate", 1.0)
                it_v = self.item(r, self.COL_VOICE)
                v_text = it_v.text().strip() if it_v else (combo.currentText() if combo else self._default_voice)
                data.append({
                    "id": sid_int,
                    "vi_text": item_vi.text().strip() if item_vi else "",
                    "voice": v_text,
                    "speed": float(speed_val or 1.0),
                    "mute_tts": bool(s_orig.get("mute_tts", False)),
                    "mute_sub": bool(s_orig.get("mute_sub", False)),
                })
        return data

    def set_selected_segments_voice(self, selected_ids: List[int], voice: str):
        """Set voice for all selected segment IDs in table and notify backend."""
        for r in range(self.rowCount()):
            item_idx = self.item(r, self.COL_IDX)
            item_vi = self.item(r, self.COL_VI)
            s_id = None
            if item_idx and item_idx.data(Qt.ItemDataRole.UserRole) is not None:
                s_id = item_idx.data(Qt.ItemDataRole.UserRole)
            elif item_vi and item_vi.data(Qt.ItemDataRole.UserRole) is not None:
                s_id = item_vi.data(Qt.ItemDataRole.UserRole)
            if s_id is not None and int(s_id) in selected_ids:
                it_v = self.item(r, self.COL_VOICE)
                if it_v:
                    it_v.setText(voice)
                combo = super().cellWidget(r, self.COL_VOICE)
                if isinstance(combo, QComboBox):
                    all_items = MALE_VOICES + FEMALE_VOICES
                    pos = all_items.index(voice) if voice in all_items else -1
                    if pos >= 0:
                        combo_idx = pos if pos < len(MALE_VOICES) else pos + 1
                        combo.blockSignals(True)
                        combo.setCurrentIndex(combo_idx)
                        combo.blockSignals(False)
                for s in self._segments:
                    if s.get("id") == int(s_id):
                        s["voice"] = voice
                self.segment_voice_changed.emit(int(s_id), voice)

    def _is_seg_tts_muted(self, seg_id: int) -> bool:
        for s in self._segments:
            if s.get("id") == seg_id:
                return bool(s.get("mute_tts"))
        return False

    def _is_seg_sub_muted(self, seg_id: int) -> bool:
        for s in self._segments:
            if s.get("id") == seg_id:
                return bool(s.get("mute_sub"))
        return False

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            if self.state() == QAbstractItemView.State.EditingState:
                super().keyPressEvent(event)
                return

            selected_ids = self.get_selected_segment_ids()
            if selected_ids:
                self.delete_segments_requested.emit(selected_ids)
                return

        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        """Minimal right-click menu: Only Toggle Subtitle and Toggle TTS."""
        selected_ids = self.get_selected_segment_ids()
        if not selected_ids:
            item = self.itemAt(event.pos())
            if item:
                r = item.row()
                idx_item = self.item(r, self.COL_IDX)
                if idx_item and idx_item.data(Qt.ItemDataRole.UserRole) is not None:
                    selected_ids = [int(idx_item.data(Qt.ItemDataRole.UserRole))]
                    self.selectRow(r)

        if not selected_ids:
            return

        menu = QMenu(self)
        count_suffix = f" ({len(selected_ids)} đoạn)" if len(selected_ids) > 1 else ""

        # 1. Bật/Tắt phụ đề
        is_any_sub_muted = any(self._is_seg_sub_muted(sid) for sid in selected_ids)
        if is_any_sub_muted:
            act_sub = menu.addAction(f"Bật lại phụ đề{count_suffix}")
            act_sub.setIcon(get_icon("subtitles", "#10b981", "#10b981", 15))
            act_sub.triggered.connect(lambda: self.toggle_sub_requested.emit(selected_ids, False))
        else:
            act_sub = menu.addAction(f"Tắt phụ đề{count_suffix}")
            act_sub.setIcon(get_icon("subtitles", "#ef4444", "#ef4444", 15))
            act_sub.triggered.connect(lambda: self.toggle_sub_requested.emit(selected_ids, True))

        menu.addSeparator()

        # 2. Bật/Tắt giọng đọc TTS
        is_any_tts_muted = any(self._is_seg_tts_muted(sid) for sid in selected_ids)
        if is_any_tts_muted:
            act_tts = menu.addAction(f"Bật lại giọng đọc TTS{count_suffix}")
            act_tts.setIcon(get_icon("volume-2", "#10b981", "#10b981", 15))
            act_tts.triggered.connect(lambda: self.toggle_tts_requested.emit(selected_ids, False))
        else:
            act_tts = menu.addAction(f"Tắt giọng đọc TTS{count_suffix}")
            act_tts.setIcon(get_icon("volume-x", "#ef4444", "#ef4444", 15))
            act_tts.triggered.connect(lambda: self.toggle_tts_requested.emit(selected_ids, True))

        menu.addSeparator()

        # 3. Đổi giọng đọc hàng loạt cho các câu đang chọn
        voice_menu = menu.addMenu(f"Đổi giọng đọc{count_suffix}")
        voice_menu.setIcon(get_icon("mic", "#38bdf8", "#38bdf8", 15))

        male_sub = voice_menu.addMenu("Giọng Nam")
        for v in MALE_VOICES:
            act = male_sub.addAction(v)
            act.triggered.connect(lambda checked=False, vc=v: self.set_selected_segments_voice(selected_ids, vc))

        female_sub = voice_menu.addMenu("Giọng Nữ")
        for v in FEMALE_VOICES:
            act = female_sub.addAction(v)
            act.triggered.connect(lambda checked=False, vc=v: self.set_selected_segments_voice(selected_ids, vc))

        menu.addSeparator()

        # 4. Xóa lời thoại đã chọn
        act_del = menu.addAction(f"Xóa lời thoại đã chọn{count_suffix} (Delete)")
        act_del.setIcon(get_icon("trash", "#ef4444", "#fca5a5", 15))
        act_del.triggered.connect(lambda: self.delete_segments_requested.emit(selected_ids))

        menu.exec(event.globalPos())


class FindReplaceBar(QWidget):
    """
    Search and replace toolbar for subtitles (Ctrl + F).
    Supports: Find Next, Replace, Replace All, and Delete All Found.
    """
    closed = pyqtSignal()

    def __init__(self, editor: SubtitleEditorWidget, parent=None):
        super().__init__(parent)
        self._editor = editor
        self._setup_ui()
        self.setVisible(False)

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)
        self.setStyleSheet("""
            FindReplaceBar {
                background-color: #171B26;
                border: 1px solid #262C3A;
                border-radius: 8px;
            }
            QLineEdit {
                background-color: #0B0D13;
                color: #F1F5F9;
                border: 1px solid #262C3A;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11.5px;
            }
            QLineEdit:focus {
                border: 1px solid #6366F1;
            }
            QPushButton {
                background-color: #1F2433;
                color: #E2E8F0;
                border: 1px solid #262C3A;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11.5px;
            }
            QPushButton:hover {
                background-color: #282F42;
                color: #ffffff;
                border-color: #3730A3;
            }
            QPushButton#primary {
                background-color: #6366F1;
                color: #ffffff;
                border: 1px solid #818CF8;
            }
            QPushButton#primary:hover {
                background-color: #4F46E5;
            }
            QPushButton#danger {
                background-color: #4C1D24;
                color: #FCA5A5;
                border: 1px solid #7F1D1D;
            }
            QPushButton#danger:hover {
                background-color: #7F1D1D;
                color: #ffffff;
            }
        """)

        lbl_find = QLabel("Tìm:")
        lbl_find.setStyleSheet("color: #9ca3af; font-size: 12px; border: none; background: transparent;")
        layout.addWidget(lbl_find)

        self._txt_find = QLineEdit()
        self._txt_find.setPlaceholderText("Nhập từ/cụm từ cần tìm...")
        self._txt_find.setMinimumWidth(160)
        self._txt_find.textChanged.connect(self._on_find_text_changed)
        self._txt_find.returnPressed.connect(self._on_find_next)
        layout.addWidget(self._txt_find)

        lbl_replace = QLabel("Thay thế:")
        lbl_replace.setStyleSheet("color: #9ca3af; font-size: 12px; border: none; background: transparent;")
        layout.addWidget(lbl_replace)

        self._txt_replace = QLineEdit()
        self._txt_replace.setPlaceholderText("Thay thế bằng...")
        self._txt_replace.setMinimumWidth(160)
        self._txt_replace.returnPressed.connect(self._on_replace)
        layout.addWidget(self._txt_replace)

        self._btn_next = QPushButton("Tìm tiếp")
        self._btn_next.setToolTip("Tìm vị trí tiếp theo (Enter)")
        self._btn_next.clicked.connect(self._on_find_next)
        layout.addWidget(self._btn_next)

        self._btn_replace = QPushButton("Thay thế")
        self._btn_replace.setToolTip("Thay thế từ khóa ở dòng đang chọn")
        self._btn_replace.clicked.connect(self._on_replace)
        layout.addWidget(self._btn_replace)

        self._btn_replace_all = QPushButton("Thay thế tất cả")
        self._btn_replace_all.setObjectName("primary")
        self._btn_replace_all.setToolTip("Thay thế toàn bộ trong tất cả các câu phụ đề")
        self._btn_replace_all.clicked.connect(self._on_replace_all)
        layout.addWidget(self._btn_replace_all)

        self._btn_delete_all = QPushButton(" Xóa hàng loạt")
        self._btn_delete_all.setIcon(get_icon("trash", "#ef4444", "#ef4444", 13))
        self._btn_delete_all.setObjectName("danger")
        self._btn_delete_all.setToolTip("Xóa bỏ nhanh toàn bộ từ khóa này khỏi mọi câu phụ đề")
        self._btn_delete_all.clicked.connect(self._on_delete_all)
        layout.addWidget(self._btn_delete_all)

        self._lbl_count = QLabel("")
        self._lbl_count.setStyleSheet("color: #38bdf8; font-size: 11px; border: none; background: transparent;")
        layout.addWidget(self._lbl_count)

        layout.addStretch(1)

        btn_close = QPushButton()
        btn_close.setIcon(get_icon("close", "#9ca3af", "#f0f2f5", 14))
        btn_close.setFixedSize(26, 26)
        btn_close.setToolTip("Đóng thanh tìm kiếm (Esc)")
        btn_close.clicked.connect(self.hide_bar)
        layout.addWidget(btn_close)

    def show_bar(self):
        self.setVisible(True)
        self._txt_find.setFocus()
        self._txt_find.selectAll()
        self._update_count()

    def hide_bar(self):
        self.setVisible(False)
        self.closed.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide_bar()
        else:
            super().keyPressEvent(event)

    def _update_count(self):
        query = self._txt_find.text().strip()
        if not query:
            self._lbl_count.setText("")
            return
        count = self._editor.count_occurrences(query)
        self._lbl_count.setText(f"({count} kết quả)" if count > 0 else "(0 kết quả)")

    def _on_find_text_changed(self):
        self._update_count()
        query = self._txt_find.text().strip()
        if query:
            self._editor.find_text(query, start_row=self._editor.currentRow())

    def _on_find_next(self):
        query = self._txt_find.text().strip()
        if not query:
            return
        cur_row = self._editor.currentRow()
        next_row = cur_row + 1 if cur_row >= 0 else 0
        found = self._editor.find_text(query, start_row=next_row)
        if found is None and next_row > 0:
            self._editor.find_text(query, start_row=0)
        self._update_count()

    def _on_replace(self):
        query = self._txt_find.text()
        if not query:
            return
        replacement = self._txt_replace.text()
        cur_row = self._editor.currentRow()
        if cur_row >= 0:
            self._editor.replace_at_row(cur_row, query, replacement)
            self._on_find_next()
        else:
            self._on_find_next()

    def _on_replace_all(self):
        query = self._txt_find.text()
        if not query:
            return
        replacement = self._txt_replace.text()
        count = self._editor.replace_all(query, replacement)
        self._update_count()
        QMessageBox.information(self, "Thay thế hoàn tất", f"Đã thay thế thành công {count} vị trí!")

    def _on_delete_all(self):
        query = self._txt_find.text()
        if not query:
            return
        reply = QMessageBox.question(
            self, "Xác nhận xóa hàng loạt",
            f"Bạn có chắc muốn xóa tất cả từ '{query}' khỏi toàn bộ các câu phụ đề?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            count = self._editor.delete_all(query)
            self._update_count()
            QMessageBox.information(self, "Xóa hoàn tất", f"Đã xóa từ khóa khỏi {count} vị trí!")


def _fmt_time(t: float) -> str:
    mins = int(t) // 60
    secs = t - mins * 60
    return f"{mins}:{secs:05.2f}"

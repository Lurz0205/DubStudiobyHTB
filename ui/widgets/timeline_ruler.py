"""Custom timeline widget: draggable subtitle/audio segments on a time ruler with zoom & horizontal scrollbar."""
from __future__ import annotations

import math
from typing import List, Optional

from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollBar,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ui.icons import get_icon


def _fmt_time(sec: float) -> str:
    m = int(sec) // 60
    s = sec - m * 60
    return f"{m:02d}:{s:04.1f}"


# Track layout constants
RULER_H = 28        # height of the time ruler at top
TRACK_H = 36        # height of each clip track
TRACK_PAD = 4       # vertical padding between tracks
LABEL_W = 72        # left label column width
MIN_ZOOM = 15       # px per second (min zoom)
MAX_ZOOM = 800      # px per second (max zoom)


class Segment:
    """Lightweight segment model for timeline display."""
    def __init__(self, idx: int, start: float, end: float, text: str,
                 voice: str = "", track: int = 0, slices: Optional[List[dict]] = None,
                 mute_sub: bool = False, mute_tts: bool = False):
        self.idx = idx
        self.start = start
        self.end = end
        self.text = text
        self.voice = voice
        self.track = track  # 0 = subtitle, 1 = tts audio
        self.slices = list(slices) if slices else []
        self.mute_sub = mute_sub
        self.mute_tts = mute_tts


class TimelineCanvas(QWidget):
    """Drawing area for ruler, tracks, audio/sub blocks, and playhead."""

    seek_requested = pyqtSignal(float)             # time in seconds
    segment_moved = pyqtSignal(int, float, float)    # idx, new_start, new_end (backwards compat)
    subtitle_moved = pyqtSignal(int, float, float)   # idx, new_start, new_end
    voice_moved = pyqtSignal(int, float)             # idx, new_voice_start
    segment_selected = pyqtSignal(int)             # idx
    orig_range_created = pyqtSignal(float, float)        # start, end
    orig_range_changed = pyqtSignal(int, float, float)  # id, new_start, new_end
    orig_range_deleted = pyqtSignal(int)                 # id
    segment_context_menu_requested = pyqtSignal(int, QPoint)  # seg_idx, globalPos
    view_scrolled = pyqtSignal()                   # emitted when offset or zoom changes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(RULER_H + 3 * (TRACK_H + TRACK_PAD) + 8)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMouseTracking(True)

        self._segments: List[Segment] = []
        self._orig_ranges: List[dict] = []
        self._zoom: float = 80.0       # px per second
        self._offset: float = 0.0     # scroll offset in seconds
        self._duration: float = 60.0  # total duration in seconds
        self._playhead: float = 0.0   # current playhead position

        # Drag state
        self._drag_seg: Optional[Segment] = None
        self._drag_range: Optional[dict] = None
        self._drag_mode: str = "move"  # "move", "resize_left", "resize_right"
        self._drag_start_x: int = 0
        self._drag_orig_start: float = 0.0
        self._drag_orig_end: float = 0.0
        self._pan_last_x: Optional[int] = None

        # Right-click drag creation for orig audio ranges on Track 2
        self._rb_start_pos: Optional[QPoint] = None
        self._rb_current_pos: Optional[QPoint] = None
        self._rb_creating_range: bool = False
        self._rb_dragged: bool = False

        self._selected_idx: int = -1
        self._hover_idx: int = -1

        # Colors
        self._c_bg = QColor("#0c0d10")
        self._c_ruler = QColor("#121418")
        self._c_ruler_text = QColor("#656d7d")
        self._c_tick = QColor("#242732")
        self._c_track_bg = QColor("#14151b")
        self._c_track_label = QColor("#1e212a")
        self._c_seg_sub = QColor("#0f2a40")
        self._c_seg_sub_border = QColor("#38bdf8")
        self._c_seg_tts = QColor("#0d3622")
        self._c_seg_tts_border = QColor("#10b981")
        self._c_seg_hover = QColor("#1a4468")
        self._c_seg_selected = QColor("#1b5687")
        self._c_seg_text = QColor("#f0f2f5")
        self._c_playhead = QColor("#ef4444")
        self._c_grid = QColor("#1b1d24")

    def visible_duration(self) -> float:
        w = max(10, self.width() - LABEL_W)
        return w / max(0.001, self._zoom)

    def set_zoom(self, zoom: float, anchor_x: Optional[float] = None):
        old_zoom = self._zoom
        new_zoom = max(MIN_ZOOM, min(MAX_ZOOM, zoom))
        if abs(new_zoom - old_zoom) < 0.1:
            return

        if anchor_x is None:
            anchor_x = float(LABEL_W + (self.width() - LABEL_W) / 2.0)

        # Keep timestamp under anchor fixed
        anchor_t = self._x_to_time(int(anchor_x))
        self._zoom = new_zoom
        new_x = self._time_to_x(anchor_t)
        self._offset = max(0.0, self._offset + (new_x - anchor_x) / self._zoom)
        self.update()
        self.view_scrolled.emit()

    def set_offset(self, offset: float):
        self._offset = max(0.0, offset)
        self.update()
        self.view_scrolled.emit()

    def _time_to_x(self, t: float) -> int:
        return LABEL_W + int((t - self._offset) * self._zoom)

    def _x_to_time(self, x: int) -> float:
        return self._offset + (x - LABEL_W) / self._zoom

    def _track_y(self, track: int) -> int:
        return RULER_H + track * (TRACK_H + TRACK_PAD)

    def _seg_rect(self, seg: Segment) -> QRect:
        x1 = self._time_to_x(seg.start)
        x2 = self._time_to_x(seg.end)
        y = self._track_y(seg.track)
        return QRect(x1, y + 2, max(x2 - x1, 4), TRACK_H - 4)

    def _seg_at(self, pos: QPoint) -> Optional[Segment]:
        for seg in reversed(self._segments):
            if self._seg_rect(seg).contains(pos):
                return seg
        return None

    def _orig_range_rect(self, r: dict) -> QRect:
        x1 = self._time_to_x(float(r.get("start", 0.0)))
        x2 = self._time_to_x(float(r.get("end", 0.0)))
        y = self._track_y(2)
        return QRect(x1, y + 2, max(x2 - x1, 6), TRACK_H - 4)

    def _orig_range_at(self, pos: QPoint) -> Optional[dict]:
        for r in reversed(self._orig_ranges):
            if self._orig_range_rect(r).contains(pos):
                return r
        return None

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, self._c_bg)

        # Track backgrounds (3 tracks: 0=Sub, 1=TTS, 2=Orig Audio)
        for track in range(3):
            y = self._track_y(track)
            p.fillRect(0, y, LABEL_W, TRACK_H, self._c_track_label)
            p.fillRect(LABEL_W, y, w - LABEL_W, TRACK_H, self._c_track_bg)

        self._draw_ruler(p, w)
        self._draw_grid(p, h)
        self._draw_track_labels(p)
        self._draw_segments(p)
        self._draw_playhead(p, h)
        p.end()

    def _draw_ruler(self, p: QPainter, w: int):
        p.fillRect(0, 0, w, RULER_H, self._c_ruler)

        tick_intervals = [0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30, 60]
        tick_s = 1.0
        for t in tick_intervals:
            if t * self._zoom >= 60:
                tick_s = t
                break

        visible_end = self._offset + (w - LABEL_W) / self._zoom
        t = math.floor(self._offset / tick_s) * tick_s
        font = QFont("Segoe UI", 9)
        p.setFont(font)
        p.setPen(QColor("#555555"))

        while t <= visible_end + tick_s:
            x = self._time_to_x(t)
            if x >= LABEL_W:
                is_major = round(t / tick_s) % 5 == 0 if tick_s < 10 else True
                tick_h = 14 if is_major else 7
                p.drawLine(x, RULER_H - tick_h, x, RULER_H)
                if is_major:
                    mins = int(t) // 60
                    secs = t - mins * 60
                    label = f"{mins}:{secs:04.1f}" if mins > 0 else f"{secs:.1f}s"
                    p.setPen(self._c_ruler_text)
                    p.drawText(x + 3, RULER_H - 14, 60, 14, Qt.AlignmentFlag.AlignLeft, label)
                    p.setPen(QColor("#555555"))
            t = round(t + tick_s, 6)

    def _draw_grid(self, p: QPainter, h: int):
        visible_end = self._offset + (self.width() - LABEL_W) / self._zoom
        tick_s = 1.0
        tick_intervals = [0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60]
        for t in tick_intervals:
            if t * self._zoom >= 60:
                tick_s = t
                break

        pen = QPen(self._c_grid)
        pen.setStyle(Qt.PenStyle.DotLine)
        p.setPen(pen)

        t = math.floor(self._offset / tick_s) * tick_s
        while t <= visible_end + tick_s:
            x = self._time_to_x(t)
            if x >= LABEL_W and round(t / tick_s) % 5 == 0:
                p.drawLine(x, RULER_H, x, h)
            t = round(t + tick_s, 6)

    def _draw_track_labels(self, p: QPainter):
        labels = ["Phụ đề", "Lồng tiếng", "Âm gốc 🎵"]
        font = QFont("Segoe UI", 9, QFont.Weight.DemiBold)
        p.setFont(font)
        for i, label in enumerate(labels):
            y = self._track_y(i)
            p.setPen(QColor("#f59e0b" if i == 2 else "#94a3b8"))
            p.drawText(0, y, LABEL_W - 6, TRACK_H,
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, label)

    def _draw_segments(self, p: QPainter):
        font = QFont("Segoe UI", 9)
        fm = QFontMetrics(font)
        p.setFont(font)

        has_tts_clips = any(s.track == 1 for s in self._segments)
        if not has_tts_clips and any(s.track == 0 for s in self._segments):
            y1 = self._track_y(1)
            p.setPen(QColor("#64748b"))
            font_hint = QFont("Segoe UI", 9)
            font_hint.setItalic(True)
            p.setFont(font_hint)
            p.drawText(LABEL_W + 16, y1, self.width() - LABEL_W - 32, TRACK_H,
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       "(Nhấn 'Tạo giọng lồng tiếng' để hiển thị các đoạn âm thanh giọng đọc thực tế trên timeline này)")
            p.setFont(font)

        for seg in self._segments:
            rect = self._seg_rect(seg)
            if rect.right() < LABEL_W or rect.left() > self.width():
                continue

            clip_rect = QRect(max(rect.left(), LABEL_W), rect.top(),
                              min(rect.right(), self.width()) - max(rect.left(), LABEL_W),
                              rect.height())
            if clip_rect.width() <= 0:
                continue

            is_sel = seg.idx == self._selected_idx and seg.track == 0
            is_hover = seg.idx == self._hover_idx

            if seg.track == 0:
                if seg.mute_sub:
                    base = QColor("#1e293b")
                    border = QColor("#475569")
                else:
                    base = self._c_seg_selected if is_sel else (self._c_seg_hover if is_hover else self._c_seg_sub)
                    border = self._c_seg_sub_border
            else:
                if seg.mute_tts:
                    base = QColor("#1c1917")
                    border = QColor("#57534e")
                else:
                    base = self._c_seg_selected if is_sel else (self._c_seg_hover if is_hover else self._c_seg_tts)
                    border = self._c_seg_tts_border

            p.setBrush(QBrush(base))
            p.setPen(QPen(border, 1))
            p.drawRoundedRect(clip_rect, 3, 3)

            # If subtitle track has multiple slices, draw dashed dividers & text for each slice
            if seg.track == 0 and getattr(seg, "slices", None) and len(seg.slices) > 1:
                for s_idx, sl in enumerate(seg.slices):
                    sl_x1 = max(clip_rect.left(), self._time_to_x(sl["start"]))
                    sl_x2 = min(clip_rect.right(), self._time_to_x(sl["end"]))
                    sl_w = max(0, sl_x2 - sl_x1)
                    if sl_w <= 0:
                        continue
                    sl_rect = QRect(sl_x1, clip_rect.top(), sl_w, clip_rect.height())

                    # Draw dashed vertical divider between slices
                    if s_idx > 0 and sl_x1 > clip_rect.left() and sl_x1 < clip_rect.right():
                        pen_div = QPen(QColor("#38bdf8"), 1.5, Qt.PenStyle.DashLine)
                        p.setPen(pen_div)
                        p.drawLine(sl_x1, clip_rect.top() + 2, sl_x1, clip_rect.bottom() - 2)

                    # Draw slice text
                    if sl_w > 16:
                        p.setPen(QColor("#64748b") if seg.mute_sub else self._c_seg_text)
                        raw_sl = sl.get("text", "").strip()
                        if seg.mute_sub:
                            raw_sl = f"[TẮT] {raw_sl}"
                        sl_text = fm.elidedText(raw_sl, Qt.TextElideMode.ElideRight, sl_w - 6)
                        p.drawText(sl_rect.adjusted(5, 0, -5, 0),
                                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, sl_text)
            else:
                if clip_rect.width() > 20:
                    p.setPen(QColor("#64748b") if (seg.mute_sub or seg.mute_tts) else self._c_seg_text)
                    raw_txt = seg.text.replace("\n", " ").strip()
                    if seg.track == 0 and seg.mute_sub:
                        raw_txt = f"[TẮT] {raw_txt}"
                    elif seg.track == 1 and seg.mute_tts:
                        raw_txt = f"[TẮT TTS] {raw_txt}"
                    text = fm.elidedText(raw_txt, Qt.TextElideMode.ElideRight, clip_rect.width() - 8)
                    p.drawText(clip_rect.adjusted(6, 0, -6, 0),
                               Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)

            # Edge grip handles for subtitle track
            if seg.track == 0 and clip_rect.width() >= 18:
                p.setPen(QPen(border.lighter(140), 1))
                p.drawLine(clip_rect.left() + 3, clip_rect.top() + 5, clip_rect.left() + 3, clip_rect.bottom() - 5)
                p.drawLine(clip_rect.right() - 3, clip_rect.top() + 5, clip_rect.right() - 3, clip_rect.bottom() - 5)

        # ─── Track 2: Original Audio Ranges (Khoanh vùng giữ âm thanh gốc) ───
        y2 = self._track_y(2)
        if not self._orig_ranges:
            p.setPen(QColor("#78350f"))
            font_hint = QFont("Segoe UI", 9)
            font_hint.setItalic(True)
            p.setFont(font_hint)
            p.drawText(LABEL_W + 16, y2, self.width() - LABEL_W - 32, TRACK_H,
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       "(Kéo giữ chuột phải trên thanh này để tạo nhanh vùng giữ âm gốc | Hoặc nhấn '+ Vùng âm gốc')")
            p.setFont(font)
        else:
            c_orig_bg = QColor("#451a03")
            c_orig_border = QColor("#f59e0b")
            c_orig_text = QColor("#fef3c7")
            for r in self._orig_ranges:
                rect = self._orig_range_rect(r)
                if rect.right() < LABEL_W or rect.left() > self.width():
                    continue
                clip_rect = QRect(max(rect.left(), LABEL_W), rect.top(),
                                  min(rect.right(), self.width()) - max(rect.left(), LABEL_W),
                                  rect.height())
                if clip_rect.width() <= 0:
                    continue

                p.setBrush(QBrush(c_orig_bg))
                p.setPen(QPen(c_orig_border, 1.5))
                p.drawRoundedRect(clip_rect, 4, 4)

                if clip_rect.width() > 24:
                    p.setPen(c_orig_text)
                    st = float(r.get("start", 0.0))
                    en = float(r.get("end", 0.0))
                    label_str = f"🎵 Âm gốc ({st:.1f}s → {en:.1f}s)"
                    elided = fm.elidedText(label_str, Qt.TextElideMode.ElideRight, clip_rect.width() - 10)
                    p.drawText(clip_rect.adjusted(6, 0, -6, 0),
                               Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)

                if clip_rect.width() >= 18:
                    p.setPen(QPen(c_orig_border.lighter(130), 1))
                    p.drawLine(clip_rect.left() + 3, clip_rect.top() + 5, clip_rect.left() + 3, clip_rect.bottom() - 5)
                    p.drawLine(clip_rect.right() - 3, clip_rect.top() + 5, clip_rect.right() - 3, clip_rect.bottom() - 5)

        # Preview hộp khoanh vùng khi kéo giữ chuột phải
        if self._rb_creating_range and self._rb_dragged and self._rb_start_pos and self._rb_current_pos:
            x_min = max(LABEL_W, min(self._rb_start_pos.x(), self._rb_current_pos.x()))
            x_max = max(LABEL_W, max(self._rb_start_pos.x(), self._rb_current_pos.x()))
            w_box = max(6, x_max - x_min)
            sel_rect = QRect(x_min, y2 + 2, w_box, TRACK_H - 4)

            p.fillRect(sel_rect, QColor(245, 158, 11, 85))
            p.setPen(QPen(QColor("#f59e0b"), 2, Qt.PenStyle.DashLine))
            p.drawRoundedRect(sel_rect, 4, 4)

            t1 = max(0.0, self._x_to_time(x_min))
            t2 = max(0.0, self._x_to_time(x_max))
            dur = max(0.0, t2 - t1)
            badge_text = f"+ Vùng âm gốc: {dur:.1f}s ({_fmt_time(t1)} → {_fmt_time(t2)})"
            p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            p.setPen(QColor("#ffffff"))
            p.drawText(sel_rect.adjusted(6, 0, -6, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, badge_text)
            p.setFont(font)

    def _draw_playhead(self, p: QPainter, h: int):
        x = self._time_to_x(self._playhead)
        if x < LABEL_W or x > self.width():
            return
        pen = QPen(self._c_playhead, 2)
        p.setPen(pen)
        p.drawLine(x, 0, x, h)

        p.setBrush(QBrush(self._c_playhead))
        p.setPen(Qt.PenStyle.NoPen)
        from PyQt6.QtGui import QPolygon
        tri = QPolygon([QPoint(x - 6, 0), QPoint(x + 6, 0), QPoint(x, 10)])
        p.drawPolygon(tri)

    def mousePressEvent(self, event):
        pos = event.pos()
        y2 = self._track_y(2)
        is_on_track2 = (y2 - 2 <= pos.y() <= y2 + TRACK_H + 4) and (pos.x() >= LABEL_W)

        # Right click handling
        if event.button() == Qt.MouseButton.RightButton:
            self._rb_start_pos = pos
            self._rb_current_pos = pos
            self._rb_dragged = False
            self._rb_creating_range = False

            # Chuột phải trên thanh Track 2: Kích hoạt chế độ kéo thả tạo nhanh vùng giữ âm gốc
            if is_on_track2:
                self._rb_creating_range = True
                return

            # Chuột phải trên khoảng trống ngoài Track 2: Kéo cuộn timeline
            if not self._seg_at(pos) and not self._orig_range_at(pos):
                self._pan_last_x = pos.x()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                return

        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_last_x = pos.x()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if pos.y() < RULER_H:
                t = max(0.0, self._x_to_time(pos.x()))
                self._playhead = t
                self.seek_requested.emit(t)
                self.update()
                return

            # Check Track 2 range click
            r_item = self._orig_range_at(pos)
            if r_item:
                self._drag_range = r_item
                self._drag_start_x = pos.x()
                self._drag_orig_start = float(r_item.get("start", 0.0))
                self._drag_orig_end = float(r_item.get("end", 0.0))
                rect = self._orig_range_rect(r_item)
                edge_margin = min(10, max(4, rect.width() // 4))
                if abs(pos.x() - rect.left()) <= edge_margin:
                    self._drag_mode = "resize_left"
                elif abs(pos.x() - rect.right()) <= edge_margin:
                    self._drag_mode = "resize_right"
                else:
                    self._drag_mode = "move"
                self.update()
                return

            seg = self._seg_at(pos)
            if seg:
                self._drag_seg = seg
                self._drag_start_x = pos.x()
                self._drag_orig_start = seg.start
                self._drag_orig_end = seg.end

                if seg.track == 0:
                    r = self._seg_rect(seg)
                    edge_margin = min(10, max(4, r.width() // 4))
                    if abs(pos.x() - r.left()) <= edge_margin:
                        self._drag_mode = "resize_left"
                    elif abs(pos.x() - r.right()) <= edge_margin:
                        self._drag_mode = "resize_right"
                    else:
                        self._drag_mode = "move"
                else:
                    self._drag_mode = "move"

                if seg.track == 0:
                    self._selected_idx = seg.idx
                    self.segment_selected.emit(seg.idx)
                self.update()
            else:
                if pos.x() >= LABEL_W:
                    t = max(0.0, self._x_to_time(pos.x()))
                    self._playhead = t
                    self.seek_requested.emit(t)
                    self.update()

    def mouseMoveEvent(self, event):
        pos = event.pos()
        y2 = self._track_y(2)
        is_on_track2 = (y2 - 2 <= pos.y() <= y2 + TRACK_H + 4) and (pos.x() >= LABEL_W)

        # Kéo giữ chuột phải trên Track 2 để tạo vùng giữ âm gốc
        if (event.buttons() & Qt.MouseButton.RightButton) and self._rb_creating_range and self._rb_start_pos:
            dx = abs(pos.x() - self._rb_start_pos.x())
            if dx > 5:
                self._rb_dragged = True
            self._rb_current_pos = pos
            self.setCursor(Qt.CursorShape.CrossCursor)
            self.update()
            return

        # Pan with middle/right button
        if self._pan_last_x is not None:
            dx = self._pan_last_x - pos.x()
            self._offset = max(0.0, self._offset + dx / self._zoom)
            self._pan_last_x = pos.x()
            self.update()
            self.view_scrolled.emit()
            return

        # Drag orig range
        if self._drag_range is not None and event.buttons() & Qt.MouseButton.LeftButton:
            dx = pos.x() - self._drag_start_x
            dt = dx / self._zoom
            if self._drag_mode == "resize_left":
                new_start = round(min(self._drag_orig_end - 0.2, max(0.0, self._drag_orig_start + dt)), 2)
                new_end = self._drag_orig_end
            elif self._drag_mode == "resize_right":
                new_start = self._drag_orig_start
                new_end = round(max(self._drag_orig_start + 0.2, self._drag_orig_end + dt), 2)
            else:
                dur = self._drag_orig_end - self._drag_orig_start
                new_start = round(max(0.0, self._drag_orig_start + dt), 2)
                new_end = round(new_start + dur, 2)
            self._drag_range["start"] = new_start
            self._drag_range["end"] = new_end
            self.update()
            return

        # Drag segment
        if self._drag_seg is not None and event.buttons() & Qt.MouseButton.LeftButton:
            dx = pos.x() - self._drag_start_x
            dt = dx / self._zoom

            if self._drag_mode == "resize_left":
                new_start = round(min(self._drag_orig_end - 0.15, max(0.0, self._drag_orig_start + dt)), 3)
                new_end = self._drag_orig_end
            elif self._drag_mode == "resize_right":
                new_start = self._drag_orig_start
                new_end = round(max(self._drag_orig_start + 0.15, self._drag_orig_end + dt), 3)
            else:
                new_start = round(max(0.0, self._drag_orig_start + dt), 3)
                dur = self._drag_orig_end - self._drag_orig_start
                new_end = round(new_start + dur, 3)

            self._drag_seg.start = new_start
            self._drag_seg.end = new_end
            if self._drag_seg.track == 0 and getattr(self._drag_seg, "slices", None) and len(self._drag_seg.slices) > 1:
                self._drag_seg.slices = TimelineWidget._recompute_slices(self._drag_seg.slices, new_start, new_end)
            self.update()
            return

        r_hover = self._orig_range_at(pos)
        if r_hover:
            rect = self._orig_range_rect(r_hover)
            edge_margin = min(10, max(4, rect.width() // 4))
            if abs(pos.x() - rect.left()) <= edge_margin or abs(pos.x() - rect.right()) <= edge_margin:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                self.setToolTip("Kéo mép để co dãn khoảng giữ âm thanh gốc")
            else:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
                self.setToolTip("Kéo để di chuyển khoảng giữ âm thanh gốc | Chuột phải để xóa")
            return

        if is_on_track2:
            self.setCursor(Qt.CursorShape.CrossCursor)
            self.setToolTip("Kéo giữ chuột phải để tạo nhanh vùng giữ âm gốc | Hoặc nhấn '+ Vùng âm gốc'")
            return

        seg = self._seg_at(pos)
        new_hover = seg.idx if seg else -1
        if new_hover != self._hover_idx:
            self._hover_idx = new_hover
            self.update()

        if seg:
            if seg.track == 0:
                r = self._seg_rect(seg)
                edge_margin = min(10, max(4, r.width() // 4))
                if abs(pos.x() - r.left()) <= edge_margin or abs(pos.x() - r.right()) <= edge_margin:
                    self.setCursor(Qt.CursorShape.SizeHorCursor)
                    self.setToolTip("Kéo mép trái/phải để co dãn thời lượng phụ đề")
                else:
                    self.setCursor(Qt.CursorShape.OpenHandCursor)
                    self.setToolTip("Kéo để di chuyển câu phụ đề (Chuột phải để Bật/Tắt)")
            else:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
                self.setToolTip("Kéo để điều chỉnh vị trí giọng đọc (Chuột phải để Bật/Tắt)")
        elif pos.y() < RULER_H and pos.x() >= LABEL_W:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip("Nhấn để nhảy tới thời điểm này")
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.setToolTip("")

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            was_dragged = self._rb_dragged
            if self._rb_creating_range and self._rb_dragged and self._rb_start_pos and self._rb_current_pos:
                t1 = max(0.0, self._x_to_time(self._rb_start_pos.x()))
                t2 = max(0.0, self._x_to_time(self._rb_current_pos.x()))
                st = round(min(t1, t2), 2)
                en = round(max(t1, t2), 2)
                if en - st >= 0.15:
                    self.orig_range_created.emit(st, en)
            self._rb_creating_range = False
            self._rb_start_pos = None
            self._rb_current_pos = None
            self._pan_last_x = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.update()
            if was_dragged:
                return

        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_last_x = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return

        if event.button() == Qt.MouseButton.LeftButton and self._drag_range:
            r = self._drag_range
            if abs(float(r["start"]) - self._drag_orig_start) > 0.05 or abs(float(r["end"]) - self._drag_orig_end) > 0.05:
                self.orig_range_changed.emit(r["id"], float(r["start"]), float(r["end"]))
            self._drag_range = None
            self._drag_mode = "move"

        if event.button() == Qt.MouseButton.LeftButton and self._drag_seg:
            seg = self._drag_seg
            if abs(seg.start - self._drag_orig_start) > 0.01 or abs(seg.end - self._drag_orig_end) > 0.01:
                if seg.track == 0:
                    self.subtitle_moved.emit(seg.idx, seg.start, seg.end)
                    self.segment_moved.emit(seg.idx, seg.start, seg.end)
                else:
                    self.voice_moved.emit(seg.idx, seg.start)
            self._drag_seg = None
            self._drag_mode = "move"

    def contextMenuEvent(self, event):
        if self._rb_dragged:
            self._rb_dragged = False
            event.accept()
            return

        pos = event.pos()
        # 1. Track 2 range click
        range_item = self._orig_range_at(pos)
        if range_item:
            menu = QMenu(self)
            rid = range_item.get("id")
            st = float(range_item.get("start", 0.0))
            en = float(range_item.get("end", 0.0))
            act_del = menu.addAction(f"Xóa vùng giữ âm gốc này ({_fmt_time(st)} → {_fmt_time(en)})")
            act_del.setIcon(get_icon("trash", "#ef4444", "#ef4444", 14))
            act_del.triggered.connect(lambda: self.orig_range_deleted.emit(rid))
            menu.exec(event.globalPos())
            return

        # 2. Track 0 or 1 segment click
        seg = self._seg_at(pos)
        if seg:
            self._selected_idx = seg.idx
            self.segment_selected.emit(seg.idx)
            self.segment_context_menu_requested.emit(seg.idx, event.globalPos())
            return

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Zoom anchored at mouse position
            factor = 1.18 if delta > 0 else 0.85
            self.set_zoom(self._zoom * factor, anchor_x=event.position().x())
        else:
            # Horizontal scroll across timeline
            self._offset = max(0.0, self._offset - (delta / self._zoom) * 1.5)
            self.update()
            self.view_scrolled.emit()


class TimelineWidget(QWidget):
    """
    Complete Professional Timeline Component with:
    - Dedicated Zoom toolbar (+, -, Slider, Fit All, Go to Start)
    - Full-featured canvas with Subtitle & Audio tracks
    - Responsive native Horizontal ScrollBar for 100% effortless scrolling
    """

    seek_requested = pyqtSignal(float)
    segment_moved = pyqtSignal(int, float, float)
    subtitle_moved = pyqtSignal(int, float, float)
    voice_moved = pyqtSignal(int, float)
    segment_selected = pyqtSignal(int)
    orig_range_created = pyqtSignal(float, float)
    orig_range_changed = pyqtSignal(int, float, float)
    orig_range_deleted = pyqtSignal(int)
    add_orig_range_requested = pyqtSignal()
    segment_context_menu_requested = pyqtSignal(int, QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # ─── 1. Top Control Bar (Zoom & Navigation) ───
        bar = QHBoxLayout()
        bar.setContentsMargins(4, 2, 4, 2)
        bar.setSpacing(8)

        lbl_title = QLabel("TIMELINE ÂM THANH & PHỤ ĐỀ")
        lbl_title.setStyleSheet("font-weight: bold; color: #38bdf8; font-size: 11px;")
        bar.addWidget(lbl_title)

        lbl_hint = QLabel("(Lăn chuột để cuộn | Ctrl+Lăn chuột hoặc dùng nút để phóng to)")
        lbl_hint.setStyleSheet("color: #64748b; font-size: 11px; font-style: italic;")
        bar.addWidget(lbl_hint)

        bar.addStretch(1)

        self._btn_goto_start = QPushButton(" Về đầu")
        self._btn_goto_start.setFixedHeight(22)
        self._btn_goto_start.setToolTip("Cuộn khung nhìn về giây 0:00")
        self._btn_goto_start.clicked.connect(self._on_goto_start)
        bar.addWidget(self._btn_goto_start)

        self._btn_fit_all = QPushButton(" Toàn cảnh")
        self._btn_fit_all.setFixedHeight(22)
        self._btn_fit_all.setToolTip("Thu nhỏ vừa khít toàn bộ thời lượng video")
        self._btn_fit_all.clicked.connect(self._on_fit_all)
        bar.addWidget(self._btn_fit_all)

        btn_zoom_out = QPushButton("-")
        btn_zoom_out.setFixedSize(22, 22)
        btn_zoom_out.setToolTip("Thu nhỏ timeline")
        btn_zoom_out.clicked.connect(lambda: self._adjust_zoom(0.80))
        bar.addWidget(btn_zoom_out)

        self._slider_zoom = QSlider(Qt.Orientation.Horizontal)
        self._slider_zoom.setRange(MIN_ZOOM, MAX_ZOOM)
        self._slider_zoom.setValue(80)
        self._slider_zoom.setFixedWidth(100)
        self._slider_zoom.valueChanged.connect(self._on_slider_zoom_changed)
        bar.addWidget(self._slider_zoom)

        btn_zoom_in = QPushButton("+")
        btn_zoom_in.setFixedSize(22, 22)
        btn_zoom_in.setToolTip("Phóng to timeline")
        btn_zoom_in.clicked.connect(lambda: self._adjust_zoom(1.25))
        bar.addWidget(btn_zoom_in)

        self._lbl_zoom_val = QLabel("80 px/s")
        self._lbl_zoom_val.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self._lbl_zoom_val.setFixedWidth(50)
        bar.addWidget(self._lbl_zoom_val)

        bar.addSpacing(12)

        self._btn_add_orig_range = QPushButton(" + Vùng âm gốc")
        self._btn_add_orig_range.setFixedHeight(22)
        self._btn_add_orig_range.setIcon(get_icon("music", "#f59e0b", "#f59e0b", 12))
        self._btn_add_orig_range.setToolTip("Khoanh vùng giữ 100% âm thanh gốc của video (tách biệt hoàn toàn với phụ đề)")
        self._btn_add_orig_range.setStyleSheet(
            "color: #f59e0b; font-weight: bold; border: 1px solid #78350f; background: #1c1917; border-radius: 4px; padding: 0 8px;"
        )
        self._btn_add_orig_range.clicked.connect(self.add_orig_range_requested.emit)
        bar.addWidget(self._btn_add_orig_range)

        layout.addLayout(bar)

        # ─── 2. Middle: Canvas Ruler & Tracks ───
        self._canvas = TimelineCanvas(self)
        self._canvas.seek_requested.connect(self.seek_requested.emit)
        self._canvas.segment_moved.connect(self.segment_moved.emit)
        self._canvas.subtitle_moved.connect(self.subtitle_moved.emit)
        self._canvas.voice_moved.connect(self.voice_moved.emit)
        self._canvas.segment_selected.connect(self.segment_selected.emit)
        self._canvas.orig_range_created.connect(self.orig_range_created.emit)
        self._canvas.orig_range_changed.connect(self.orig_range_changed.emit)
        self._canvas.orig_range_deleted.connect(self.orig_range_deleted.emit)
        self._canvas.segment_context_menu_requested.connect(self.segment_context_menu_requested.emit)
        self._canvas.view_scrolled.connect(self._sync_canvas_to_scrollbar)
        layout.addWidget(self._canvas)

        # ─── 3. Bottom: Native Horizontal ScrollBar ───
        self._scrollbar = QScrollBar(Qt.Orientation.Horizontal, self)
        self._scrollbar.setFixedHeight(12)
        self._scrollbar.valueChanged.connect(self._on_scrollbar_moved)
        layout.addWidget(self._scrollbar)

        self._update_scrollbar_range()

    # ─── Public API (Compatible Drop-in Replacement) ──────────────────────────

    @staticmethod
    def _recompute_slices(raw_slices: list, start: float, end: float) -> list:
        total_dur = max(0.2, end - start)
        word_counts = [max(1, len(sl.get("text", "").split())) for sl in raw_slices]
        total_w = sum(word_counts)
        res = []
        curr_t = start
        for idx, (sl, wc) in enumerate(zip(raw_slices, word_counts), start=1):
            if idx == len(raw_slices):
                seg_end = end
            else:
                dur = round(total_dur * (wc / total_w), 2)
                seg_end = round(curr_t + dur, 2)
                seg_end = max(curr_t + 0.1, min(end - 0.1 * (len(raw_slices) - idx), seg_end))
            res.append({"text": sl.get("text", "").strip(), "start": curr_t, "end": seg_end})
            curr_t = seg_end
        return res

    @staticmethod
    def _build_slices_from_lines(lines: list, start: float, end: float) -> list:
        raw = [{"text": l} for l in lines]
        return TimelineWidget._recompute_slices(raw, start, end)

    def set_segments(self, segments: List[dict], duration: float = 0.0):
        self._canvas._segments = []
        max_end = 0.0
        for s in segments:
            raw_start = float(s.get("start", 0))
            raw_end = float(s.get("end", raw_start + 2))
            text = s.get("vi_text", s.get("zh_text", ""))
            voice = s.get("voice", "")
            idx = int(s.get("id", s.get("index", len(self._canvas._segments))))

            has_audio = bool(s.get("tts_dur") or s.get("tts_file"))
            if has_audio:
                tts_dur = float(s.get("tts_dur") or (raw_end - raw_start))
                fit_info = s.get("fit") or {}
                rate = float(fit_info.get("rate", 1.0) or 1.0)
                effective_dur = round(tts_dur / rate, 3) if fit_info.get("method") in ("speedup", "slowdown") and rate > 0 else tts_dur
                tts_start = float(s.get("voice_start") if s.get("voice_start") is not None else fit_info.get("offset_start", raw_start))
                tts_end = round(tts_start + effective_dur, 3)
                start = tts_start
                end = tts_end
            else:
                start = raw_start
                end = raw_end

            max_end = max(max_end, end)
            slices = []

            # 0. Custom explicit cues (from auto-split DP or manual edit)
            combined_cues_text = " ".join(c.get("text", "").strip() for c in s.get("cues", []) if isinstance(c, dict)) if s.get("cues") else ""
            combined_main_text = " ".join(text.split())
            if s.get("cues") and len(s["cues"]) > 1 and combined_cues_text == combined_main_text:
                slices = [
                    {"text": c.get("text", "").strip(), "start": float(c.get("start", start)), "end": float(c.get("end", end))}
                    for c in s["cues"] if c.get("text", "").strip()
                ]
            # 1. Custom explicit sub_slices
            elif s.get("sub_slices") and len(s["sub_slices"]) > 1:
                slices = self._recompute_slices(s["sub_slices"], start, end)
            # 2. Text containing newlines
            elif "\n" in text and len(text.splitlines()) > 1:
                lines = [l.strip() for l in text.splitlines() if l.strip()]
                slices = self._build_slices_from_lines(lines, start, end)
            # 3. Auto-slice long sentences (>15 words) IF TTS audio already exists
            elif has_audio and len(text.split()) > 15:
                from dubstudio.subtitles.ass import split_subtitle_slices
                slices = split_subtitle_slices(text, start, end, target_words=12, max_words=15)

            mute_sub = bool(s.get("mute_sub", False))
            mute_tts = bool(s.get("mute_tts", False))

            self._canvas._segments.append(
                Segment(idx, start, end, text, voice, track=0, slices=slices, mute_sub=mute_sub, mute_tts=mute_tts)
            )

            if has_audio:
                max_end = max(max_end, tts_end)
                clip_label = f"{voice} ({effective_dur:.1f}s)" if voice else f"{effective_dur:.1f}s"
                self._canvas._segments.append(
                    Segment(idx, tts_start, tts_end, clip_label, voice, track=1, mute_sub=mute_sub, mute_tts=mute_tts)
                )

        self._canvas._duration = max(duration, max_end, 10.0)
        self._update_scrollbar_range()
        self._canvas.update()

    def set_orig_ranges(self, ranges: List[dict]):
        """Update original audio passthrough ranges on Track 2."""
        self._canvas._orig_ranges = list(ranges)
        self._canvas.update()

    def set_playhead(self, t: float):
        self._canvas._playhead = t
        vis_start = self._canvas._offset
        vis_end = self._canvas._offset + self._canvas.visible_duration()
        if t < vis_start or t > vis_end - 2:
            self._canvas._offset = max(0.0, t - 2.0)
            self._sync_canvas_to_scrollbar()
        self._canvas.update()

    def set_duration(self, d: float):
        self._canvas._duration = max(d, 10.0)
        self._update_scrollbar_range()
        self._canvas.update()

    # ─── Controls Interaction ────────────────────────────────────────────────

    def _on_goto_start(self):
        self._canvas.set_offset(0.0)
        self._sync_canvas_to_scrollbar()

    def _on_fit_all(self):
        avail_w = max(100, self._canvas.width() - LABEL_W)
        dur = max(1.0, self._canvas._duration)
        fit_zoom = max(MIN_ZOOM, min(MAX_ZOOM, avail_w / dur))
        self._slider_zoom.blockSignals(True)
        self._slider_zoom.setValue(int(fit_zoom))
        self._slider_zoom.blockSignals(False)
        self._lbl_zoom_val.setText(f"{int(fit_zoom)} px/s")
        self._canvas._zoom = fit_zoom
        self._canvas._offset = 0.0
        self._update_scrollbar_range()
        self._canvas.update()

    def _adjust_zoom(self, factor: float):
        new_val = int(self._canvas._zoom * factor)
        new_val = max(MIN_ZOOM, min(MAX_ZOOM, new_val))
        self._slider_zoom.setValue(new_val)

    def _on_slider_zoom_changed(self, val: int):
        self._lbl_zoom_val.setText(f"{val} px/s")
        self._canvas.set_zoom(val)
        self._update_scrollbar_range()

    def _update_scrollbar_range(self):
        vis = self._canvas.visible_duration()
        total = self._canvas._duration
        max_scroll = max(0.0, total - vis)
        self._scrollbar.blockSignals(True)
        self._scrollbar.setRange(0, int(round(max_scroll * 100)))
        self._scrollbar.setPageStep(int(round(vis * 100)))
        self._scrollbar.setValue(int(round(self._canvas._offset * 100)))
        self._scrollbar.blockSignals(False)

    def _sync_canvas_to_scrollbar(self):
        self._update_scrollbar_range()
        self._slider_zoom.blockSignals(True)
        self._slider_zoom.setValue(int(self._canvas._zoom))
        self._slider_zoom.blockSignals(False)
        self._lbl_zoom_val.setText(f"{int(self._canvas._zoom)} px/s")

    def _on_scrollbar_moved(self, val: int):
        self._canvas._offset = val / 100.0
        self._canvas.update()

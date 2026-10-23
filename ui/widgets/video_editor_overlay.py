"""Interactive visual canvas overlay for Video Editor (Crop, Multi Color Boxes, and Logo manipulation)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import QWidget


class VideoEditorOverlay(QWidget):
    """
    Full-canvas interactive overlay widget sitting directly on top of the VideoPlayer viewport.
    Provides direct on-screen manipulation (drag to move, drag handles to resize) for:
      - 1. Crop Area (with dimmed outside mask & 8 resize handles)
      - 2. Color Boxes / Masks (multiple boxes supported, true color, opacity, rounded corners & resize handles)
      - 3. Logo / Watermark (with image render, corner handles & strict aspect-ratio lock)
    """

    crop_changed = pyqtSignal(int, int, int, int)   # x, y, w, h in native video pixels
    box_changed = pyqtSignal(int, int, int, int)    # x, y, w, h for the currently selected box
    boxes_updated = pyqtSignal(list)                # list of all boxes
    box_selected = pyqtSignal(int)                  # index of selected box
    img_changed = pyqtSignal(int, int, int, int)    # x, y, w, h in native video pixels
    element_selected = pyqtSignal(str)              # "crop", "box", "image"

    HANDLE_SIZE = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        # Video geometry
        self._video_w: int = 1280
        self._video_h: int = 720
        self._get_video_rect_func = None

        # 1. Crop state (in native pixels)
        self._crop_enabled: bool = False
        self._crop_x: int = 0
        self._crop_y: int = 0
        self._crop_w: int = 1280
        self._crop_h: int = 720

        # 2. Multi Color Boxes state (in native pixels)
        self._boxes: List[Dict[str, Any]] = []
        self._selected_box_idx: int = -1

        # 3. Logo state (in native pixels)
        self._img_enabled: bool = False
        self._img_x: int = 20
        self._img_y: int = 20
        self._img_w: int = 180
        self._img_h: int = 180
        self._img_pixmap: Optional[QPixmap] = None
        self._fix_scale: bool = True

        # Active interaction state
        self._active_target: str = "crop"  # "crop", "box", "image"
        self._drag_action: Optional[str] = None  # "move_<target>" or "resize_<target>_<handle>"
        self._drag_start_pos: Optional[QPoint] = None
        self._orig_rect: Optional[QRect] = None

    def set_video_dimensions(self, w: int, h: int, get_video_rect_func):
        self._video_w = max(10, w)
        self._video_h = max(10, h)
        self._get_video_rect_func = get_video_rect_func
        self.update()

    def set_crop_params(self, enabled: bool, x: int, y: int, w: int, h: int):
        self._crop_enabled = enabled
        self._crop_x = x
        self._crop_y = y
        self._crop_w = max(10, w)
        self._crop_h = max(10, h)
        self.update()

    # ─── Multi Color Boxes Management ────────────────────────────────────────

    def get_boxes(self) -> List[Dict[str, Any]]:
        return self._boxes

    def set_boxes(self, boxes: List[Dict[str, Any]], selected_idx: int = 0):
        self._boxes = list(boxes) if boxes else []
        self._selected_box_idx = max(0, min(len(self._boxes) - 1, selected_idx)) if self._boxes else -1
        self.update()

    def add_box(self, box: Optional[Dict[str, Any]] = None) -> int:
        if box is None:
            # Default new box slightly offset from previous
            prev = self.get_selected_box() or {}
            offset = 20 * (len(self._boxes) % 5)
            new_box = {
                "enabled": True,
                "x": min(max(0, prev.get("x", 0) + offset), max(0, self._video_w - 200)),
                "y": min(max(0, prev.get("y", max(0, self._video_h - 140)) + offset), max(0, self._video_h - 60)),
                "w": min(prev.get("w", self._video_w), self._video_w),
                "h": min(prev.get("h", 120), self._video_h),
                "color": prev.get("color", "#000000"),
                "opacity": prev.get("opacity", 0.80),
                "radius": prev.get("radius", 8),
                "rotation": prev.get("rotation", 0.0),
                "text": prev.get("text", ""),
                "font_name": prev.get("font_name", "Arial"),
                "font_size": prev.get("font_size", 24),
                "text_color": prev.get("text_color", "#FFFFFF"),
                "text_outline_color": prev.get("text_outline_color", "#000000"),
                "text_outline_width": prev.get("text_outline_width", 2),
            }
        else:
            new_box = box

        self._boxes.append(new_box)
        self._selected_box_idx = len(self._boxes) - 1
        self._active_target = "box"
        self.update()
        self.boxes_updated.emit(self._boxes)
        self.box_selected.emit(self._selected_box_idx)
        return self._selected_box_idx

    def delete_selected_box(self) -> int:
        if not self._boxes:
            return -1
        if 0 <= self._selected_box_idx < len(self._boxes):
            del self._boxes[self._selected_box_idx]

        if not self._boxes:
            self._selected_box_idx = -1
        else:
            self._selected_box_idx = min(self._selected_box_idx, len(self._boxes) - 1)

        self.update()
        self.boxes_updated.emit(self._boxes)
        self.box_selected.emit(self._selected_box_idx)
        return self._selected_box_idx

    def get_selected_box(self) -> Optional[Dict[str, Any]]:
        if 0 <= self._selected_box_idx < len(self._boxes):
            return self._boxes[self._selected_box_idx]
        return None

    def set_selected_box_idx(self, idx: int):
        if 0 <= idx < len(self._boxes):
            self._selected_box_idx = idx
            self.update()

    def set_box_params(
        self,
        enabled: bool,
        x: int,
        y: int,
        w: int,
        h: int,
        color: str,
        opacity: float,
        radius: int,
        rotation: float = 0.0,
        text: str = "",
        font_name: str = "Arial",
        font_size: int = 24,
        text_color: str = "#FFFFFF",
        text_outline_color: str = "#000000",
        text_outline_width: int = 2,
    ):
        """Update parameters of the currently selected box."""
        if not self._boxes or self._selected_box_idx < 0:
            return
        b = self._boxes[self._selected_box_idx]
        b["enabled"] = enabled
        b["x"] = x
        b["y"] = y
        b["w"] = max(10, w)
        b["h"] = max(10, h)
        b["color"] = color
        b["opacity"] = max(0.0, min(1.0, opacity))
        b["radius"] = max(0, radius)
        b["rotation"] = float(rotation)
        b["text"] = str(text)
        b["font_name"] = str(font_name)
        b["font_size"] = max(8, int(font_size))
        b["text_color"] = str(text_color)
        b["text_outline_color"] = str(text_outline_color)
        b["text_outline_width"] = max(0, int(text_outline_width))
        self.update()

    # ─── Logo Parameters ─────────────────────────────────────────────────────

    def set_img_params(self, enabled: bool, x: int, y: int, w: int, h: int, pixmap: Optional[QPixmap], fix_scale: bool):
        self._img_enabled = enabled
        self._img_x = x
        self._img_y = y
        self._img_w = max(10, w)
        self._img_h = max(10, h)
        self._img_pixmap = pixmap
        self._fix_scale = fix_scale
        self.update()

    def set_active_target(self, target: str):
        if target in ("crop", "box", "image"):
            self._active_target = target
            self.update()

    # ─── Coordinate Helpers ──────────────────────────────────────────────────

    def _get_active_rect(self) -> tuple[float, float, float, float, float]:
        if self._get_video_rect_func:
            return self._get_video_rect_func()
        w = float(self.width())
        h = float(self.height())
        scale = min(w / float(self._video_w), h / float(self._video_h))
        dw = self._video_w * scale
        dh = self._video_h * scale
        return (w - dw) / 2.0, (h - dh) / 2.0, dw, dh, scale

    def _native_to_screen(self, nx: int, ny: int, nw: int, nh: int) -> QRect:
        dx, dy, dw, dh, scale = self._get_active_rect()
        sx = int(round(dx + nx * scale))
        sy = int(round(dy + ny * scale))
        sw = max(4, int(round(nw * scale)))
        sh = max(4, int(round(nh * scale)))
        return QRect(sx, sy, sw, sh)

    def _screen_to_native(self, sx: int, sy: int, sw: int, sh: int) -> tuple[int, int, int, int]:
        dx, dy, dw, dh, scale = self._get_active_rect()
        if scale <= 0:
            scale = 0.001
        nx = int(round((sx - dx) / scale))
        ny = int(round((sy - dy) / scale))
        nw = max(10, int(round(sw / scale)))
        nh = max(10, int(round(sh / scale)))
        return nx, ny, nw, nh

    # ─── Drawing ─────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        dx, dy, dw, dh, scale = self._get_active_rect()
        vid_rect = QRect(int(dx), int(dy), int(dw), int(dh))

        # 1. Draw Crop Box & Dimmed Outer Mask
        if self._crop_enabled:
            crop_scr = self._native_to_screen(self._crop_x, self._crop_y, self._crop_w, self._crop_h)

            mask_color = QColor(0, 0, 0, 130)
            if crop_scr.top() > vid_rect.top():
                painter.fillRect(vid_rect.left(), vid_rect.top(), vid_rect.width(), crop_scr.top() - vid_rect.top(), mask_color)
            if crop_scr.bottom() < vid_rect.bottom():
                painter.fillRect(vid_rect.left(), crop_scr.bottom(), vid_rect.width(), vid_rect.bottom() - crop_scr.bottom(), mask_color)
            if crop_scr.left() > vid_rect.left():
                painter.fillRect(vid_rect.left(), crop_scr.top(), crop_scr.left() - vid_rect.left(), crop_scr.height(), mask_color)
            if crop_scr.right() < vid_rect.right():
                painter.fillRect(crop_scr.right(), crop_scr.top(), vid_rect.right() - crop_scr.right(), crop_scr.height(), mask_color)

            crop_pen = QPen(QColor("#38bdf8"), 2.0, Qt.PenStyle.SolidLine)
            painter.setPen(crop_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(crop_scr)
            self._draw_handles(painter, crop_scr, QColor("#38bdf8"))
            self._draw_badge(painter, crop_scr, f"Khung Cắt ({self._crop_w}x{self._crop_h})", QColor("#0284c7"))

        # 2. Draw Multi Color / Text Boxes (Khối che & khối chữ xoay được)
        for idx, box in enumerate(self._boxes):
            if not box.get("enabled", False):
                continue
            bx = box.get("x", 0)
            by = box.get("y", 0)
            bw = box.get("w", 100)
            bh = box.get("h", 50)
            box_scr = self._native_to_screen(bx, by, bw, bh)
            rot = float(box.get("rotation", 0.0) or 0.0)

            painter.save()
            center_pt = box_scr.center()
            if rot != 0.0:
                painter.translate(center_pt)
                painter.rotate(rot)
                painter.translate(-center_pt)

            c = QColor(box.get("color", "#000000"))
            if not c.isValid():
                c = QColor(0, 0, 0)
            c.setAlphaF(float(box.get("opacity", 0.8)))
            painter.setBrush(QBrush(c))
            painter.setPen(Qt.PenStyle.NoPen)
            rad_scr = max(0, int(round(box.get("radius", 8) * scale)))
            painter.drawRoundedRect(box_scr, rad_scr, rad_scr)

            # Draw text if present
            box_text = str(box.get("text", "") or "").strip()
            if box_text:
                f_name = box.get("font_name", "Arial")
                f_size = max(8, int(round(float(box.get("font_size", 24) or 24) * scale)))
                t_col = QColor(box.get("text_color", "#FFFFFF"))
                o_col = QColor(box.get("text_outline_color", "#000000"))
                o_w = max(0, int(round(float(box.get("text_outline_width", 2) or 2) * scale)))

                qfont = QFont(f_name)
                qfont.setPixelSize(f_size)
                qfont.setBold(True)
                painter.setFont(qfont)

                fm = QFontMetrics(qfont)
                flags = Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap
                pad = max(2, int(round(4 * scale)))
                inner_rect = box_scr.adjusted(pad, pad, -pad, -pad)
                text_rect = fm.boundingRect(inner_rect, flags, box_text)

                if o_w > 0:
                    path = QPainterPath()
                    path.addText(float(text_rect.left()), float(text_rect.top() + fm.ascent()), qfont, box_text)
                    pen_out = QPen(o_col, o_w * 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
                    painter.strokePath(path, pen_out)
                    painter.fillPath(path, QBrush(t_col))
                else:
                    painter.setPen(QPen(t_col))
                    painter.drawText(inner_rect, flags, box_text)

            is_selected = (idx == self._selected_box_idx)
            badge_title = f"Khối #{idx + 1}"
            if rot != 0:
                badge_title += f" ({int(rot)}°)"
            if box_text:
                short_t = box_text[:8] + ".." if len(box_text) > 8 else box_text
                badge_title += f": {short_t}"

            if is_selected:
                # Selected box: highlighted dashed border and resize handles
                pen_box = QPen(QColor("#f59e0b"), 2.0, Qt.PenStyle.DashLine)
                painter.setPen(pen_box)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(box_scr, rad_scr, rad_scr)
                self._draw_handles(painter, box_scr, QColor("#f59e0b"))
                self._draw_badge(painter, box_scr, badge_title, QColor("#d97706"))
            else:
                # Unselected box: subtle dashed border
                pen_box = QPen(QColor(245, 158, 11, 120), 1.0, Qt.PenStyle.DotLine)
                painter.setPen(pen_box)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(box_scr, rad_scr, rad_scr)
                self._draw_badge(painter, box_scr, badge_title, QColor(100, 100, 100, 180))

            painter.restore()

        # 3. Draw Image / Logo Overlay
        if self._img_enabled and self._img_pixmap and not self._img_pixmap.isNull():
            img_scr = self._native_to_screen(self._img_x, self._img_y, self._img_w, self._img_h)
            painter.drawPixmap(img_scr, self._img_pixmap)

            pen_img = QPen(QColor("#a855f7"), 1.8, Qt.PenStyle.DashLine)
            painter.setPen(pen_img)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(img_scr)
            self._draw_handles(painter, img_scr, QColor("#a855f7"))
            self._draw_badge(painter, img_scr, f"Logo ({self._img_w}x{self._img_h})", QColor("#7e22ce"))

    def _draw_handles(self, painter: QPainter, rect: QRect, color: QColor):
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor("#ffffff"), 1.0))
        hs = self.HANDLE_SIZE
        half = hs // 2

        points = [
            rect.topLeft(),
            QPoint(rect.center().x(), rect.top()),
            rect.topRight(),
            QPoint(rect.right(), rect.center().y()),
            rect.bottomRight(),
            QPoint(rect.center().x(), rect.bottom()),
            rect.bottomLeft(),
            QPoint(rect.left(), rect.center().y()),
        ]
        for pt in points:
            painter.drawRect(pt.x() - half, pt.y() - half, hs, hs)

    def _draw_badge(self, painter: QPainter, rect: QRect, text: str, bg_color: QColor):
        font = QFont("Segoe UI", 8)
        font.setBold(True)
        painter.setFont(font)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text) + 12
        th = fm.height() + 4

        bx = max(rect.left() + 4, min(rect.left() + 6, self.width() - tw - 4))
        by = max(rect.top() + 4, min(rect.top() + 6, self.height() - th - 4))

        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRect(bx, by, tw, th), 3, 3)

        painter.setPen(QPen(QColor("#ffffff")))
        painter.drawText(QRect(bx, by, tw, th), Qt.AlignmentFlag.AlignCenter, text)

    # ─── Mouse Interaction ───────────────────────────────────────────────────

    def _get_target_rect(self, target: str, box_idx: Optional[int] = None) -> Optional[QRect]:
        if target == "crop" and self._crop_enabled:
            return self._native_to_screen(self._crop_x, self._crop_y, self._crop_w, self._crop_h)
        if target == "box":
            idx = self._selected_box_idx if box_idx is None else box_idx
            if 0 <= idx < len(self._boxes):
                b = self._boxes[idx]
                if b.get("enabled", False):
                    return self._native_to_screen(b.get("x", 0), b.get("y", 0), b.get("w", 100), b.get("h", 50))
        if target == "image" and self._img_enabled:
            return self._native_to_screen(self._img_x, self._img_y, self._img_w, self._img_h)
        return None

    def _hit_test(self, pt: QPoint) -> tuple[Optional[str], Optional[str]]:
        """Determine target ('crop'|'box'|'image') and handle ('tl'|'t'|'tr'|'r'|'br'|'b'|'bl'|'l'|'body')."""
        hs = self.HANDLE_SIZE + 4
        half = hs // 2

        # 1. Test Image / Logo (topmost)
        img_rect = self._get_target_rect("image")
        if img_rect:
            handles = {
                "tl": img_rect.topLeft(),
                "t": QPoint(img_rect.center().x(), img_rect.top()),
                "tr": img_rect.topRight(),
                "r": QPoint(img_rect.right(), img_rect.center().y()),
                "br": img_rect.bottomRight(),
                "b": QPoint(img_rect.center().x(), img_rect.bottom()),
                "bl": img_rect.bottomLeft(),
                "l": QPoint(img_rect.left(), img_rect.center().y()),
            }
            for h_name, h_pt in handles.items():
                if abs(pt.x() - h_pt.x()) <= half and abs(pt.y() - h_pt.y()) <= half:
                    return "image", h_name
            if img_rect.contains(pt):
                return "image", "body"

        # 2. Test Color / Text Boxes (selected box handles first, then other boxes)
        # Check selected box handles
        sel_rect = self._get_target_rect("box", self._selected_box_idx)
        if sel_rect:
            b_sel = self._boxes[self._selected_box_idx]
            rot = float(b_sel.get("rotation", 0.0) or 0.0)
            test_pt = pt
            if rot != 0.0:
                cx = float(sel_rect.center().x())
                cy = float(sel_rect.center().y())
                from PyQt6.QtGui import QTransform
                t = QTransform().translate(cx, cy).rotate(-rot).translate(-cx, -cy)
                test_pt = t.map(pt)

            handles = {
                "tl": sel_rect.topLeft(),
                "t": QPoint(sel_rect.center().x(), sel_rect.top()),
                "tr": sel_rect.topRight(),
                "r": QPoint(sel_rect.right(), sel_rect.center().y()),
                "br": sel_rect.bottomRight(),
                "b": QPoint(sel_rect.center().x(), sel_rect.bottom()),
                "bl": sel_rect.bottomLeft(),
                "l": QPoint(sel_rect.left(), sel_rect.center().y()),
            }
            for h_name, h_pt in handles.items():
                if abs(test_pt.x() - h_pt.x()) <= half and abs(test_pt.y() - h_pt.y()) <= half:
                    return "box", h_name

        # Check all boxes body (reverse order so topmost box is clicked first)
        for idx in reversed(range(len(self._boxes))):
            box_r = self._get_target_rect("box", idx)
            if box_r:
                b_item = self._boxes[idx]
                rot = float(b_item.get("rotation", 0.0) or 0.0)
                test_pt = pt
                if rot != 0.0:
                    cx = float(box_r.center().x())
                    cy = float(box_r.center().y())
                    from PyQt6.QtGui import QTransform
                    t = QTransform().translate(cx, cy).rotate(-rot).translate(-cx, -cy)
                    test_pt = t.map(pt)
                if box_r.contains(test_pt):
                    if idx != self._selected_box_idx:
                        self._selected_box_idx = idx
                        self.box_selected.emit(idx)
                        self.update()
                    return "box", "body"

        # 3. Test Crop Area
        crop_rect = self._get_target_rect("crop")
        if crop_rect:
            handles = {
                "tl": crop_rect.topLeft(),
                "t": QPoint(crop_rect.center().x(), crop_rect.top()),
                "tr": crop_rect.topRight(),
                "r": QPoint(crop_rect.right(), crop_rect.center().y()),
                "br": crop_rect.bottomRight(),
                "b": QPoint(crop_rect.center().x(), crop_rect.bottom()),
                "bl": crop_rect.bottomLeft(),
                "l": QPoint(crop_rect.left(), crop_rect.center().y()),
            }
            for h_name, h_pt in handles.items():
                if abs(pt.x() - h_pt.x()) <= half and abs(pt.y() - h_pt.y()) <= half:
                    return "crop", h_name
            if crop_rect.contains(pt):
                return "crop", "body"

        return None, None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            t, h = self._hit_test(event.pos())
            if t and h:
                self._active_target = t
                self.element_selected.emit(t)
                self._drag_start_pos = event.pos()
                r = self._get_target_rect(t)
                self._orig_rect = QRect(r) if r else None

                if h == "body":
                    self._drag_action = f"move_{t}"
                    self.setCursor(Qt.CursorShape.SizeAllCursor)
                else:
                    self._drag_action = f"resize_{t}_{h}"
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_action and self._drag_start_pos and self._orig_rect:
            dx = event.pos().x() - self._drag_start_pos.x()
            dy = event.pos().y() - self._drag_start_pos.y()
            r = QRect(self._orig_rect)

            target = self._active_target
            action = self._drag_action

            if action.startswith("move_"):
                r.translate(dx, dy)
            elif action.startswith("resize_"):
                h_name = action.split("_")[-1]

                # STRICT ASPECT-RATIO LOCK FOR LOGO/IMAGE
                if target == "image" and self._fix_scale:
                    if self._img_pixmap and not self._img_pixmap.isNull() and self._img_pixmap.height() > 0:
                        aspect = float(self._img_pixmap.width()) / float(self._img_pixmap.height())
                    else:
                        aspect = max(0.01, float(self._orig_rect.width()) / max(1.0, float(self._orig_rect.height())))

                    ow = self._orig_rect.width()
                    oh = self._orig_rect.height()

                    if h_name == "br":
                        new_w = max(16, ow + dx)
                        new_h = max(16, int(round(new_w / aspect)))
                        r = QRect(self._orig_rect.left(), self._orig_rect.top(), new_w, new_h)
                    elif h_name == "tl":
                        new_w = max(16, ow - dx)
                        new_h = max(16, int(round(new_w / aspect)))
                        r = QRect(self._orig_rect.right() - new_w, self._orig_rect.bottom() - new_h, new_w, new_h)
                    elif h_name == "tr":
                        new_w = max(16, ow + dx)
                        new_h = max(16, int(round(new_w / aspect)))
                        r = QRect(self._orig_rect.left(), self._orig_rect.bottom() - new_h, new_w, new_h)
                    elif h_name == "bl":
                        new_w = max(16, ow - dx)
                        new_h = max(16, int(round(new_w / aspect)))
                        r = QRect(self._orig_rect.right() - new_w, self._orig_rect.top(), new_w, new_h)
                    elif h_name in ("r", "l"):
                        delta_w = dx if h_name == "r" else -dx
                        new_w = max(16, ow + delta_w)
                        new_h = max(16, int(round(new_w / aspect)))
                        center_y = self._orig_rect.center().y()
                        new_top = center_y - new_h // 2
                        new_left = self._orig_rect.left() if h_name == "r" else self._orig_rect.right() - new_w
                        r = QRect(new_left, new_top, new_w, new_h)
                    elif h_name in ("t", "b"):
                        delta_h = dy if h_name == "b" else -dy
                        new_h = max(16, oh + delta_h)
                        new_w = max(16, int(round(new_h * aspect)))
                        center_x = self._orig_rect.center().x()
                        new_left = center_x - new_w // 2
                        new_top = self._orig_rect.top() if h_name == "b" else self._orig_rect.bottom() - new_h
                        r = QRect(new_left, new_top, new_w, new_h)
                else:
                    # Freeform resize for crop or color box
                    if "l" in h_name:
                        r.setLeft(min(r.right() - 20, r.left() + dx))
                    if "r" in h_name:
                        r.setRight(max(r.left() + 20, r.right() + dx))
                    if "t" in h_name:
                        r.setTop(min(r.bottom() - 20, r.top() + dy))
                    if "b" in h_name:
                        r.setBottom(max(r.top() + 20, r.bottom() + dy))

            # Convert screen rect to native video coordinates
            nx, ny, nw, nh = self._screen_to_native(r.left(), r.top(), r.width(), r.height())
            nx = max(0, min(self._video_w - nw, nx))
            ny = max(0, min(self._video_h - nh, ny))
            nw = min(self._video_w - nx, nw)
            nh = min(self._video_h - ny, nh)

            if target == "crop":
                self._crop_x, self._crop_y, self._crop_w, self._crop_h = nx, ny, nw, nh
                self.crop_changed.emit(nx, ny, nw, nh)
            elif target == "box":
                if 0 <= self._selected_box_idx < len(self._boxes):
                    b = self._boxes[self._selected_box_idx]
                    b["x"] = nx
                    b["y"] = ny
                    b["w"] = nw
                    b["h"] = nh
                    self.box_changed.emit(nx, ny, nw, nh)
                    self.boxes_updated.emit(self._boxes)
            elif target == "image":
                if self._fix_scale:
                    if self._img_pixmap and not self._img_pixmap.isNull() and self._img_pixmap.height() > 0:
                        aspect = float(self._img_pixmap.width()) / float(self._img_pixmap.height())
                    else:
                        aspect = max(0.01, float(self._img_w) / max(1.0, float(self._img_h)))
                    nh = max(10, int(round(nw / aspect)))
                    if ny + nh > self._video_h:
                        nh = self._video_h - ny
                        nw = max(10, int(round(nh * aspect)))
                self._img_x, self._img_y, self._img_w, self._img_h = nx, ny, nw, nh
                self.img_changed.emit(nx, ny, nw, nh)

            self.update()
            return

        # Hover cursor update
        t, h = self._hit_test(event.pos())
        if h == "body":
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        elif h in ("tl", "br"):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif h in ("tr", "bl"):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif h in ("l", "r"):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif h in ("t", "b"):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_action = None
        self._drag_start_pos = None
        self._orig_rect = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(event)

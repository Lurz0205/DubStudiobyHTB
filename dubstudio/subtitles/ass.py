"""Advanced SubStation Alpha (.ass) subtitle generator supporting Vietnamese typography."""
from dataclasses import dataclass
import math
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional


def format_ass_time(seconds: float) -> str:
    """Format seconds into ASS timestamp format: H:MM:SS.cs"""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis == 100:
        secs += 1
        centis = 0
    return f"{hrs:d}:{mins:02d}:{secs:02d}.{centis:02d}"


def wrap_balanced_lines(text: str, max_chars_per_line: int = 32) -> str:
    """Wrap Vietnamese text into balanced lines using \\N for ASS, respecting max_chars_per_line."""
    if "\n" in text:
        parts = [wrap_balanced_lines(p, max_chars_per_line) for p in text.splitlines() if p.strip()]
        return "\\N".join(parts)

    words = text.strip().split()
    if not words:
        return ""

    total_chars = len(text)
    if total_chars <= max_chars_per_line:
        return text

    # Determine target number of lines
    num_lines = max(2, round(total_chars / max_chars_per_line))
    target_len = total_chars / num_lines
    effective_max = max(max_chars_per_line, math.ceil(target_len))

    lines = []
    cur_line = []
    cur_len = 0

    for word in words:
        potential_len = cur_len + (1 + len(word) if cur_line else len(word))
        if cur_line and potential_len > effective_max and cur_len >= target_len * 0.75:
            lines.append(" ".join(cur_line))
            cur_line = [word]
            cur_len = len(word)
        else:
            cur_line.append(word)
            cur_len = potential_len

    if cur_line:
        lines.append(" ".join(cur_line))

    return "\\N".join(lines)


def hex_to_ass_color(hex_str: str, alpha: int = 0) -> str:
    """Convert CSS hex color '#RRGGBB' or 'rgba(r,g,b,a)' to ASS color '&HAABBGGRR'."""
    if not hex_str:
        return f"&H{max(0, min(255, alpha)):02X}000000"
    if hex_str.startswith("&H"):
        return hex_str
    if hex_str.startswith("rgba"):
        import re
        nums = re.findall(r"[\d.]+", hex_str)
        if len(nums) >= 3:
            r = int(float(nums[0]))
            g = int(float(nums[1]))
            b = int(float(nums[2]))
            a_val = float(nums[3]) if len(nums) >= 4 else 1.0
            ass_a = alpha if alpha > 0 else int(round((1.0 - a_val) * 255))
            return f"&H{max(0, min(255, ass_a)):02X}{b:02X}{g:02X}{r:02X}"
    hex_clean = hex_str.lstrip("#")
    if len(hex_clean) == 6:
        r, g, b = hex_clean[0:2], hex_clean[2:4], hex_clean[4:6]
    elif len(hex_clean) == 3:
        r, g, b = hex_clean[0]*2, hex_clean[1]*2, hex_clean[2]*2
    else:
        r, g, b = "FF", "FF", "FF"
    a_hex = f"{max(0, min(255, alpha)):02X}"
    return f"&H{a_hex}{b}{g}{r}"


PUNCT_SPLIT_CHARS = set(".,!?:;—–…\"'”’")
NATURAL_CONJUNCTIONS = {
    "và", "nhưng", "mà", "nên", "thì", "rồi", "để", "bởi", "do", "vì",
    "nếu", "tuy", "dù", "hoặc", "hay", "song", "đồng thời", "trong khi", "khi"
}


def split_subtitle_slices(
    text: str,
    start: float,
    end: float,
    target_words: int = 12,
    max_words: int = 15,
) -> List[Dict[str, Any]]:
    """
    Split a long subtitle sentence into clean display slices of ~10-15 words
    prioritizing natural pauses (punctuation or conjunctions), allocating
    duration proportionally based on word count without altering speech audio.
    """
    words = text.strip().split()
    if not words:
        return []
    total_words = len(words)
    if total_words <= max_words:
        return [{"text": text.strip(), "start": start, "end": end}]

    slices_words: List[List[str]] = []
    cur = 0
    while cur < total_words:
        rem = total_words - cur
        if rem <= max_words + 2:
            if rem <= max_words:
                slices_words.append(words[cur:])
                break
            else:
                half = rem // 2
                best_k = cur + half
                best_score = -999.0
                for k in range(cur + max(4, half - 3), min(total_words, cur + half + 4)):
                    prev_w = words[k - 1]
                    next_w = words[k].lower() if k < total_words else ""
                    score = 0.0
                    if any(prev_w.endswith(p) for p in PUNCT_SPLIT_CHARS):
                        score += 8.0
                    if next_w in NATURAL_CONJUNCTIONS:
                        score += 5.0
                    score -= abs(k - (cur + half)) * 0.5
                    if score > best_score:
                        best_score = score
                        best_k = k
                slices_words.append(words[cur:best_k])
                slices_words.append(words[best_k:])
                break
        else:
            min_k = cur + 8
            max_k = min(total_words - 4, cur + max_words + 2)
            if min_k >= max_k:
                max_k = min(total_words, cur + max_words)
                min_k = cur + max(1, target_words - 2)

            target_k = cur + target_words
            best_k = target_k
            best_score = -999.0

            for k in range(min_k, max_k + 1):
                prev_w = words[k - 1]
                next_w = words[k].lower() if k < total_words else ""
                score = 0.0
                if any(prev_w.endswith(p) for p in "?!."):
                    score += 10.0
                elif any(prev_w.endswith(p) for p in ",;:-—…"):
                    score += 7.0
                if next_w in NATURAL_CONJUNCTIONS:
                    score += 5.0
                score -= abs(k - target_k) * 0.6
                if score > best_score:
                    best_score = score
                    best_k = k

            slices_words.append(words[cur:best_k])
            cur = best_k

    total_dur = max(0.2, end - start)
    result = []
    running_start = start
    for idx, sl in enumerate(slices_words):
        if idx == len(slices_words) - 1:
            sl_end = end
        else:
            sl_dur = round(total_dur * (len(sl) / total_words), 3)
            sl_end = round(running_start + sl_dur, 3)
            sl_end = min(sl_end, end - 0.1)
            sl_end = max(sl_end, running_start + 0.1)

        result.append({
            "text": " ".join(sl),
            "start": round(running_start, 3),
            "end": round(sl_end, 3),
        })
        running_start = sl_end

    return result


def get_segment_slices(seg: Dict[str, Any], target_words: int = 12, max_words: int = 15) -> List[Dict[str, Any]]:
    """
    Resolve a subtitle segment into one or more timed slices.
    Priority:
    1. Explicit seg["sub_slices"] (created by user splitting sentence in Studio).
    2. Multi-line vi_text separated by newlines (\\n).
    3. Auto-split long sentences (>max_words words) via split_subtitle_slices.
    4. Single slice covering the entire segment duration.
    """
    if seg.get("mute_sub") or seg.get("muted_sub"):
        return []

    if "vi_text" in seg:
        raw_text = (seg.get("vi_text") or "").strip()
    elif "text" in seg:
        raw_text = (seg.get("text") or "").strip()
    else:
        raw_text = (seg.get("src_text") or "").strip()
    if not raw_text:
        return []

    st = float(seg.get("start", 0.0))
    en = float(seg.get("end", st + 1.0))
    total_dur = max(0.2, en - st)

    def _norm_cmp(s: str) -> str:
        import re
        return re.sub(r'[^\w\s]', '', s.lower()).strip()

    # 1. Explicit cues (from DP word-count splitting or manual edits)
    cues = seg.get("cues")
    if cues and isinstance(cues, list) and len(cues) > 0:
        valid_cues = [c for c in cues if isinstance(c, dict) and c.get("text", "").strip()]
        if valid_cues:
            combined_cues = " ".join(c.get("text", "").strip() for c in valid_cues)
            combined_raw = " ".join(raw_text.split())
            if combined_cues == combined_raw or _norm_cmp(combined_cues) == _norm_cmp(combined_raw):
                return [{
                    "text": c.get("text", "").strip(),
                    "start": float(c.get("start", st)),
                    "end": float(c.get("end", en)),
                } for c in valid_cues]

    # 2. Explicit sub_slices from studio (must match current raw_text to prevent stale subtitle burn)
    sub_slices = seg.get("sub_slices")
    if sub_slices and isinstance(sub_slices, list) and len(sub_slices) > 0:
        valid_slices = [s for s in sub_slices if isinstance(s, dict) and s.get("text", "").strip()]
        if valid_slices:
            combined_slices = " ".join(sl.get("text", "").strip() for sl in valid_slices)
            combined_raw = " ".join(raw_text.split())
            if combined_slices == combined_raw or _norm_cmp(combined_slices) == _norm_cmp(combined_raw):
                word_counts = [max(1, len(sl.get("text", "").strip().split())) for sl in valid_slices]
                total_w = sum(word_counts)
                res = []
                curr_t = st
                for idx, (sl, wc) in enumerate(zip(valid_slices, word_counts), start=1):
                    if idx == len(valid_slices):
                        seg_end = en
                    else:
                        dur = round(total_dur * (wc / total_w), 2)
                        seg_end = round(curr_t + dur, 2)
                        seg_end = max(curr_t + 0.1, min(en - 0.1 * (len(valid_slices) - idx), seg_end))
                    res.append({
                        "text": sl.get("text", "").strip(),
                        "start": round(curr_t, 3),
                        "end": round(seg_end, 3),
                    })
                    curr_t = seg_end
                return res

    # 2. Text containing newlines (\n) - sequential display with _effective_weight matching cue_split.py
    if "\n" in raw_text:
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
        if len(lines) > 1:
            punct_comma = {",", "，", ";", "；", "—", "-"}
            punct_term = {".", "。", "?", "？", "!", "！", "…"}

            def _line_weight(line_str: str) -> float:
                base = float(len(line_str.replace(" ", "")))
                if line_str and line_str[-1] in punct_comma:
                    base += 2.5
                elif line_str and line_str[-1] in punct_term:
                    base += 4.0
                return max(1.0, base)

            weights = [_line_weight(l) for l in lines]
            total_w = sum(weights)
            res = []
            curr_t = st
            for idx, (l, w) in enumerate(zip(lines, weights), start=1):
                if idx == len(lines):
                    seg_end = en
                else:
                    dur = round(total_dur * (w / total_w), 3)
                    seg_end = round(curr_t + dur, 3)
                    seg_end = max(curr_t + 0.1, min(en - 0.1 * (len(lines) - idx), seg_end))
                res.append({
                    "text": l,
                    "start": round(curr_t, 3),
                    "end": round(seg_end, 3),
                })
                curr_t = seg_end
            return res

    # 3. Auto-slice long sentences
    if len(raw_text.split()) > max_words:
        return split_subtitle_slices(raw_text, st, en, target_words=target_words, max_words=max_words)

    # 4. Single default slice
    return [{
        "text": raw_text,
        "start": round(st, 3),
        "end": round(en, 3),
    }]


def make_rounded_box_path(w: int, h: int, r: int) -> str:
    """Generate an ASS drawing path with cubic bezier curves for smooth rounded corners."""
    if r <= 0:
        return f"m 0 0 l {w} 0 l {w} {h} l 0 {h}"
    radius = min(r, w // 2, h // 2)
    k = 0.5522847498 * radius
    return (
        f"m {int(radius)} 0 "
        f"l {int(w - radius)} 0 "
        f"b {int(round(w - radius + k))} 0 {w} {int(round(radius - k))} {w} {int(radius)} "
        f"l {w} {int(h - radius)} "
        f"b {w} {int(round(h - radius + k))} {int(round(w - radius + k))} {h} {int(w - radius)} {h} "
        f"l {int(radius)} {h} "
        f"b {int(round(radius - k))} {h} 0 {int(round(h - radius + k))} 0 {int(h - radius)} "
        f"l 0 {int(radius)} "
        f"b 0 {int(round(radius - k))} {int(round(radius - k))} 0 {int(radius)} 0"
    )


# Platform-specific native font measurement structures
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _GDI_RECT(ctypes.Structure):
        _fields_ = [
            ("left", wintypes.LONG),
            ("top", wintypes.LONG),
            ("right", wintypes.LONG),
            ("bottom", wintypes.LONG),
        ]

    _gdi_font_cache: dict[tuple[str, int, bool], int] = {}
    _hdc_screen = None

    def _get_screen_hdc():
        global _hdc_screen
        if _hdc_screen is None:
            try:
                _hdc_screen = ctypes.windll.user32.GetDC(0)
            except Exception:
                _hdc_screen = None
        return _hdc_screen

    def _get_gdi_hfont(font_name: str, font_px: int, bold: bool = True) -> int | None:
        key = (font_name.lower(), font_px, bold)
        if key in _gdi_font_cache:
            return _gdi_font_cache[key]
        hdc = _get_screen_hdc()
        if not hdc:
            return None
        weight = 700 if bold else 400
        try:
            # CreateFontW: height is negative for character height in pixels
            # CLEARTYPE_QUALITY = 5, DEFAULT_CHARSET = 1
            hfont = ctypes.windll.gdi32.CreateFontW(
                -int(font_px), 0, 0, 0, weight, 0, 0, 0, 1, 0, 0, 5, 0, font_name
            )
            if hfont:
                _gdi_font_cache[key] = hfont
                return hfont
        except Exception:
            pass
        return None


def _measure_text_box_gdi(
    clean_text: str,
    font_name: str,
    font_px: int,
    pad_x: int,
    pad_y: int,
    box_mode: str,
    box_width_pct: float,
    video_width: int,
    text_align: str = "center",
) -> tuple[int, int] | None:
    """Measure exact subtitle box dimensions using native Windows GDI (0ms overhead, 0 external deps)."""
    if sys.platform != "win32":
        return None
    hdc = _get_screen_hdc()
    if not hdc:
        return None
    hfont = _get_gdi_hfont(font_name, font_px, bold=True)
    if not hfont:
        return None

    try:
        old_font = ctypes.windll.gdi32.SelectObject(hdc, hfont)

        # DT_CALCRECT = 0x00000400, DT_WORDBREAK = 0x00000010
        flags = 0x00000400 | 0x00000010
        if text_align == "left":
            flags |= 0x00000000
        elif text_align == "right":
            flags |= 0x00000002
        else:
            flags |= 0x00000001

        if box_mode == "wrap_text":
            target_w = max(40, int(round(video_width * (box_width_pct / 100.0))))
            avail_w = max(40, target_w - pad_x * 2)
            rect = _GDI_RECT(0, 0, avail_w, 2000)
            ctypes.windll.user32.DrawTextW(hdc, clean_text, -1, ctypes.byref(rect), flags)
            bw = rect.right - rect.left
            bh = rect.bottom - rect.top
            w = min(target_w, bw + pad_x * 2)
            h = bh + pad_y * 2
        else:
            w = int(round(video_width * (box_width_pct / 100.0)))
            avail_w = max(40, w - pad_x * 2)
            rect = _GDI_RECT(0, 0, avail_w, 2000)
            ctypes.windll.user32.DrawTextW(hdc, clean_text, -1, ctypes.byref(rect), flags)
            bh = rect.bottom - rect.top
            h = bh + pad_y * 2

        ctypes.windll.gdi32.SelectObject(hdc, old_font)
        return max(40, int(w)), max(20, int(h))
    except Exception:
        return None


def _measure_text_box_qt(
    clean_text: str,
    font_name: str,
    font_px: int,
    pad_x: int,
    pad_y: int,
    box_mode: str,
    box_width_pct: float,
    video_width: int,
    text_align: str = "center",
) -> tuple[int, int] | None:
    """Escape hatch: Fallback to Qt QFontMetrics ONLY if explicitly enabled via DUBSTUDIO_USE_QT_FONT=1."""
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QFont, QFontMetrics
        from PyQt6.QtCore import QRect, Qt
        if not QApplication.instance():
            _app = QApplication([])
        f = QFont(font_name)
        f.setPixelSize(font_px)
        f.setBold(True)
        fm = QFontMetrics(f)
        flags = Qt.TextFlag.TextWordWrap
        if text_align == "left":
            flags |= (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        elif text_align == "right":
            flags |= (Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        else:
            flags |= Qt.AlignmentFlag.AlignCenter

        if box_mode == "wrap_text":
            target_w = max(40, int(round(video_width * (box_width_pct / 100.0))))
            bound = fm.boundingRect(QRect(0, 0, max(40, target_w - pad_x * 2), 2000), flags, clean_text)
            w = min(target_w, bound.width() + pad_x * 2)
            h = bound.height() + pad_y * 2
        else:
            w = int(round(video_width * (box_width_pct / 100.0)))
            bound = fm.boundingRect(QRect(0, 0, max(40, w - pad_x * 2), 2000), flags, clean_text)
            h = bound.height() + pad_y * 2
        return max(40, w), max(20, h)
    except Exception:
        return None


def measure_text_box(
    text: str,
    font_name: str,
    font_px: int,
    pad_x: int,
    pad_y: int,
    box_mode: str,
    box_width_pct: float,
    video_width: int,
    text_align: str = "center",
) -> tuple[int, int]:
    """Measure exact subtitle box width and height matching typography metrics.
    Priority:
    1. Native Windows GDI (0ms overhead, 100% pixel parity, zero PyQt6 dependency).
    2. Fallback to Qt (if DUBSTUDIO_USE_QT_FONT=1 and PyQt6 is present).
    3. Mathematical heuristic fallback.
    """
    clean_text = text.replace(r"\N", "\n")

    # Optional escape hatch / rollback switch
    if os.getenv("DUBSTUDIO_USE_QT_FONT") == "1":
        res_qt = _measure_text_box_qt(
            clean_text, font_name, font_px, pad_x, pad_y, box_mode, box_width_pct, video_width, text_align
        )
        if res_qt is not None:
            return res_qt

    # 1. Primary: Windows Native GDI (fastest, most accurate on Windows, 0 external deps)
    res_gdi = _measure_text_box_gdi(
        clean_text, font_name, font_px, pad_x, pad_y, box_mode, box_width_pct, video_width, text_align
    )
    if res_gdi is not None:
        return res_gdi

    # 2. Secondary fallback: Qt if available
    res_qt = _measure_text_box_qt(
        clean_text, font_name, font_px, pad_x, pad_y, box_mode, box_width_pct, video_width, text_align
    )
    if res_qt is not None:
        return res_qt

    # 3. Tertiary fallback: Mathematical heuristic approximation
    lines = clean_text.splitlines() if clean_text else [""]
    num_lines = max(1, len(lines))
    line_h = int(round(font_px * 1.16))
    h = num_lines * line_h + pad_y * 2
    if box_mode == "wrap_text":
        max_chars = max(len(l.strip()) for l in lines) if lines else 10
        w = min(int(round(video_width * (box_width_pct / 100.0))), int(round(max_chars * font_px * 0.58)) + pad_x * 2)
    else:
        w = int(round(video_width * (box_width_pct / 100.0)))
    return max(40, w), max(20, h)


@dataclass
class SubtitleGeometry:
    box_left: int
    box_top: int
    box_w: int
    box_h: int
    font_size: int
    pad_x: int
    pad_y: int
    box_radius: int
    cx: int
    cy: int
    tx: int
    wrapped_text: str
    box_mode: str
    has_box: bool
    box_color: str
    box_opacity: float
    text_color: str
    outline_color: str
    outline_width: int
    text_align: str
    video_w: int
    video_h: int


def compute_subtitle_geometry(
    text: str,
    style: Optional[Dict[str, Any]] = None,
    video_w: int = 1280,
    video_h: int = 720,
) -> SubtitleGeometry:
    """
    Canonical Subtitle Geometry Engine.
    Computes exact subtitle box, font size, padding, and text coordinates strictly
    in native video pixel space (video_w x video_h).
    Ensures 100% pixel-perfect consistency between Preview (any panel size / aspect ratio) and final Render.
    """
    style = style or {}
    video_w = max(int(video_w or 1280), 100)
    video_h = max(int(video_h or 720), 100)

    font_name = style.get("font_name", "Arial") or "Arial"
    font_size_val = float(style.get("font_size", 24) or 24)
    outline_width_val = float(style.get("outline_width", 2) if style.get("outline_width") is not None else 2)
    margin_v_val = float(style.get("margin_v", 35) or 35)
    box_width_pct = float(style.get("box_width_pct", 85.0) or 85.0)
    box_mode = style.get("box_mode", "full_width") or "full_width"
    has_box = bool(style.get("has_box", True))
    box_opacity = float(style.get("box_opacity", 0.6) if style.get("box_opacity") is not None else 0.6)
    box_radius_val = float(style.get("box_radius", 6) if style.get("box_radius") is not None else 6)
    raw_box_color = style.get("box_color", "#000000") or "#000000"
    pos = style.get("position", "bottom") or "bottom"
    align_mode = style.get("text_align", "center") or "center"

    primary_color = style.get("primary_color", "#FFFFFF") or "#FFFFFF"
    outline_color = style.get("outline_color", "#000000") or "#000000"

    # Base typography scale against reference 720p height so Fontsize in ASS matches preview 1:1
    scale_v = max(video_h, 360) / 720.0
    ass_font_size = max(12, int(round(font_size_val * scale_v)))
    ass_outline_width = max(0, int(round(outline_width_val * scale_v)))
    ass_margin_v = max(2, int(round(margin_v_val * scale_v)))
    ass_box_radius = max(0, int(round(box_radius_val * scale_v)))

    box_pad_x = float(style.get("box_padding_x", 14) if style.get("box_padding_x") is not None else 14)
    box_pad_y = float(style.get("box_padding_y", 8) if style.get("box_padding_y") is not None else 8)
    ass_pad_x = max(4, int(round(box_pad_x * scale_v)))
    ass_pad_y = max(2, int(round(box_pad_y * scale_v)))

    # Balance word wrap based on native box width (100% of usable width between padding)
    box_w_ref = video_w * (box_width_pct / 100.0)
    approx_char_width = max(8.0, ass_font_size * 0.54)
    max_chars_per_line = max(12, int(max(40.0, box_w_ref - ass_pad_x * 2) / approx_char_width))
    wrapped_text = wrap_balanced_lines(text or "", max_chars_per_line=max_chars_per_line)

    box_w, box_h = measure_text_box(
        text=wrapped_text,
        font_name=font_name,
        font_px=ass_font_size,
        pad_x=ass_pad_x,
        pad_y=ass_pad_y,
        box_mode=box_mode,
        box_width_pct=box_width_pct,
        video_width=video_w,
        text_align=align_mode,
    )

    box_left = int(round((video_w - box_w) / 2.0))
    cx = int(round(video_w / 2.0))
    if style and style.get("pos_y_pct") is not None:
        pct = float(style["pos_y_pct"])
        # WYSIWYG preview positions the vertical center (cy) at posYPct% with transform: translate(-50%, -50%)
        cy = int(round(video_h * (pct / 100.0)))
        box_top = max(0, min(video_h - box_h, int(round(cy - box_h / 2.0))))
        cy = int(round(box_top + box_h / 2.0))
    elif pos == "top":
        box_top = ass_margin_v
        cy = int(round(box_top + box_h / 2.0))
    elif pos == "center":
        cy = int(round(video_h / 2.0))
        box_top = int(round((video_h - box_h) / 2.0))
    else:  # "bottom"
        box_top = int(round(video_h - ass_margin_v - box_h))
        cy = int(round(box_top + box_h / 2.0))

    if align_mode == "left":
        tx = int(round(box_left + ass_pad_x))
    elif align_mode == "right":
        tx = int(round(box_left + box_w - ass_pad_x))
    else:
        tx = cx

    return SubtitleGeometry(
        box_left=box_left,
        box_top=box_top,
        box_w=box_w,
        box_h=box_h,
        font_size=ass_font_size,
        pad_x=ass_pad_x,
        pad_y=ass_pad_y,
        box_radius=ass_box_radius,
        cx=cx,
        cy=cy,
        tx=tx,
        wrapped_text=wrapped_text,
        box_mode=box_mode,
        has_box=has_box,
        box_color=raw_box_color,
        box_opacity=box_opacity,
        text_color=primary_color,
        outline_color=outline_color,
        outline_width=ass_outline_width,
        text_align=align_mode,
        video_w=video_w,
        video_h=video_h,
    )


def generate_ass_subtitles(
    segments_or_units: List[Dict[str, Any]],
    output_path: Path,
    title: str = "dubstudio Vietnamese Subtitles",
    font_name: str = "Arial",
    font_size: int = 24,
    primary_color: str = "&H00FFFFFF",   # White (BGR)
    outline_color: str = "&H00000000",   # Black (BGR)
    outline_width: int = 2,
    margin_v: int = 35,
    video_width: int = 1280,
    video_height: int = 720,
    style: Optional[Dict[str, Any]] = None,
) -> Path:
    """Generate an ASS subtitle file formatted for clean typography and Vietnamese diacritics."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    box_width_pct = 85.0
    box_mode = "full_width"
    has_box = True
    box_opacity = 0.6
    box_radius = 6
    raw_box_color = "#000000"
    pos = "bottom"
    align_mode = "center"

    if style:
        font_name = style.get("font_name") or font_name
        font_size = int(style.get("font_size") or font_size)
        outline_width = int(style.get("outline_width") or outline_width)
        margin_v = int(style.get("margin_v") or margin_v)
        if style.get("video_width"):
            video_width = int(style["video_width"])
        if style.get("video_height"):
            video_height = int(style["video_height"])
        if style.get("box_width_pct"):
            box_width_pct = float(style["box_width_pct"])

        box_mode = style.get("box_mode", "full_width") or "full_width"
        has_box = bool(style.get("has_box", True))
        box_opacity = float(style.get("box_opacity", 0.6) if style.get("box_opacity") is not None else 0.6)
        box_radius = int(style.get("box_radius", 6) if style.get("box_radius") is not None else 6)
        raw_box_color = style.get("box_color", "#000000") or "#000000"

        if style.get("primary_color"):
            primary_color = hex_to_ass_color(style["primary_color"])
        if style.get("outline_color"):
            outline_color = hex_to_ass_color(style["outline_color"])

        pos = style.get("position", "bottom") or "bottom"
        align_mode = style.get("text_align", "center") or "center"

    # Base typography scale against reference 720p height so Fontsize in ASS (PlayResY) matches preview 1:1
    ref_h = 720.0
    scale_v = max(video_height, 360) / ref_h

    # Adjustable box padding: horizontal (width) and vertical (height/length)
    box_pad_x = float(style.get("box_padding_x", 14) if style and style.get("box_padding_x") is not None else 14)
    box_pad_y = float(style.get("box_padding_y", 8) if style and style.get("box_padding_y") is not None else 8)

    # Scaled dimensions in video pixel coordinates matching preview 1:1
    ass_font_size = max(12, int(round(font_size * scale_v)))
    # Compensate for Windows GDI / libass internal leading font scaling difference (~1.116x)
    ass_font_size_libass = max(12, int(round(ass_font_size * 1.116)))

    ass_outline_width = max(1, int(round(outline_width * scale_v)))
    ass_margin_v = max(5, int(round(margin_v * scale_v)))
    ass_box_radius = max(0, int(round(box_radius * scale_v)))
    ass_pad_x = max(4, int(round(box_pad_x * scale_v)))
    ass_pad_y = max(2, int(round(box_pad_y * scale_v)))
    box_opacity = max(0.0, min(1.0, box_opacity))
    box_alpha = int(round(255 * (1.0 - box_opacity)))
    alpha_hex = f"&H{box_alpha:02X}&"

    clean_box_bgr = hex_to_ass_color(raw_box_color, alpha=0)[4:]
    box_color_tag = f"&H{clean_box_bgr}&"

    # Max line length for wrapping
    box_w_ref = video_width * (box_width_pct / 100.0)
    approx_char_width = max(8.0, ass_font_size * 0.52)
    max_chars_per_line = max(12, int((box_w_ref - ass_font_size) / approx_char_width))

    header = f"""[Script Info]
; Script generated by dubstudio
Title: {title}
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: None
PlayResX: {video_width}
PlayResY: {video_height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{ass_font_size_libass},{primary_color},&H000000FF,{outline_color},&H00000000,-1,0,0,0,100,100,0,0,1,{ass_outline_width},0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    # Collect all slices and strictly eliminate time overlaps so next subtitle cleanly overrides previous subtitle
    all_slices = []
    for item in segments_or_units:
        slices = get_segment_slices(item)
        if slices:
            all_slices.extend(slices)

    all_slices.sort(key=lambda s: float(s.get("start", 0.0)))

    for k, sl in enumerate(all_slices):
        sl_start = float(sl.get("start", 0.0))
        sl_end = float(sl.get("end", 0.0))
        # Strictly truncate end time when overlapping with next subtitle
        if k + 1 < len(all_slices):
            next_start = float(all_slices[k + 1].get("start", 0.0))
            if sl_end > next_start:
                sl_end = max(sl_start + 0.05, next_start)

        sl_text = sl.get("text", "")
        start_str = format_ass_time(sl_start)
        end_str = format_ass_time(sl_end)

        geo = compute_subtitle_geometry(sl_text, style=style, video_w=video_width, video_h=video_height)

        if geo.text_align == "left":
            text_override = f"{{\\pos({geo.tx},{geo.cy})\\an4\\b1}}"
        elif geo.text_align == "right":
            text_override = f"{{\\pos({geo.tx},{geo.cy})\\an6\\b1}}"
        else:
            text_override = f"{{\\pos({geo.cx},{geo.cy})\\an5\\b1}}"

        if geo.has_box:
            path = make_rounded_box_path(geo.box_w, geo.box_h, geo.box_radius)
            bg_line = (
                f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,"
                f"{{\\pos({geo.box_left},{geo.box_top})\\an7\\bord0\\shad0\\1c{box_color_tag}\\1a{alpha_hex}\\p1}}"
                f"{path}{{\\p0}}"
            )
            events.append(bg_line)
            text_line = f"Dialogue: 1,{start_str},{end_str},Default,,0,0,0,,{text_override}{geo.wrapped_text}"
            events.append(text_line)
        else:
            text_line = f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text_override}{geo.wrapped_text}"
            events.append(text_line)

    full_content = header + "\n".join(events) + "\n"
    output_path.write_text(full_content, encoding="utf-8")
    return output_path


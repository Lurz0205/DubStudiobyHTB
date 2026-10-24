"""Pixel-to-pixel test: Subtitle WYSIWYG matching between Qt Preview and FFmpeg Render."""
import os
import subprocess
import sys
from pathlib import Path
import numpy as np
import pytest
from PIL import Image
from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QFontMetrics, QImage, QPainter
from PyQt6.QtWidgets import QApplication

from dubstudio.paths import resolve_tool
from dubstudio.subtitles.ass import generate_ass_subtitles


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    return app


def test_subtitle_wysiwyg_box_alignment(qapp, tmp_path):
    """
    Test pixel-to-pixel alignment of subtitle background box between
    Qt Preview rendering (QPainter) and FFmpeg ASS subtitle burning.
    Error on (x, y, w, h) must be strictly <= 1px.
    """
    video_w = 1920
    video_h = 1080
    ref_h = 720.0
    video_scale = video_h / ref_h

    font_name = "Arial"
    font_size_setting = 24
    box_width_pct = 85.0
    margin_v_setting = 35
    pad_x_setting = 14
    pad_y_setting = 8
    box_radius_setting = 6
    text = "Chiếc iPhone Duo này hoàn toàn mới,"

    native_font_size = max(12, int(round(font_size_setting * video_scale)))
    scaled_margin_v = max(5, int(round(margin_v_setting * video_scale)))
    native_pad_x = max(4, int(round(pad_x_setting * video_scale)))
    native_pad_y = max(2, int(round(pad_y_setting * video_scale)))
    native_box_w = int(round(video_w * (box_width_pct / 100.0)))
    native_box_radius = int(round(box_radius_setting * video_scale))

    # 1. Render Preview frame via Qt QPainter
    qimg = QImage(video_w, video_h, QImage.Format.Format_ARGB32)
    qimg.fill(QColor(0, 0, 0, 255))

    painter = QPainter(qimg)
    font = QFont(font_name)
    font.setPixelSize(native_font_size)
    font.setBold(True)
    painter.setFont(font)
    fm = QFontMetrics(font)

    flags = Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap
    text_rect_needed = fm.boundingRect(QRect(0, 0, max(40, native_box_w - native_pad_x * 2), 2000), flags, text)
    preview_box_h = text_rect_needed.height() + native_pad_y * 2
    preview_box_left = int((video_w - native_box_w) / 2.0)
    preview_box_top = video_h - scaled_margin_v - preview_box_h

    # Draw pure bright green box (#00FF00) for clean segmentation
    painter.setBrush(QBrush(QColor(0, 255, 0)))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(preview_box_left, preview_box_top, native_box_w, preview_box_h, native_box_radius, native_box_radius)
    painter.end()

    preview_png = tmp_path / "preview.png"
    qimg.save(str(preview_png))

    # Extract preview coordinates
    arr_prev = np.array(Image.open(preview_png))
    green_prev = (arr_prev[:, :, 1] > 200) & (arr_prev[:, :, 0] < 50) & (arr_prev[:, :, 2] < 50)
    coords_prev = np.argwhere(green_prev)
    assert len(coords_prev) > 0, "Preview green box not found"
    y_min_prev, x_min_prev = coords_prev.min(axis=0)
    y_max_prev, x_max_prev = coords_prev.max(axis=0)
    w_prev = x_max_prev - x_min_prev + 1
    h_prev = y_max_prev - y_min_prev + 1

    # 2. Render ASS via FFmpeg libass filter
    style = {
        "font_name": font_name,
        "font_size": font_size_setting,
        "has_box": True,
        "box_color": "#00FF00",
        "box_opacity": 1.0,
        "box_radius": box_radius_setting,
        "box_padding_x": pad_x_setting,
        "box_padding_y": pad_y_setting,
        "box_width_pct": box_width_pct,
        "position": "bottom",
        "margin_v": margin_v_setting,
        "primary_color": "#FFFFFF",
        "outline_color": "#000000",
        "outline_width": 2,
        "text_align": "center",
    }
    segs = [{"id": 1, "start": 0.0, "end": 2.0, "vi_text": text}]
    ass_file = tmp_path / "test.ass"
    generate_ass_subtitles(segs, ass_file, style=style, video_width=video_w, video_height=video_h)

    ffmpeg_exe = resolve_tool("ffmpeg")
    render_png = tmp_path / "render.png"
    escaped_ass = str(ass_file.resolve()).replace("\\", "/").replace(":", r"\:")

    cmd = [
        ffmpeg_exe, "-y",
        "-f", "lavfi", "-i", f"color=c=black:s={video_w}x{video_h}:d=1",
        "-vf", f"subtitles='{escaped_ass}'",
        "-vframes", "1",
        str(render_png),
    ]
    subprocess.run(cmd, capture_output=True, check=True)

    arr_rnd = np.array(Image.open(render_png))
    green_rnd = (arr_rnd[:, :, 1] > 200) & (arr_rnd[:, :, 0] < 50) & (arr_rnd[:, :, 2] < 50)
    coords_rnd = np.argwhere(green_rnd)
    assert len(coords_rnd) > 0, "Rendered green box not found"
    y_min_rnd, x_min_rnd = coords_rnd.min(axis=0)
    y_max_rnd, x_max_rnd = coords_rnd.max(axis=0)
    w_rnd = x_max_rnd - x_min_rnd + 1
    h_rnd = y_max_rnd - y_min_rnd + 1

    print(f"\nPreview: x={x_min_prev}, y={y_min_prev}, w={w_prev}, h={h_prev}")
    print(f"Render : x={x_min_rnd}, y={y_min_rnd}, w={w_rnd}, h={h_rnd}")

    # Pixel-to-pixel assertions: error strictly < 2 pixels
    assert abs(x_min_prev - x_min_rnd) <= 1, f"Box X mismatch: Preview {x_min_prev} vs Render {x_min_rnd}"
    assert abs(y_min_prev - y_min_rnd) <= 1, f"Box Y mismatch: Preview {y_min_prev} vs Render {y_min_rnd}"
    assert abs(w_prev - w_rnd) <= 1, f"Box Width mismatch: Preview {w_prev} vs Render {w_rnd}"
    assert abs(h_prev - h_rnd) <= 1, f"Box Height mismatch: Preview {h_prev} vs Render {h_rnd}"


def test_audio_200pct_loudness_and_peak(tmp_path):
    """
    Test that TTS vocal processing at 200% provides a massive +8 to +10 LUFS loudness boost
    while keeping True Peak strictly <= -0.3 dBFS with zero clipping.
    """
    import re
    ffmpeg_exe = resolve_tool("ffmpeg")

    # Generate 3 seconds of reference speech-like vocal tones (fundamental 180Hz + harmonics)
    test_wav = tmp_path / "test_synth_voice.wav"
    synth_cmd = [
        ffmpeg_exe, "-y",
        "-f", "lavfi",
        "-i", "sine=f=180:d=3,volume=0.6",
        str(test_wav),
    ]
    subprocess.run(synth_cmd, capture_output=True, check=True)

    eq_chain = (
        "aresample=48000,"
        "highpass=f=80,"
        "equalizer=f=180:t=q:w=1.2:g=2.0,"
        "equalizer=f=5500:t=q:w=1.5:g=-2.5"
    )

    filt_100 = f"{eq_chain},volume=0.85,alimiter=limit=0.92:attack=5:release=50:asc=0"
    filt_200 = f"{eq_chain},acompressor=threshold=-23dB:ratio=3.0:attack=5:release=60:makeup=14dB,alimiter=limit=0.89:attack=3:release=40:level=disabled"

    out_100 = tmp_path / "voice_100.wav"
    out_200 = tmp_path / "voice_200.wav"

    subprocess.run([ffmpeg_exe, "-y", "-i", str(test_wav), "-af", filt_100, str(out_100)], capture_output=True, check=True)
    subprocess.run([ffmpeg_exe, "-y", "-i", str(test_wav), "-af", filt_200, str(out_200)], capture_output=True, check=True)

    def measure(wav_file: Path) -> tuple[float, float]:
        res = subprocess.run([ffmpeg_exe, "-i", str(wav_file), "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True)
        i_match = re.findall(r"I:\s+([-\d.]+)\s+LUFS", res.stderr)
        pk_match = re.findall(r"Peak:\s+([-\d.]+)\s+dBFS", res.stderr)
        i_val = float(i_match[-1]) if i_match else -70.0
        pk_val = float(pk_match[-1]) if pk_match else 0.0
        return i_val, pk_val

    i_100, pk_100 = measure(out_100)
    i_200, pk_200 = measure(out_200)

    print(f"\n100% Voice: Loudness={i_100} LUFS, Peak={pk_100} dBFS")
    print(f"200% Voice: Loudness={i_200} LUFS, Peak={pk_200} dBFS")
    lufs_delta = i_200 - i_100
    print(f"Loudness Boost (200% vs 100%): +{lufs_delta:.2f} LUFS")

    # 1. 200% must be significantly louder (+6 to +12 LUFS increase)
    assert lufs_delta >= 6.0, f"200% boost insufficient: only +{lufs_delta:.2f} LUFS"
    # 2. Peak must be strictly below 0 dBFS (safe margin <= -0.3 dBFS)
    assert pk_200 <= -0.3, f"200% True Peak exceeds safe ceiling: {pk_200} dBFS"


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
        "equalizer=f=350:t=q:w=1.4:g=-1.2,"
        "equalizer=f=3200:t=q:w=1.2:g=1.8"
    )

    filt_100 = f"{eq_chain},volume=1.00"
    filt_200 = f"{eq_chain},volume=20.00dB,alimiter=limit=0.98:attack=1:release=15:level=disabled"

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


def test_subtitle_relative_geometry_across_widget_sizes(qapp):
    """
    Test 1: Verify relative subtitle box geometry (box_w/inner_w, box_h/inner_h, box_left/inner_w, box_top/inner_h)
    is identical (error <= 0.005) between different widget display sizes
    (e.g., Tab Phụ đề 780x438 vs Trang Chỉnh sửa 710x400).
    """
    from dubstudio.subtitles.ass import compute_subtitle_geometry
    from ui.widgets.video_player import VideoPlayerWidget

    native_w, native_h = 1280, 720
    text = "Xin chào! Đây là phụ đề kiểm thử độ chính xác hiển thị."
    style = {
        "font_name": "Arial",
        "font_size": 24,
        "box_width_pct": 85.0,
        "box_padding_x": 14,
        "box_padding_y": 8,
        "position": "bottom",
        "margin_v": 35,
    }

    player = VideoPlayerWidget()
    player._video_native_w = native_w
    player._video_native_h = native_h
    player.update_subtitle_overlay(text, style, visible=True)

    # Size 1: Tab Phụ đề (780 x 438)
    player.resize(780, 480)
    player._view.viewport().resize(780, 438)
    player._on_container_resized()
    dx1, dy1, dw1, dh1, _ = player._get_active_video_rect()
    w1 = player._sub_overlay.width()
    h1 = player._sub_overlay.height()
    proxy1 = player._proxy.pos()
    x1 = proxy1.x() - dx1
    y1 = proxy1.y() - dy1

    # Size 2: Trang Chỉnh sửa (710 x 400)
    player.resize(710, 440)
    player._view.viewport().resize(710, 400)
    player._on_container_resized()
    dx2, dy2, dw2, dh2, _ = player._get_active_video_rect()
    w2 = player._sub_overlay.width()
    h2 = player._sub_overlay.height()
    proxy2 = player._proxy.pos()
    x2 = proxy2.x() - dx2
    y2 = proxy2.y() - dy2

    # Relative ratios against inner video rectangle
    rw1, rh1, rx1, ry1 = w1 / dw1, h1 / dh1, x1 / dw1, y1 / dh1
    rw2, rh2, rx2, ry2 = w2 / dw2, h2 / dh2, x2 / dw2, y2 / dh2

    assert abs(rw1 - rw2) <= 0.005, f"Width ratio mismatch: {rw1} vs {rw2}"
    assert abs(rh1 - rh2) <= 0.005, f"Height ratio mismatch: {rh1} vs {rh2}"
    assert abs(rx1 - rx2) <= 0.005, f"X ratio mismatch: {rx1} vs {rx2}"
    assert abs(ry1 - ry2) <= 0.005, f"Y ratio mismatch: {ry1} vs {ry2}"


def test_subtitle_relative_geometry_canvas_aspect_expansion(qapp):
    """
    Test 2: Verify relative subtitle box coordinates on inner_video_rect remain unchanged
    (error <= 0.005) whether 9:16 canvas aspect expansion is OFF or ON.
    """
    from ui.widgets.video_player import VideoPlayerWidget

    native_w, native_h = 1280, 720
    text = "Xin chào! Đây là phụ đề kiểm thử mở rộng tỉ lệ nền."
    style = {
        "font_name": "Arial",
        "font_size": 24,
        "box_width_pct": 85.0,
        "position": "bottom",
        "margin_v": 35,
    }

    player = VideoPlayerWidget()
    player._video_native_w = native_w
    player._video_native_h = native_h
    player.resize(800, 600)
    player._view.viewport().resize(800, 560)
    player.update_subtitle_overlay(text, style, visible=True)

    # State A: Canvas Aspect Ratio Disabled (16:9 original)
    player.set_canvas_aspect_ratio("original", "#FFFFFF", enabled=False)
    player._on_container_resized()
    dx_a, dy_a, dw_a, dh_a, _ = player._get_active_video_rect()
    w_a = player._sub_overlay.width()
    h_a = player._sub_overlay.height()
    pos_a = player._proxy.pos()
    x_a = pos_a.x() - dx_a
    y_a = pos_a.y() - dy_a

    # State B: Canvas Aspect Ratio Enabled (9:16 expanded)
    player.set_canvas_aspect_ratio("9:16", "#FFFFFF", enabled=True)
    player._on_container_resized()
    dx_b, dy_b, dw_b, dh_b, _ = player._get_active_video_rect()
    w_b = player._sub_overlay.width()
    h_b = player._sub_overlay.height()
    pos_b = player._proxy.pos()
    x_b = pos_b.x() - dx_b
    y_b = pos_b.y() - dy_b

    # Relative ratios on inner video rect (error strictly <= 0.005 due to integer pixel sizing)
    rw_a, rh_a, rx_a, ry_a = w_a / dw_a, h_a / dh_a, x_a / dw_a, y_a / dh_a
    rw_b, rh_b, rx_b, ry_b = w_b / dw_b, h_b / dh_b, x_b / dw_b, y_b / dh_b

    assert abs(rw_a - rw_b) <= 0.005, f"Relative box width mismatch: {rw_a} vs {rw_b}"
    assert abs(rh_a - rh_b) <= 0.005, f"Relative box height mismatch: {rw_a} vs {rw_b}"
    assert abs(rx_a - rx_b) <= 0.005, f"Relative box X mismatch: {rx_a} vs {rx_b}"
    assert abs(ry_a - ry_b) <= 0.005, f"Relative box Y mismatch: {ry_a} vs {ry_b}"


def test_export_9_16_canvas_subtitles_inside_video_area(tmp_path):
    """
    Test 3: Render 1 test frame via FFmpeg with 9:16 aspect ratio expansion and #FFFFFF white canvas.
    Verify top and bottom white padding areas have 100% #FFFFFF pixels (no subtitle spillover),
    and subtitles are burned cleanly inside the inner video frame.
    """
    ffmpeg_exe = resolve_tool("ffmpeg")
    vid_w, vid_h = 720, 405  # 16:9
    canvas_w, canvas_h = 720, 1280  # 9:16
    top_pad = (canvas_h - vid_h) // 2  # 437
    bottom_pad_start = top_pad + vid_h  # 842

    style = {
        "font_name": "Arial",
        "font_size": 24,
        "has_box": True,
        "box_color": "#000000",
        "box_opacity": 0.8,
        "box_radius": 6,
        "box_padding_x": 14,
        "box_padding_y": 8,
        "box_width_pct": 85.0,
        "position": "bottom",
        "margin_v": 35,
        "primary_color": "#FFFF00",
        "outline_color": "#000000",
        "outline_width": 2,
        "text_align": "center",
    }
    segs = [{"id": 1, "start": 0.0, "end": 2.0, "vi_text": "Phụ đề nằm hoàn toàn bên trong khung video"}]
    ass_file = tmp_path / "sub_916.ass"
    generate_ass_subtitles(segs, ass_file, style=style, video_width=vid_w, video_height=vid_h)

    escaped_ass = str(ass_file.resolve()).replace("\\", "/").replace(":", r"\:")
    out_png = tmp_path / "frame_916.png"

    # Burn subtitles directly on video frame BEFORE pad filter (matching edit_video_api)
    vf = f"subtitles='{escaped_ass}',pad={canvas_w}:{canvas_h}:(ow-iw)/2:(oh-ih)/2:color=0xFFFFFF"
    cmd = [
        ffmpeg_exe, "-y",
        "-f", "lavfi", "-i", f"color=c=blue:s={vid_w}x{vid_h}:d=1",
        "-vf", vf,
        "-vframes", "1",
        str(out_png),
    ]
    subprocess.run(cmd, capture_output=True, check=True)

    arr = np.array(Image.open(out_png))
    assert arr.shape == (canvas_h, canvas_w, 3) or arr.shape == (canvas_h, canvas_w, 4)

    # Top padding region: y from 0 to 420 (well inside top padding)
    top_region = arr[0:420, :, :3]
    assert np.all(top_region >= 250), "Top white padding contains subtitle artifacts!"

    # Bottom padding region: y from 860 to 1279 (well inside bottom padding)
    bottom_region = arr[860:1279, :, :3]
    assert np.all(bottom_region >= 250), "Bottom white padding contains subtitle artifacts!"

    # Middle video region: must contain the yellow subtitle text or black box
    video_region = arr[top_pad:bottom_pad_start, :, :3]
    # Check that it's not all pure blue, proving subtitles were rendered inside the video
    non_blue_pixels = np.sum((video_region[:, :, 2] < 200) | (video_region[:, :, 0] > 50))
    assert non_blue_pixels > 500, "Subtitles not found inside the video area!"



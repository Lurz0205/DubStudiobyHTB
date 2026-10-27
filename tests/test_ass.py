import pytest
from dubstudio.subtitles.ass import format_ass_time, generate_ass_subtitles, wrap_balanced_lines


def test_format_ass_time():
    assert format_ass_time(0.0) == "0:00:00.00"
    assert format_ass_time(1.25) == "0:00:01.25"
    assert format_ass_time(65.5) == "0:01:05.50"
    assert format_ass_time(3600.0) == "1:00:00.00"


def test_wrap_balanced_lines():
    short_text = "Xin chào các bạn"
    assert wrap_balanced_lines(short_text, max_chars_per_line=30) == short_text

    long_text = "Chào mừng quý vị và các bạn đã quay trở lại với kênh video của chúng tôi"
    wrapped = wrap_balanced_lines(long_text, max_chars_per_line=35)
    assert "\\N" in wrapped
    parts = wrapped.split("\\N")
    assert len(parts) == 2


def test_generate_ass_subtitles(tmp_path):
    segments = [
        {"id": 1, "start": 0.5, "end": 2.5, "vi_text": "Chào mừng các bạn đến với dubstudio!"},
        {"id": 2, "start": 3.0, "end": 5.0, "vi_text": "Phần mềm lồng tiếng video Trung Việt chất lượng cao."},
    ]
    out_ass = tmp_path / "test.ass"
    generate_ass_subtitles(segments, out_ass)

    assert out_ass.exists()
    content = out_ass.read_text(encoding="utf-8")
    assert "[Script Info]" in content
    assert "[V4+ Styles]" in content
    assert "dubstudio" in content


def test_make_rounded_box_path():
    from dubstudio.subtitles.ass import make_rounded_box_path
    # Sharp box
    sharp = make_rounded_box_path(400, 60, 0)
    assert sharp.startswith("m 0 0 l 400 0")
    assert "b " not in sharp

    # Rounded box
    rounded = make_rounded_box_path(400, 60, 10)
    assert "b " in rounded
    assert rounded.startswith("m 10 0 l 390 0")


def test_generate_ass_with_rounded_box_styling(tmp_path):
    from dubstudio.subtitles.ass import generate_ass_subtitles
    segments = [
        {"id": 1, "start": 0.0, "end": 2.0, "vi_text": "Thử nghiệm hộp nền bo góc và độ mờ."},
    ]
    style = {
        "font_name": "Arial",
        "font_size": 28,
        "primary_color": "#FFFFFF",
        "outline_color": "#000000",
        "outline_width": 2,
        "has_box": True,
        "box_color": "#000000",
        "box_opacity": 0.6,
        "box_radius": 12,
        "box_mode": "full_width",
        "box_width_pct": 90.0,
        "position": "bottom",
        "margin_v": 35,
        "text_align": "center",
    }
    out_ass = tmp_path / "styled.ass"
    generate_ass_subtitles(segments, out_ass, style=style, video_width=1280, video_height=720)

    content = out_ass.read_text(encoding="utf-8")
    assert "\\1a&H66&" in content  # 1 - 0.6 = 0.4 -> 0.4 * 255 = 102 = 0x66
    assert "\\1c&H000000&" in content
    assert "\\an7" in content
    assert "\\an5" in content
    assert "b " in content  # bezier rounded corners


def test_generate_ass_with_pos_y_pct(tmp_path):
    segments = [
        {"id": 1, "start": 0.0, "end": 2.0, "vi_text": "Phụ đề ở chính giữa màn hình."},
    ]
    # Set continuous vertical percentage to 50%
    style = {
        "pos_y_pct": 50.0,
        "has_box": True,
    }
    out_ass = tmp_path / "center_pct.ass"
    generate_ass_subtitles(segments, out_ass, style=style, video_width=1280, video_height=720)

    content = out_ass.read_text(encoding="utf-8")
    assert "\\pos(" in content
    # For video_height 720 and pos_y_pct 50%, box_top is 360
    assert "\\pos(80,360)" in content or ",360)" in content or ",37" in content


def test_measure_text_box_native_gdi_no_pyqt6():
    import subprocess
    import sys

    # Run check in a clean isolated subprocess to guarantee PyQt6 is never imported
    cmd = [
        sys.executable,
        "-c",
        (
            "import sys; "
            "from dubstudio.subtitles.ass import measure_text_box; "
            "w, h = measure_text_box('Xin chào các bạn đã quay trở lại', 'Arial', 48, 12, 10, 'wrap_text', 85.0, 1080); "
            "assert w > 100 and h > 40; "
            "assert not any(m.startswith('PyQt6') for m in sys.modules), 'PyQt6 should not be imported'"
        ),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"Subprocess failed: {res.stderr}"


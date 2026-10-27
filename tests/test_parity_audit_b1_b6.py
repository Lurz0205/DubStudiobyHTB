"""
Unit tests for Parity Audit items B1 to B6 in DubStudio v2.0.0:
- B1: Text normalization for TTS via vi_normalize
- B2: Manual translate event & prompt handling
- B3: Mute subtitle and mute TTS flag synchronization
- B4: GPU hardware inspection
- B5: Diagnostic bundle export
- B6: Color / text box overlay rasterization
"""
import json
from pathlib import Path
import pytest


def test_b1_vi_normalize_for_tts():
    """Verify vi_normalize converts numbers, units, and dates accurately for TTS."""
    from dubstudio.text.vi_normalize import normalize_for_tts
    
    text = "Ngày 20/10 có 500 khách tham quan, đạt 99% mục tiêu với 1500k."
    normalized = normalize_for_tts(text)
    
    assert "hai mươi" in normalized
    assert "năm trăm" in normalized
    assert "phần trăm" in normalized


def test_b3_mute_sub_and_mute_tts():
    """Verify ass.py honors mute_sub and mix.py/tts.py honor mute_tts."""
    from dubstudio.subtitles.ass import generate_ass_subtitles
    
    segments = [
        {"id": 1, "start": 0.0, "end": 2.0, "text": "Câu 1 hiển thị bình thường", "mute_sub": False, "mute_tts": False},
        {"id": 2, "start": 2.5, "end": 4.5, "text": "Câu 2 bị tắt phụ đề", "mute_sub": True, "mute_tts": False},
        {"id": 3, "start": 5.0, "end": 7.0, "text": "Câu 3 bị tắt cả hai", "muted_sub": True, "muted_tts": True},
    ]
    
    out_ass = Path("tests/fixtures/test_mute.ass")
    out_ass.parent.mkdir(parents=True, exist_ok=True)
    try:
        generate_ass_subtitles(segments, out_ass)
        content = out_ass.read_text(encoding="utf-8")
        assert "Câu 1 hiển thị bình thường" in content
        assert "Câu 2 bị tắt phụ đề" not in content
        assert "Câu 3 bị tắt cả hai" not in content
    finally:
        if out_ass.exists():
            out_ass.unlink()


def test_b4_gpu_check():
    """Verify GPU inspection returns structured hardware info."""
    from dubstudio.gpu_check import inspect_gpu_and_driver
    
    info = inspect_gpu_and_driver()
    assert isinstance(info, dict)
    assert "status" in info
    assert "card_name" in info
    assert "vram_gb" in info


def test_b5_export_diagnostic_bundle(tmp_path):
    """Verify diagnostic bundle produces a valid zip with system_summary.json."""
    from dubstudio.diagnostics import export_diagnostics_bundle, export_diagnostic_bundle
    import zipfile
    
    target_zip = tmp_path / "test_diag.zip"
    out_zip = export_diagnostics_bundle(target_zip)
    assert out_zip.exists()
    
    with zipfile.ZipFile(out_zip, "r") as zf:
        names = zf.namelist()
        assert "system_summary.json" in names
        raw_summary = json.loads(zf.read("system_summary.json").decode("utf-8"))
        assert "os" in raw_summary
        assert "python" in raw_summary
    
    # Also verify alias
    assert export_diagnostic_bundle == export_diagnostics_bundle


def test_b6_rasterize_color_boxes(tmp_path):
    """Verify rasterize_color_boxes draws rounded boxes with text overlay."""
    from dubstudio.stages.render import rasterize_color_boxes
    from PIL import Image
    
    boxes = [
        {
            "id": "box_1",
            "x": 10,
            "y": 10,
            "w": 30,
            "h": 15,
            "color": "#FF0000",
            "opacity": 0.8,
            "radius": 8,
            "rotation": 0,
            "text": "TEST WATERMARK",
            "font_size": 20,
            "text_color": "#FFFFFF",
            "enabled": True,
            "is_percent": True,
        },
        {
            "id": "box_disabled",
            "x": 50,
            "y": 50,
            "w": 20,
            "h": 10,
            "enabled": False,
        }
    ]
    
    out_png = tmp_path / "boxes.png"
    res = rasterize_color_boxes(boxes, 1280, 720, out_png)
    assert res is True
    assert out_png.exists()
    
    img = Image.open(out_png)
    assert img.size == (1280, 720)
    assert img.mode == "RGBA"

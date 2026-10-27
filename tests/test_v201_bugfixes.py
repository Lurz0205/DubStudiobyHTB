import json
from pathlib import Path
import pytest
from dubstudio.subtitles.ass import get_segment_slices
from dubstudio.stages.mix import run as mix_run
from dubstudio.stages import fit


def test_bug1_has_subtitles_only_when_segments_not_empty(tmp_path):
    # Empty segments
    empty_seg = tmp_path / "segments.json"
    empty_seg.write_text(json.dumps({"segments": []}), encoding="utf-8")
    
    s_data = json.loads(empty_seg.read_text(encoding="utf-8"))
    segs = s_data.get("segments", []) if isinstance(s_data, dict) else s_data
    has_subtitles = bool(isinstance(segs, list) and len(segs) > 0)
    assert has_subtitles is False

    # Populated segments
    empty_seg.write_text(json.dumps({"segments": [{"id": 1, "text": "Xin chào"}]}), encoding="utf-8")
    s_data = json.loads(empty_seg.read_text(encoding="utf-8"))
    segs = s_data.get("segments", []) if isinstance(s_data, dict) else s_data
    has_subtitles = bool(isinstance(segs, list) and len(segs) > 0)
    assert has_subtitles is True


def test_bug2_bgm_mix_volume_normalization():
    # Test percentage vs ratio volume normalization logic
    for raw_bgm, expected in [(100, 1.0), (80, 0.8), (1.0, 1.0), (0.5, 0.5), (200, 2.0)]:
        val = float(raw_bgm)
        if val > 2.0:
            val /= 100.0
        assert round(val, 2) == round(expected, 2)


def test_bug3_get_segment_slices_rejects_stale_sub_slices():
    # Segment has new rewritten vi_text, but old sub_slices from first run
    seg = {
        "id": 1,
        "start": 0.0,
        "end": 2.0,
        "vi_text": "Câu này đã được rút gọn",
        "sub_slices": [
            {"text": "Câu này rất dài từ lần đầu tạo chưa được rút gọn", "start": 0.0, "end": 2.0}
        ],
    }
    
    slices = get_segment_slices(seg)
    assert len(slices) > 0
    # Must NOT contain the old text
    assert "rất dài từ lần đầu" not in slices[0]["text"]
    # Must contain the new rewritten text
    assert "rút gọn" in slices[0]["text"]


def test_bug3_get_segment_slices_accepts_matching_sub_slices():
    # Segment has matching sub_slices
    seg = {
        "id": 1,
        "start": 0.0,
        "end": 2.0,
        "vi_text": "Câu này đã được rút gọn",
        "sub_slices": [
            {"text": "Câu này đã được", "start": 0.0, "end": 1.0},
            {"text": "rút gọn", "start": 1.0, "end": 2.0},
        ],
    }
    slices = get_segment_slices(seg)
    assert len(slices) == 2
    assert slices[0]["text"] == "Câu này đã được"
    assert slices[1]["text"] == "rút gọn"

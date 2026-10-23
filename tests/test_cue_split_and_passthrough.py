"""Tests for Punctuation-first cue splitting and Original Audio Passthrough / Mute TTS."""
import json
import pytest
from pathlib import Path
from dubstudio.subtitles.cue_split import split_sentence_cues, _split_into_clauses
from dubstudio.subtitles.ass import get_segment_slices
from dubstudio.config import AppConfig


def test_intro_adverbial_clause_merged():
    """
    User request test case:
    'Với mình, những điều đó là...'
    Cụm mở đầu 2-3 từ ('Với mình,') không bị tách riêng thành 1 dòng đơn lẻ
    khi số từ ước lượng (target_n) đủ lớn.
    """
    text = "Với mình, những điều đó là vô cùng quan trọng đối với tương lai sau này."
    cues = split_sentence_cues(text, start=0.0, end=10.0, target_n=7)
    
    assert len(cues) >= 1
    # Dòng đầu tiên phải bắt đầu bằng 'Với mình,' và KHÔNG được đứng một mình (chỉ có 2 từ)
    first_cue = cues[0]["text"]
    assert first_cue.startswith("Với mình,")
    assert len(first_cue.split()) > 2, f"Cụm mở đầu bị tách riêng trơ trọi: '{first_cue}'"
    assert "những điều đó" in first_cue


def test_intro_adverbial_variations():
    """Kiểm tra các trạng từ mở đầu ngắn khác: 'Theo tôi,', 'Thực ra,', 'Tuy nhiên,'"""
    samples = [
        "Theo tôi, quyết định này sẽ đem lại lợi ích to lớn.",
        "Thực ra, chúng ta đã có câu trả lời ngay từ đầu.",
        "Tuy nhiên, kế hoạch ban đầu cần được xem xét lại kỹ càng.",
    ]
    for text in samples:
        cues = split_sentence_cues(text, start=0.0, end=8.0, target_n=6)
        first_cue = cues[0]["text"]
        # Phải chứa cả cụm mở đầu và vế kế tiếp trong cùng 1 cue
        assert len(first_cue.split()) >= 4, f"Bị tách cụm mở đầu ngắn thành cue riêng: '{first_cue}'"


def test_mandatory_comma_split_between_clauses():
    """
    Kiểm tra hai vế câu bình thường cách nhau bằng dấu phẩy
    thì bắt buộc điểm ngắt phải ở dấu phẩy chứ không chém ngang giữa vế.
    """
    text = "Hôm nay tôi đi làm rất mệt, nhưng tôi vẫn cố gắng hoàn thành công việc được giao."
    cues = split_sentence_cues(text, start=0.0, end=12.0, target_n=6)
    
    assert len(cues) >= 2
    # Dòng 1 bắt buộc kết thúc bằng dấu phẩy, vế 1 trọn vẹn
    assert cues[0]["text"] == "Hôm nay tôi đi làm rất mệt,"
    # Dòng 2 tiếp nối bắt đầu bằng 'nhưng'
    assert cues[1]["text"].startswith("nhưng")


def test_ass_empty_vi_text_no_fallback_to_chinese():
    """
    Khi người dùng xóa phụ đề (vi_text=''), hệ thống không được fallback về src_text (tiếng Trung).
    Phải trả về rỗng [] để phụ đề không hiển thị trên video.
    """
    seg = {
        "id": 1,
        "start": 0.0,
        "end": 2.5,
        "vi_text": "",
        "src_text": "今天天气很好",
        "zh": "今天天气很好",
    }
    slices = get_segment_slices(seg)
    assert slices == [], f"Dù vi_text='' nhưng vẫn fallback về: {slices}"


def test_batch_update_and_delete_api():
    """
    Kiểm tra backend API lưu trữ chính xác mute_tts, keep_original và xóa hàng loạt.
    """
    import shutil
    from fastapi.testclient import TestClient
    from dubstudio.api.app import app

    job_id = "test_job_passthrough_api"
    ws = Path("workspace") / job_id
    ws.mkdir(parents=True, exist_ok=True)
    seg_file = ws / "segments.json"
    dummy_data = {
        "job_id": job_id,
        "segments": [
            {"id": 1, "start": 0.0, "end": 2.0, "vi_text": "Đoạn 1", "mute_tts": False, "keep_original": False},
            {"id": 2, "start": 2.5, "end": 5.0, "vi_text": "Đoạn 2", "mute_tts": False, "keep_original": False},
            {"id": 3, "start": 5.5, "end": 8.0, "vi_text": "Đoạn 3", "mute_tts": False, "keep_original": False},
        ]
    }
    seg_file.write_text(json.dumps(dummy_data, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        client = TestClient(app)

        # 1. Test batch update mute_tts và keep_original
        res = client.post(f"/api/jobs/{job_id}/segments/batch-update", json={
            "segments": [
                {"id": 1, "mute_tts": True},
                {"id": 2, "keep_original": True},
            ]
        })
        assert res.status_code == 200
        saved = json.loads(seg_file.read_text(encoding="utf-8"))
        assert saved["segments"][0]["mute_tts"] is True
        assert saved["segments"][1]["keep_original"] is True

        # 2. Test batch delete
        res_del = client.post(f"/api/jobs/{job_id}/segments/batch-delete", json={
            "seg_ids": [1, 3]
        })
        assert res_del.status_code == 200
        saved_del = json.loads(seg_file.read_text(encoding="utf-8"))
        assert len(saved_del["segments"]) == 1
        assert saved_del["segments"][0]["id"] == 2
    finally:
        if ws.exists():
            shutil.rmtree(ws, ignore_errors=True)

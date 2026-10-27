import pytest
from pathlib import Path
if not Path('ui').exists():
    pytest.skip('Legacy PyQt6 v1 UI tests skipped because ui/ was decommissioned in v2.0.0', allow_module_level=True)

"""Tests for Independent Original Audio Ranges and Minimal Context Menu (Mute Sub & Mute TTS)."""
import json
import shutil
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from dubstudio.subtitles.ass import get_segment_slices
from dubstudio.api.app import app
from dubstudio.config import AppConfig

client = TestClient(app)


def test_mute_sub_flag_preserves_text_but_omits_subtitles():
    """
    Khi mute_sub = True, vi_text vẫn được lưu giữ nhưng get_segment_slices trả về rỗng []
    để không hiển thị lên video. Khi mute_sub = False, phụ đề hiển thị bình thường.
    """
    seg = {
        "id": 1,
        "start": 1.0,
        "end": 4.0,
        "vi_text": "Đây là câu phụ đề thử nghiệm",
        "mute_sub": True,
    }
    # Tắt phụ đề -> không sinh slice
    slices_muted = get_segment_slices(seg)
    assert slices_muted == []

    # Bật lại phụ đề -> sinh slice bình thường
    seg["mute_sub"] = False
    slices_active = get_segment_slices(seg)
    assert len(slices_active) > 0
    assert slices_active[0]["text"] == "Đây là câu phụ đề thử nghiệm"


def test_orig_audio_ranges_api():
    """
    Kiểm tra API lưu và lấy danh sách các khoảng giữ âm thanh gốc độc lập (GET / POST /api/jobs/{id}/orig-ranges).
    """
    job_id = "test_job_orig_ranges"
    ws = Path("workspace") / job_id
    ws.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Ban đầu chưa có khoảng nào
        res_get1 = client.get(f"/api/jobs/{job_id}/orig-ranges")
        assert res_get1.status_code == 200
        assert res_get1.json()["ranges"] == []

        # 2. Lưu 2 khoảng giữ âm thanh gốc
        payload = {
            "ranges": [
                {"id": 1, "start": 10.5, "end": 25.0, "label": "Đoạn nhạc giữa"},
                {"id": 2, "start": 60.0, "end": 85.5, "label": "Đoạn hát kết"},
            ]
        }
        res_save = client.post(f"/api/jobs/{job_id}/orig-ranges", json=payload)
        assert res_save.status_code == 200
        assert res_save.json()["status"] == "saved"

        # 3. Đọc lại và kiểm tra file trên đĩa
        res_get2 = client.get(f"/api/jobs/{job_id}/orig-ranges")
        assert res_get2.status_code == 200
        ranges = res_get2.json()["ranges"]
        assert len(ranges) == 2
        assert ranges[0]["start"] == 10.5
        assert ranges[1]["end"] == 85.5

        # File orig_audio_ranges.json tồn tại trong workspace
        f = ws / "orig_audio_ranges.json"
        assert f.exists()
        saved_disk = json.loads(f.read_text(encoding="utf-8"))
        assert len(saved_disk) == 2
    finally:
        if ws.exists():
            shutil.rmtree(ws, ignore_errors=True)


def test_add_orig_range_dialog_defaults_and_5s():
    """Kiểm tra AddOrigRangeDialog mặc định lấy vị trí video làm start và +5s làm end."""
    import sys
    from PyQt6.QtWidgets import QApplication
    app_qt = QApplication.instance() or QApplication(sys.argv)

    from ui.pages.studio_page import AddOrigRangeDialog
    dlg = AddOrigRangeDialog(current_time=12.5, max_duration=120.0)

    # 1. Start = 12.5, End = 17.5 (+5s)
    st, en = dlg.get_range()
    assert abs(st - 12.5) < 0.01
    assert abs(en - 17.5) < 0.01

    # 2. Thay đổi start lên 20.0 -> end tự động nhảy thành 25.0 nếu end cũ < 20.0
    dlg._spn_start.setValue(20.0)
    st2, en2 = dlg.get_range()
    assert abs(st2 - 20.0) < 0.01
    assert abs(en2 - 25.0) < 0.01


def test_timeline_right_click_drag_creates_orig_range():
    """Kiểm tra TimelineCanvas phát tín hiệu orig_range_created khi kéo chuột phải trên Track 2."""
    import sys
    from PyQt6.QtCore import Qt, QPoint, QPointF
    from PyQt6.QtGui import QMouseEvent
    from PyQt6.QtWidgets import QApplication
    app_qt = QApplication.instance() or QApplication(sys.argv)

    from ui.widgets.timeline_ruler import TimelineWidget
    tw = TimelineWidget()
    tw.resize(800, 200)

    received_ranges = []
    tw.orig_range_created.connect(lambda st, en: received_ranges.append((st, en)))

    canvas = tw._canvas
    y2 = float(canvas._track_y(2) + 10)  # Point inside Track 2

    # 1. Nhấn chuột phải tại x=100
    p1 = QPointF(100.0, y2)
    ev_press = QMouseEvent(QMouseEvent.Type.MouseButtonPress, p1, Qt.MouseButton.RightButton, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier)
    canvas.mousePressEvent(ev_press)
    assert canvas._rb_creating_range is True

    # 2. Kéo chuột phải sang x=260
    p2 = QPointF(260.0, y2)
    ev_move = QMouseEvent(QMouseEvent.Type.MouseMove, p2, Qt.MouseButton.RightButton, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier)
    canvas.mouseMoveEvent(ev_move)
    assert canvas._rb_dragged is True

    # 3. Thả chuột phải -> phát tín hiệu orig_range_created
    ev_release = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, p2, Qt.MouseButton.RightButton, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier)
    canvas.mouseReleaseEvent(ev_release)

    assert len(received_ranges) == 1
    st, en = received_ranges[0]
    assert en > st
    assert abs((en - st) - ((260.0 - 100.0) / canvas._zoom)) < 0.1



def test_batch_update_mute_sub_api():
    """
    Kiểm tra batch-update hỗ trợ cập nhật cờ mute_sub độc lập cho từng câu.
    """
    job_id = "test_job_batch_mute_sub"
    ws = Path("workspace") / job_id
    ws.mkdir(parents=True, exist_ok=True)
    seg_file = ws / "segments.json"
    dummy_data = {
        "job_id": job_id,
        "segments": [
            {"id": 1, "start": 0.0, "end": 2.0, "vi_text": "Câu 1", "mute_sub": False, "mute_tts": False},
            {"id": 2, "start": 2.5, "end": 5.0, "vi_text": "Câu 2", "mute_sub": False, "mute_tts": False},
        ]
    }
    seg_file.write_text(json.dumps(dummy_data, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        res = client.post(f"/api/jobs/{job_id}/segments/batch-update", json={
            "segments": [
                {"id": 1, "mute_sub": True},
                {"id": 2, "mute_tts": True},
            ]
        })
        assert res.status_code == 200
        saved = json.loads(seg_file.read_text(encoding="utf-8"))
        assert saved["segments"][0]["mute_sub"] is True
        assert saved["segments"][0]["mute_tts"] is False
        assert saved["segments"][1]["mute_sub"] is False
        assert saved["segments"][1]["mute_tts"] is True
    finally:
        if ws.exists():
            shutil.rmtree(ws, ignore_errors=True)



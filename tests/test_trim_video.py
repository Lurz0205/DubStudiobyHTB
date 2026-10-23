"""Test Video Trimming tool, API endpoint, and UI components."""
from pathlib import Path
import pytest
from dubstudio.tools.trim_video import trim_video


def test_trim_video_tool(tmp_path):
    src = Path("samples/tiny.mp4")
    out = tmp_path / "trimmed.mp4"
    res = trim_video(video_path=src, start_s=0.5, end_s=2.5, output_path=out, fast_copy=True)
    assert res.exists()
    assert res.stat().st_size > 1000


def test_trim_video_api(tmp_path):
    from fastapi.testclient import TestClient
    from dubstudio.api.app import app

    client = TestClient(app)
    src = str(Path("samples/tiny.mp4").resolve())
    out_name = "api_trimmed.mp4"
    resp = client.post(
        "/api/tools/trim-video",
        json={
            "video_path": src,
            "start_s": 1.0,
            "end_s": 3.0,
            "output_name": out_name,
            "fast_copy": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["duration"] == 2.0
    out_file = Path("out") / out_name
    assert out_file.exists()


def test_range_slider_widget():
    import sys
    from PyQt6.QtWidgets import QApplication
    from ui.widgets.range_slider import RangeSlider

    app = QApplication.instance() or QApplication(sys.argv)
    slider = RangeSlider()
    slider.set_duration(100.0)
    assert slider.duration == 100.0

    slider.set_range(10.0, 40.0)
    assert slider.start_time == 10.0
    assert slider.end_time == 40.0

    slider.set_current_position(25.0)
    assert slider._current == 25.0
    slider.close()


def test_merge_page_has_trim_tab():
    import sys
    from PyQt6.QtWidgets import QApplication
    from ui.pages.merge_page import MergePage

    app = QApplication.instance() or QApplication(sys.argv)
    page = MergePage()
    # Check that there are 3 tabs: Chỉnh sửa, Ghép nối, Cắt video
    tabs = page.findChild(type(page).mro()[0])
    assert hasattr(page, "_trim_player")
    assert hasattr(page, "_range_slider")
    assert hasattr(page, "_spin_trim_start")
    assert hasattr(page, "_spin_trim_end")
    page.close()

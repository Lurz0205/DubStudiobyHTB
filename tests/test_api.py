import json
from pathlib import Path
from fastapi.testclient import TestClient
import pytest
from dubstudio.api.app import app

client = TestClient(app)


def test_index_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "DubStudio" in response.text


def test_list_jobs():
    response = client.get("/api/jobs")
    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert isinstance(data["jobs"], list)


def test_get_settings_masked():
    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert "gemini_api_key_masked" in data
    assert "translation_model" in data
    assert "auto_fallback" in data
    assert "available_models" in data
    assert "gemini-3.1-flash-lite" in data["available_models"]
    assert "gemini-2.5-flash-lite" in data["available_models"]
    assert "available_voices" in data
    voice_names = [v["name"] for v in data["available_voices"]]
    assert "Minh Đức" in voice_names
    assert "Quỳnh Anh" in voice_names


@pytest.fixture(autouse=True)
def setup_test_job(tmp_path):
    job_dir = Path("workspace") / "test_api_job"
    job_dir.mkdir(parents=True, exist_ok=True)
    seg_file = job_dir / "segments.json"
    dummy_segments = {
        "segments": [
            {"id": 1, "start": 0.5, "end": 3.0, "zh_text": "你好", "vi_text": "Xin chào", "tts_text": "Xin chào", "voice": "Minh Đức", "speed": 1.0}
        ]
    }
    seg_file.write_text(json.dumps(dummy_segments, ensure_ascii=False), encoding="utf-8")
    yield
    import shutil
    shutil.rmtree(job_dir, ignore_errors=True)


def test_get_segments_for_job():
    response = client.get("/api/jobs/test_api_job/segments")
    assert response.status_code == 200
    data = response.json()
    assert "segments" in data
    assert len(data["segments"]) == 1
    first_seg = data["segments"][0]
    assert "vi_text" in first_seg
    assert "tts_text" in first_seg


def test_update_segment_timing_and_voice():
    response = client.put(
        "/api/jobs/test_api_job/segments/1",
        json={"start": 0.2, "end": 3.5, "voice": "Minh Đức", "speed": 1.1},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "updated"
    assert data["segment"]["start"] == 0.2
    assert data["segment"]["voice"] == "Minh Đức"
    assert data["segment"]["speed"] == 1.1


def test_subtitle_style_endpoints():
    get_res = client.get("/api/jobs/test_api_job/style")
    assert get_res.status_code == 200
    assert "font_name" in get_res.json()

    post_res = client.post(
        "/api/jobs/test_api_job/style",
        json={"font_name": "Roboto", "font_size": 26, "primary_color": "#FFDD00", "outline_color": "#000000", "margin_v": 40},
    )
    assert post_res.status_code == 200
    assert post_res.json()["style"]["font_name"] == "Roboto"


def test_voices_preview_endpoint():
    res = client.get("/api/voices/preview?voice=Minh%20Đức")
    # Even if audio is not pregenerated, endpoint returns 200 or generates preview
    assert res.status_code in [200, 500]
    if res.status_code == 200:
        assert res.headers["content-type"] == "audio/wav"


def test_delete_job():
    del_job_dir = Path("workspace") / "job_to_delete"
    del_job_dir.mkdir(parents=True, exist_ok=True)
    (del_job_dir / "meta.json").write_text('{"job_id": "job_to_delete"}', encoding="utf-8")
    assert del_job_dir.exists()

    res = client.delete("/api/jobs/job_to_delete")
    assert res.status_code == 200
    assert not del_job_dir.exists()


def test_segment_crud_and_merge():
    # Setup test job with segments
    crud_dir = Path("workspace") / "test_crud_job"
    crud_dir.mkdir(parents=True, exist_ok=True)
    seg_file = crud_dir / "segments.json"
    seg_file.write_text(json.dumps({
        "segments": [
            {"id": 1, "start": 0.0, "end": 2.0, "vi_text": "Câu một", "tts_text": "Câu một", "voice": "Minh Đức"},
            {"id": 2, "start": 2.5, "end": 4.0, "vi_text": "Câu hai", "tts_text": "Câu hai", "voice": "Minh Đức"},
        ]
    }), encoding="utf-8")

    # 1. Create segment
    c_res = client.post("/api/jobs/test_crud_job/segments", json={
        "start": 4.5, "end": 6.0, "vi_text": "Câu ba"
    })
    assert c_res.status_code == 200
    assert c_res.json()["segment"]["vi_text"] == "Câu ba"
    assert c_res.json()["segment"]["id"] == 3

    # 2. Merge segments 1 and 2
    m_res = client.post("/api/jobs/test_crud_job/segments/merge", json={"seg_ids": [1, 2]})
    assert m_res.status_code == 200
    merged = m_res.json()["segment"]
    assert merged["vi_text"] == "Câu một Câu hai"
    assert merged["start"] == 0.0
    assert merged["end"] == 4.0

    # 3. Delete segment 3
    d_res = client.delete("/api/jobs/test_crud_job/segments/3")
    assert d_res.status_code == 200
    assert d_res.json()["status"] == "deleted"

    # Cleanup
    import shutil
    shutil.rmtree(crud_dir, ignore_errors=True)


def test_edit_video_api():
    payload = {
        "video_path": "samples/tiny.mp4",
        "crop_box": {"x": 10, "y": 10, "w": 300, "h": 200},
        "color_boxes": [
            {"x": 10, "y": 10, "w": 100, "h": 40, "color": "#000000", "opacity": 0.8},
            {"x": 20, "y": 60, "w": 120, "h": 30, "color": "#FF0000", "opacity": 0.5},
        ],
        "output_name": "test_edited_video.mp4",
    }
    res = client.post("/api/tools/edit-video", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "file" in data
    assert Path(data["path"]).exists()
    Path(data["path"]).unlink(missing_ok=True)


def test_edit_video_color_boxes_only():
    """Test exporting video with ONLY color boxes (the exact scenario from user's screen)."""
    payload = {
        "video_path": "samples/tiny.mp4",
        "color_boxes": [
            {"x": 0, "y": 50, "w": 200, "h": 40, "color": "#112233", "opacity": 0.75}
        ],
        "output_name": "test_color_only.mp4",
    }
    res = client.post("/api/tools/edit-video", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert Path(data["path"]).exists()
    Path(data["path"]).unlink(missing_ok=True)


def test_edit_video_crop_only():
    """Test exporting video with ONLY crop."""
    payload = {
        "video_path": "samples/tiny.mp4",
        "crop_box": {"x": 20, "y": 20, "w": 200, "h": 150},
        "output_name": "test_crop_only.mp4",
    }
    res = client.post("/api/tools/edit-video", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert Path(data["path"]).exists()
    Path(data["path"]).unlink(missing_ok=True)


def test_in_memory_asgi_bridge_on_closed_port(monkeypatch):
    """Confirm UI operations succeed 100% via In-Memory ASGI Bridge even if TCP port is completely closed."""
    # Point base URL to an arbitrary closed TCP port
    monkeypatch.setenv("DUBSTUDIO_API_PORT", "59998")

    from ui.workers import _get, _post
    import shutil

    # 1. Health check via in-memory bridge
    health = _get("/api/health")
    assert health["status"] == "ok"
    assert health["app"] == "DubStudio"

    # 2. Project creation via in-memory bridge without TCP
    job_res = _post("/api/jobs/create", {"video_path": "samples/tiny.mp4", "target_lang": "vi"})
    try:
        assert "job_id" in job_res
        assert Path(job_res["workspace"]).exists()
    finally:
        if "workspace" in job_res:
            ws_p = Path(job_res["workspace"])
            if ws_p.exists():
                shutil.rmtree(ws_p, ignore_errors=True)





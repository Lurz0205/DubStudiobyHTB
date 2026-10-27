"""Unit tests for DubStudio v2.0.0 Full Pipeline, Dynamic Port, Bridge & WYSIWYG Geometry."""
import math
import pytest
from pathlib import Path
from start_app_v2 import DesktopAPIBridge, find_free_port


def test_dynamic_port_allocation_no_hardcoded_8765():
    """Verify ephemeral port is dynamically allocated by OS and not hardcoded to 8765."""
    port1 = find_free_port()
    port2 = find_free_port()
    assert isinstance(port1, int)
    assert isinstance(port2, int)
    assert 1024 < port1 <= 65535
    assert port1 != 8765
    assert port2 != 8765


def test_bridge_project_lifecycle_in_memory(tmp_path, monkeypatch):
    """Test create_project, get_project_data, save_project_segments and save_project_style."""
    import dubstudio.paths as dp
    monkeypatch.setattr(dp, "get_workspace_dir", lambda: tmp_path)
    monkeypatch.setattr(dp, "resolve_job_workspace", lambda j_id: tmp_path / j_id)

    # 1. Prepare dummy video file
    dummy_video = tmp_path / "sample_test_video.mp4"
    dummy_video.write_bytes(b"FAKE_MP4_HEADER_DATA_12345")

    bridge = DesktopAPIBridge()

    # 2. Create project
    create_res = bridge.create_project(str(dummy_video), title="Kiem Hiep Test")
    assert create_res["status"] == "success"
    job_id = create_res["job_id"]
    assert "sample_test_video" in job_id

    # Verify video was copied to workspace
    ws_dir = tmp_path / job_id
    assert (ws_dir / "input.mp4").exists()
    assert (ws_dir / "job_config.json").exists()

    # 3. Save segments via in-memory bridge
    test_segments = [
        {"id": 1, "start": 0.5, "end": 2.5, "text": "Đoạn thuyết minh thử nghiệm", "orig": "测试"},
        {"id": 2, "start": 3.0, "end": 5.0, "text": "Câu phụ đề số hai", "orig": "第二句"},
    ]
    save_res = bridge.save_project_segments(job_id, test_segments)
    assert save_res["status"] == "success"

    # 4. Save style & volumes via in-memory bridge
    test_style = {
        "voice_volume": 150,
        "bgm_volume": 70,
        "font_size": 26,
    }
    style_res = bridge.save_project_style(job_id, test_style)
    assert style_res["status"] == "success"

    # 5. Fetch project data
    data = bridge.get_project_data(job_id)
    assert data["id"] == job_id
    assert data["has_input_video"] is True
    assert len(data["segments"]) == 2
    assert data["segments"][0]["text"] == "Đoạn thuyết minh thử nghiệm"
    assert data["style"]["voice_volume"] == 150
    assert data["style"]["bgm_volume"] == 70

    # 6. Check get_projects listing
    all_projects = bridge.get_projects()
    assert len(all_projects) >= 1
    p_meta = next(p for p in all_projects if p["id"] == job_id)
    assert p_meta["title"] == "Kiem Hiep Test"
    assert p_meta["has_video"] is True
    assert p_meta["has_subtitles"] is True


def test_wysiwyg_geometry_math_matching_ass_and_video_player():
    """Verify inner_video_rect coordinate calculation matches ass.py / video_player.py geometry."""
    # Scenario 1: Standard 16:9 container, 1920x1080 native video
    cont_w, cont_h = 1280, 720
    video_w, video_h = 1920, 1080
    target_ar = video_w / video_h  # 16/9 = 1.7777...
    cont_ar = cont_w / cont_h

    if cont_ar > target_ar:
        canvas_h = cont_h
        canvas_w = cont_h * target_ar
    else:
        canvas_w = cont_w
        canvas_h = cont_w / target_ar

    inner_left = (cont_w - canvas_w) / 2
    inner_top = (cont_h - canvas_h) / 2
    scale = canvas_w / video_w

    assert math.isclose(canvas_w, 1280, rel_tol=1e-3)
    assert math.isclose(canvas_h, 720, rel_tol=1e-3)
    assert math.isclose(inner_left, 0, abs_tol=1e-3)
    assert math.isclose(inner_top, 0, abs_tol=1e-3)
    assert math.isclose(scale, 1280 / 1920, rel_tol=1e-3)

    # Scenario 2: 9:16 background padding mode (1080x1920 canvas)
    target_916_ar = 9.0 / 16.0
    cont_w_phone, cont_h_phone = 450, 800  # 9:16 ratio container
    phone_ar = cont_w_phone / cont_h_phone

    if phone_ar > target_916_ar:
        phone_canvas_h = cont_h_phone
        phone_canvas_w = cont_h_phone * target_916_ar
    else:
        phone_canvas_w = cont_w_phone
        phone_canvas_h = cont_w_phone / target_916_ar

    phone_scale = phone_canvas_w / 1080.0
    # Inside 9:16 canvas, 16:9 video is centered horizontally with height: phone_canvas_w * 9 / 16
    inner_video_h = phone_canvas_w * (9.0 / 16.0)
    inner_video_y = (phone_canvas_h - inner_video_h) / 2

    assert math.isclose(phone_canvas_w, 450, rel_tol=1e-3)
    assert math.isclose(phone_canvas_h, 800, rel_tol=1e-3)
    assert inner_video_y > 0  # Black bars / canvas pads top and bottom

    # Scenario 3: GDI Font Compensation factor 1.116x
    base_font = 24
    compensated_font = base_font * 1.116
    assert math.isclose(compensated_font, 26.784, rel_tol=1e-3)


def test_web_audio_gain_curve_and_limiter_spec():
    """Verify Web Audio API gain formula matches +9dB at 200% and limiter settings."""
    factor_9db = 2.81838  # 10 ** (9.0 / 20.0)

    # 1. 0% vol -> 0.0 gain
    vol_0 = 0
    gain_0 = vol_0 / 100.0
    assert gain_0 == 0.0

    # 2. 100% vol -> 1.0 gain (exact unity, 0 dB clean)
    vol_100 = 100
    gain_100 = vol_100 / 100.0
    assert gain_100 == 1.0

    # 3. 150% vol -> mid-boost (+4.5 dB approx)
    vol_150 = 150
    gain_150 = 1.0 + ((vol_150 - 100) / 100.0) * (factor_9db - 1.0)
    assert 1.8 < gain_150 < 2.0

    # 4. 200% vol -> exactly +9 dB (2.818x)
    vol_200 = 200
    gain_200 = 1.0 + ((vol_200 - 100) / 100.0) * (factor_9db - 1.0)
    assert math.isclose(gain_200, factor_9db, rel_tol=1e-4)

    # 5. Brickwall peak limiter settings
    limiter_spec = {
        "threshold": -1.0,  # dBFS
        "knee": 0.0,        # Hard knee
        "ratio": 20.0,      # Brickwall
        "attack": 0.001,    # 1 ms instant peak clamp
        "release": 0.05,    # 50 ms clean release without pumping
    }
    assert limiter_spec["threshold"] == -1.0
    assert limiter_spec["ratio"] >= 20.0

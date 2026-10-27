import os
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from dubstudio.api.app import app
from dubstudio.paths import get_out_dir, resolve_job_workspace

client = TestClient(app)


def test_settings_out_dir_integration(tmp_path, monkeypatch):
    """Verify that DUBSTUDIO_OUT_DIR changes get_out_dir correctly."""
    custom_out = tmp_path / "custom_out"
    custom_out.mkdir()
    monkeypatch.setenv("DUBSTUDIO_OUT_DIR", str(custom_out))
    assert get_out_dir() == custom_out.resolve()


def test_api_settings_out_dir(tmp_path, monkeypatch):
    """Test get and update out_dir via settings API without polluting real .env."""
    custom_out = tmp_path / "api_custom_out"
    custom_out.mkdir()
    fake_env = tmp_path / ".env"
    monkeypatch.setattr("dubstudio.paths.get_env_file", lambda: fake_env)
    monkeypatch.delenv("DUBSTUDIO_OUT_DIR", raising=False)

    res = client.post("/api/settings", json={"out_dir": str(custom_out)})
    assert res.status_code == 200

    res_get = client.get("/api/settings")
    assert res_get.status_code == 200
    data = res_get.json()
    assert Path(data["out_dir"]).resolve() == custom_out.resolve()


def test_auto_split_unit_cues_force():
    """Verify that auto_split_all_units with target_n splits segments properly."""
    from dubstudio.subtitles.cue_split import auto_split_all_units

    sample_segments = [
        {
            "id": 1,
            "start": 0.0,
            "end": 6.0,
            "vi_text": "Hôm nay tôi sẽ hướng dẫn các bạn cách làm món ăn này thật ngon",
        }
    ]
    # Split with target_n=5
    res5 = auto_split_all_units(sample_segments, target_n=5, force=True)
    cues5 = res5[0].get("cues", [])
    assert len(cues5) >= 2

    # Split with target_n=9
    res9 = auto_split_all_units(sample_segments, target_n=9, force=True)
    cues9 = res9[0].get("cues", [])
    assert len(cues9) >= 1


def test_render_with_overlays_no_has_voice_error(tmp_path):
    """Verify render.run constructs overlay pipeline and executes without 'has_voice' NameError."""
    from unittest.mock import MagicMock, patch
    from dubstudio.jobstate import JobContext
    from dubstudio.config import AppConfig

    job = JobContext(workspace_path=tmp_path, job_id="test_render_overlays")
    cfg = AppConfig()

    (tmp_path / "segments.json").write_text(
        json.dumps({"segments": [{"id": 1, "start": 0, "end": 1, "text": "test"}]}),
        encoding="utf-8"
    )
    (tmp_path / "style.json").write_text(
        json.dumps({
            "color_boxes": [{"x": 10, "y": 10, "w": 100, "h": 50, "color": "#000000", "enabled": True}]
        }),
        encoding="utf-8"
    )
    dummy_vid = tmp_path / "input.mp4"
    dummy_vid.write_bytes(b"000")

    with patch("dubstudio.packaging.safe_subprocess_run") as mock_run, \
         patch("dubstudio.ffmpeg_utils.probe_file") as mock_probe, \
         patch("dubstudio.subtitles.ass.generate_ass_subtitles") as mock_ass:
        mock_probe.return_value = {"streams": [{"codec_type": "video", "width": 1920, "height": 1080}]}
        def fake_ass(segs, out_file, **kw):
            out_file.write_text("[Script Info]", encoding="utf-8")
        mock_ass.side_effect = fake_ass
        mock_run.return_value = MagicMock(returncode=0)

        from dubstudio.stages.render import run
        run(job, cfg, input_video=dummy_vid, force=True)
        assert mock_run.called
        call_cmd = mock_run.call_args[0][0]
        assert any("overlay" in arg for arg in call_cmd)

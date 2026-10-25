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

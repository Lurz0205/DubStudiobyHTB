"""Tests for GeminiTranslator cascade fallback and resume logic."""
import pytest
from dubstudio.config import AppConfig
from dubstudio.llm.gemini import GeminiTranslator


def test_cascade_candidates_builder(tmp_path):
    cfg = AppConfig(
        gemini_api_key="AIzaFakeKey123",
        translation={
            "model": "gemini-2.5-flash",
            "fallback_models": ["gemini-2.5-flash-lite", "gemini-2.0-flash"],
            "auto_fallback": True,
            "backup_gemini_api_key": "AIzaBackupKey456",
            "openrouter_api_key": "sk-or-fake",
            "openrouter_model": "google/gemini-2.0-flash-exp:free",
        }
    )
    translator = GeminiTranslator(cfg=cfg, cache_dir=tmp_path)
    cascade = translator._build_cascade()

    assert len(cascade) >= 4
    # First candidate is primary model
    assert cascade[0]["model"] == "gemini-2.5-flash"
    assert cascade[0]["key"] == "AIzaFakeKey123"

    # Backup key candidate
    assert any(c["key"] == "AIzaBackupKey456" for c in cascade)

    # Fallback models included
    models_in_cascade = [c["model"] for c in cascade]
    assert "gemini-2.5-flash-lite" in models_in_cascade
    assert "google/gemini-2.0-flash-exp:free" in models_in_cascade


def test_skip_already_translated_segments(tmp_path):
    cfg = AppConfig(
        gemini_api_key="AIzaFakeKey123",
        translation={"model": "gemini-2.5-flash", "auto_fallback": True}
    )
    translator = GeminiTranslator(cfg=cfg, cache_dir=tmp_path)

    # Segments where all are already translated
    segments = [
        {"id": 1, "zh": "你好", "vi_text": "Xin chào", "tts_text": "Xin chào"},
        {"id": 2, "zh": "谢谢", "vi_text": "Cảm ơn", "tts_text": "Cảm ơn"},
    ]

    res = translator.translate_segments(segments)
    # Should return directly without making any network calls
    assert len(res) == 2
    assert res[0]["vi_text"] == "Xin chào"
    assert res[1]["vi_text"] == "Cảm ơn"


def test_build_prompt_single_sentence_has_surrounding_context():
    from dubstudio.llm.gemini import build_prompt

    # 11 units in video
    all_units = [
        {"id": i, "zh": f"第{i}句话", "vi_text": f"Câu số {i}."}
        for i in range(1, 12)
    ]

    # Translate only unit 6
    target = [all_units[5]] # id=6
    inst, _ = build_prompt(
        batch_units=target,
        all_units=all_units,
        context={"summary": "Tóm tắt"},
        task_type="translate",
    )

    # Must contain 5 units before (#1 to #5)
    for i in range(1, 6):
        assert f"#{i}: Câu số {i}." in inst

    # Must contain 5 units after (#7 to #11)
    for i in range(7, 12):
        assert f"#{i} (ZH): 第{i}句话" in inst

    # Test edge case: Unit 1 (first sentence) with 0 prev units -> must take 5 following units
    target_u1 = [all_units[0]] # id=1
    inst_u1, _ = build_prompt(
        batch_units=target_u1,
        all_units=all_units,
        context={"summary": "Tóm tắt"},
        task_type="translate",
    )
    for i in range(2, 7):
        assert f"#{i} (ZH): 第{i}句话" in inst_u1


def test_default_project_name_date_format_and_suffix(tmp_path, monkeypatch):
    import time
    from dubstudio.config import AppConfig
    from dubstudio.api.app import create_job, CreateJobRequest

    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()

    cfg = AppConfig()
    cfg.general.workspace_dir = ws_dir
    monkeypatch.setattr(AppConfig, "load", lambda: cfg)

    # Fake input video
    dummy_video = tmp_path / "sample_video.mp4"
    dummy_video.write_bytes(b"dummy")

    today_str = time.strftime("%d%m%Y")

    # 1. First job created without project_name -> should be today_str (e.g. 18102026)
    req1 = CreateJobRequest(video_path=str(dummy_video), project_name="")
    # Monkeypatch ingest.run to avoid calling ffmpeg on dummy video
    import dubstudio.stages.ingest as ingest
    monkeypatch.setattr(ingest, "run", lambda job, cfg, vid: None)

    res1 = create_job(req1)
    assert res1["job_id"] == today_str
    assert res1["video_name"] == today_str

    # 2. Second job created on same day without project_name -> should be today_str_1
    req2 = CreateJobRequest(video_path=str(dummy_video), project_name="")
    res2 = create_job(req2)
    assert res2["job_id"] == f"{today_str}_1"
    assert res2["video_name"] == f"{today_str}_1"

    # 3. Third job created on same day without project_name -> should be today_str_2
    req3 = CreateJobRequest(video_path=str(dummy_video), project_name="")
    res3 = create_job(req3)
    assert res3["job_id"] == f"{today_str}_2"
    assert res3["video_name"] == f"{today_str}_2"


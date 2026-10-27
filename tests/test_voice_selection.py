import json
from pathlib import Path
from dubstudio.config import AppConfig
from dubstudio.jobstate import JobContext
from dubstudio.stages import voice_assign
from dubstudio.tts.base import MALE_VOICES, FEMALE_VOICES, get_voice_gender


def test_voice_gender_helper():
    assert get_voice_gender("Thùy Dung") == "female"
    assert get_voice_gender("Trúc Ly") == "female"
    assert get_voice_gender("Minh Đức") == "male"
    assert get_voice_gender("Hải Đăng") == "male"


def test_voice_assign_single_choice_female(tmp_path):
    ws = tmp_path / "workspace" / "job_female"
    ws.mkdir(parents=True)
    job = JobContext(workspace_path=ws, job_id="job_female", input_path=tmp_path / "in.mp4")
    cfg = AppConfig.load()

    # Initial segments with male voice
    seg_data = {
        "segments": [
            {"id": 1, "start": 0.0, "end": 2.0, "vi_text": "Xin chào bạn", "voice": "Minh Đức", "gender": "male"},
            {"id": 2, "start": 2.5, "end": 4.0, "vi_text": "Hôm nay thế nào", "voice": "Minh Đức", "gender": "male"},
        ]
    }
    (ws / "segments.json").write_text(json.dumps(seg_data, ensure_ascii=False), encoding="utf-8")
    (ws / "job_config.json").write_text(
        json.dumps({
            "detect_gender": False,
            "single_voice_gender": "female",
            "default_female_voice": "Trúc Ly",
            "default_male_voice": "Minh Đức",
        }, ensure_ascii=False),
        encoding="utf-8"
    )

    voice_assign.run(job, cfg)

    updated_data = json.loads((ws / "segments.json").read_text(encoding="utf-8"))
    for s in updated_data["segments"]:
        assert s["voice"] == "Trúc Ly"
        assert s["gender"] == "female"


def test_tts_enforces_female_voice_when_single_female():
    from dubstudio.tts.base import MALE_VOICES, FEMALE_VOICES
    detect_gender = False
    single_choice = "female"
    fallback_single_voice = "Trúc Ly"

    segments = [
        {"id": 1, "voice": "Minh Đức", "gender": "male"},
        {"id": 2, "voice": None, "gender": None},
        {"id": 3, "voice": "Thùy Dung", "gender": "female"},
    ]

    for s in segments:
        v_choice = s.get("voice")
        if not detect_gender:
            if (
                not v_choice
                or (single_choice == "female" and v_choice in MALE_VOICES)
                or (single_choice == "male" and v_choice in FEMALE_VOICES)
            ):
                v_choice = fallback_single_voice
        s["voice"] = v_choice

    # All segments must be female voices
    assert segments[0]["voice"] == "Trúc Ly"
    assert segments[1]["voice"] == "Trúc Ly"
    assert segments[2]["voice"] == "Thùy Dung"


def test_voice_assign_single_voice_override(tmp_path):
    ws = tmp_path / "workspace" / "job_custom"
    ws.mkdir(parents=True)
    job = JobContext(workspace_path=ws, job_id="job_custom", input_path=tmp_path / "in.mp4")
    cfg = AppConfig.load()

    seg_data = {
        "segments": [
            {"id": 1, "start": 0.0, "end": 2.0, "vi_text": "Xin chào", "voice": "Minh Đức", "gender": "male"},
            {"id": 2, "start": 2.5, "end": 4.0, "vi_text": "Câu riêng", "voice": "Trúc Ly", "gender": "female", "user_edited_voice": True},
        ]
    }
    (ws / "segments.json").write_text(json.dumps(seg_data, ensure_ascii=False), encoding="utf-8")
    (ws / "job_config.json").write_text(
        json.dumps({
            "detect_gender": False,
            "single_voice": "Adam",
        }, ensure_ascii=False),
        encoding="utf-8"
    )

    voice_assign.run(job, cfg)

    updated_data = json.loads((ws / "segments.json").read_text(encoding="utf-8"))
    assert updated_data["segments"][0]["voice"] == "Adam"
    # User edited voice on segment 2 must remain untouched
    assert updated_data["segments"][1]["voice"] == "Trúc Ly"


"""Unit test for separation stage with BS-RoFormer."""
from pathlib import Path
import pytest
from dubstudio.config import AppConfig
from dubstudio.jobstate import JobContext, compute_file_hash
from dubstudio.stages import separate


def test_separate_skip_when_already_done(tmp_path: Path):
    ws = tmp_path / "test_job"
    ws.mkdir(parents=True)
    audio_dir = ws / "audio"
    audio_dir.mkdir(parents=True)

    input_audio = ws / "input.wav"
    input_audio.write_bytes(b"RIFF" + b"\x00" * 2000)

    vocals = audio_dir / "vocals.wav"
    bgm = audio_dir / "bgm.wav"
    vocals.write_bytes(b"RIFF" + b"\x00" * 2000)
    bgm.write_bytes(b"RIFF" + b"\x00" * 2000)

    job = JobContext(workspace_path=ws, job_id="test_job", input_path=input_audio)
    cfg = AppConfig.load()

    # When outputs exist and are valid size, run should skip gracefully without spawning subprocess
    separate.run(job, cfg, input_audio)
    input_hash = compute_file_hash(input_audio)
    assert job.is_stage_done("separate", input_hash)

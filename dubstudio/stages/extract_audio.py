"""Stage: extract_audio. Converts audio track to 16kHz mono WAV."""
from pathlib import Path
from dubstudio.config import AppConfig
from dubstudio.events import emit_event
from dubstudio.ffmpeg_utils import extract_audio
from dubstudio.jobstate import JobContext, compute_file_hash


def run(job: JobContext, cfg: AppConfig, input_path: Path) -> None:
    """Execute the extract_audio stage."""
    stage_name = "extract_audio"
    emit_event(stage_name, 0.0, "Bắt đầu trích xuất âm thanh từ video")

    input_hash = compute_file_hash(input_path)
    if job.is_stage_done(stage_name, input_hash):
        emit_event(stage_name, 100.0, "skipped (up to date)")
        return

    job.start_stage(stage_name, input_hash)

    output_audio = job.workspace / "audio" / "orig.wav"
    extract_audio(
        input_path=input_path,
        output_path=output_audio,
        sample_rate=cfg.audio.sample_rate,
        channels=cfg.audio.channels,
    )

    emit_event(stage_name, 100.0, "Trích xuất âm thanh 44.1kHz stereo hoàn tất")
    job.finish_stage(stage_name, ["audio/orig.wav"])

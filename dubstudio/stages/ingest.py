"""Stage: ingest. Copies/links input file and probes media parameters."""
import json
from pathlib import Path
import shutil
from dubstudio.config import AppConfig
from dubstudio.events import emit_event
from dubstudio.ffmpeg_utils import probe_file
from dubstudio.jobstate import JobContext, compute_file_hash


def run(job: JobContext, cfg: AppConfig, input_path: Path) -> None:
    """Execute the ingest stage."""
    stage_name = "ingest"
    emit_event(stage_name, 0.0, "Bắt đầu tiếp nhận và kiểm tra video đầu vào")

    input_hash = compute_file_hash(input_path)
    if job.is_stage_done(stage_name, input_hash):
        emit_event(stage_name, 100.0, "Giai đoạn ingest đã hoàn thành trước đó (bỏ qua)")
        return

    job.start_stage(stage_name, input_hash)

    # Ingest: copy/link input video to workspace
    target_video = job.workspace / f"input{input_path.suffix}"
    if not target_video.exists() or compute_file_hash(target_video) != input_hash:
        shutil.copy2(input_path, target_video)

    # Probe media info
    probe_data = probe_file(target_video)
    probe_output = job.workspace / "probe.json"
    with open(probe_output, "w", encoding="utf-8") as f:
        json.dump(probe_data, f, ensure_ascii=False, indent=2)

    emit_event(stage_name, 100.0, "Kiểm tra thông số video hoàn tất")
    job.finish_stage(stage_name, [target_video.name, probe_output.name])

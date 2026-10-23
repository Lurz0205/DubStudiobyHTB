"""Stage: render. Produces final dubbed MP4 video and Vietnamese SRT subtitles."""
import json
from pathlib import Path
import subprocess
from dubstudio.config import AppConfig
from dubstudio.errors import DubError
from dubstudio.events import emit_event
from dubstudio.jobstate import JobContext, compute_file_hash


def format_srt_time(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def generate_srt(segments_file: Path, srt_path: Path) -> None:
    """Generate Vietnamese SRT subtitle file with proportional 10-15 word display slices."""
    from dubstudio.subtitles.ass import get_segment_slices
    with open(segments_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    srt_idx = 1
    with open(srt_path, "w", encoding="utf-8") as f:
        for seg in data.get("segments", []):
            slices = get_segment_slices(seg)
            for sl in slices:
                start_str = format_srt_time(sl["start"])
                end_str = format_srt_time(sl["end"])
                f.write(f"{srt_idx}\n{start_str} --> {end_str}\n{sl['text']}\n\n")
                srt_idx += 1


def run(job: JobContext, cfg: AppConfig, input_video: Path, force: bool = False) -> None:
    stage_name = "render"
    emit_event(stage_name, 0.0, "Bắt đầu xuất video lồng tiếng thành phẩm")

    voice_track = job.workspace / "voice_track.wav"
    style_file = job.workspace / "style.json"
    segments_file = job.workspace / "segments.json"
    mix_settings_file = job.workspace / "mix_settings.json"

    # Compute combined hash of voice_track + style.json + segments.json + mix_settings.json so changes to subtitles/style/audio always re-render
    import hashlib
    h = hashlib.sha256()
    if voice_track.exists():
        h.update(voice_track.read_bytes())
    if style_file.exists():
        h.update(style_file.read_bytes())
    if segments_file.exists():
        h.update(segments_file.read_bytes())
    if mix_settings_file.exists():
        h.update(mix_settings_file.read_bytes())
    input_hash = h.hexdigest()[:16]

    if not force and job.is_stage_done(stage_name, input_hash):
        emit_event(stage_name, 100.0, "Giai đoạn render đã hoàn thành (bỏ qua)")
        return

    job.start_stage(stage_name, input_hash)

    out_dir = cfg.general.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    base_name = job.job_id
    final_video = out_dir / f"{base_name}_vi.mp4"
    final_srt = out_dir / f"{base_name}_vi.srt"

    # 1. Sinh phụ đề SRT và ASS
    segments_file = job.workspace / "segments.json"
    generate_srt(segments_file, final_srt)

    final_ass = out_dir / f"{base_name}_vi.ass"
    from dubstudio.subtitles.ass import generate_ass_subtitles
    from dubstudio.ffmpeg_utils import probe_file
    with open(segments_file, "r", encoding="utf-8") as f:
        seg_items = json.load(f).get("segments", [])

    # Load custom subtitle styling from style.json or global preset
    style_data = None
    preset_file = Path("config") / "subtitle_preset.json"
    if style_file.exists():
        try:
            style_data = json.loads(style_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    elif preset_file.exists():
        try:
            style_data = json.loads(preset_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Probe actual video dimensions to ensure 1:1 pixel coordinate matching in ASS
    vid_w = 1280
    vid_h = 720
    try:
        info = probe_file(input_video)
        for s in info.get("streams", []):
            if s.get("codec_type") == "video":
                vid_w = int(s.get("width") or 1280)
                vid_h = int(s.get("height") or 720)
                break
    except Exception:
        pass

    generate_ass_subtitles(
        seg_items,
        final_ass,
        style=style_data,
        video_width=vid_w,
        video_height=vid_h,
    )

    # Copy ASS into workspace with relative name to avoid Windows C:\ escape bugs (AGENTS.md Section 8)
    local_ass = job.workspace / "subtitles.ass"
    local_ass.write_text(final_ass.read_text(encoding="utf-8"), encoding="utf-8")

    # 2. Render video: thay thế audio gốc bằng voice_track.wav và nhúng cứng (hard-sub) phụ đề ASS
    # Using relative path for subtitles filter executed with cwd=job.workspace to avoid Windows C:\ escape bugs (AGENTS.md Section 8)
    # Prioritize GPU hardware encoders: NVENC -> Intel QuickSync (h264_qsv) -> Windows MediaFoundation (h264_mf) -> CPU (libx264)
    encoders_to_try = [cfg.render.encoder, "h264_qsv", "h264_mf", cfg.render.fallback_encoder]
    # Deduplicate while preserving order
    encoders_to_try = list(dict.fromkeys(encoders_to_try))

    last_error_tail = ""
    for encoder in encoders_to_try:
        if encoder == "h264_nvenc":
            # Maximum-quality NVENC with two-pass fullres, VBR, and Adaptive Quantization
            target_cq = str(min(18, cfg.render.crf))
            rate_args = [
                "-preset", "p7",
                "-tune", "hq",
                "-rc:v", "vbr",
                "-cq", target_cq,
                "-b:v", "0",
                "-maxrate", "35M",
                "-bufsize", "60M",
                "-spatial-aq", "1",
                "-temporal-aq", "1",
                "-rc-lookahead", "32",
                "-multipass", "fullres",
                "-pix_fmt", "yuv420p",
            ]
        elif encoder == "h264_qsv":
            # Intel QuickSync hardware GPU encoder: fast, pristine quality, 0% CPU strain
            rate_args = [
                "-global_quality", str(min(18, cfg.render.crf)),
                "-look_ahead", "1",
            ]
        elif encoder == "h264_mf":
            # Windows MediaFoundation GPU hardware encoder with high bitrate for razor-sharp quality
            rate_args = [
                "-b:v", "18M",
                "-maxrate", "28M",
                "-bufsize", "36M",
                "-pix_fmt", "yuv420p",
            ]
        else:
            # High quality CPU fallback (libx264)
            rate_args = [
                "-preset", "slow",
                "-crf", str(min(18, cfg.render.crf)),
                "-pix_fmt", "yuv420p",
            ]

        has_voice = voice_track.exists() and voice_track.stat().st_size > 500
        from dubstudio.paths import resolve_tool
        from dubstudio.packaging import get_subprocess_env, safe_subprocess_run
        cmd = [
            resolve_tool("ffmpeg"), "-y",
            "-i", str(input_video.resolve()),
        ]
        if has_voice:
            cmd.extend(["-i", str(voice_track.resolve())])

        cmd.extend([
            "-vf", "subtitles=subtitles.ass",
            "-map", "0:v:0",
            "-map", "1:a:0" if has_voice else "0:a:0?",
            "-c:v", encoder,
            *rate_args,
            "-c:a", "aac",
            "-b:a", "256k",
            "-ar", "48000",
            "-ac", "2",
            str(final_video.resolve()),
        ])

        emit_event(stage_name, 50.0, f"Đang kết xuất video và khắc phụ đề ASS ({encoder})...")

        proc = safe_subprocess_run(
            cmd,
            cwd=str(job.workspace.resolve()),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            env=get_subprocess_env(),
        )

        if proc.returncode == 0:
            break
        else:
            last_error_tail = "\n".join(proc.stderr.splitlines()[-10:])
    else:
        raise DubError(
            code="RENDER_FAILED",
            user_message_vi="Lỗi khi xuất video thành phẩm.",
            hint_vi="Kiểm tra lại không gian đĩa trống hoặc codec video đầu vào.",
            details={"stderr": last_error_tail},
        )

    emit_event(stage_name, 100.0, f"Xuất video thành công: {final_video.name}")
    job.finish_stage(stage_name, [str(final_video), str(final_srt)])

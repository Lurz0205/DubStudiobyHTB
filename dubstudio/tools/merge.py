"""Tool for merging / concatenating multiple video files with stream-copy or re-encode."""
import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dubstudio.errors import DubError
from dubstudio.events import emit_event
from dubstudio.ffmpeg_utils import probe_file, run_command


def extract_media_profile(probe_info: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Extract primary video and audio stream profiles from ffprobe output."""
    streams = probe_info.get("streams", [])
    video_profile: Dict[str, Any] = {}
    audio_profile: Dict[str, Any] = {}

    for s in streams:
        c_type = s.get("codec_type")
        if c_type == "video" and not video_profile:
            video_profile = {
                "codec": s.get("codec_name"),
                "width": s.get("width"),
                "height": s.get("height"),
                "r_frame_rate": s.get("r_frame_rate"),
            }
        elif c_type == "audio" and not audio_profile:
            audio_profile = {
                "codec": s.get("codec_name"),
                "sample_rate": s.get("sample_rate"),
                "channels": s.get("channels"),
            }

    return video_profile, audio_profile


def can_stream_copy(profiles: List[Tuple[Dict[str, Any], Dict[str, Any]]]) -> bool:
    """Return True if all media files share identical video/audio codecs and parameters."""
    if not profiles or len(profiles) < 2:
        return True

    base_v, base_a = profiles[0]
    if not base_v:
        return False

    for v, a in profiles[1:]:
        if v.get("codec") != base_v.get("codec"):
            return False
        if v.get("width") != base_v.get("width") or v.get("height") != base_v.get("height"):
            return False
        if bool(a) != bool(base_a):
            return False
        if a and base_a:
            if a.get("codec") != base_a.get("codec"):
                return False
            if a.get("sample_rate") != base_a.get("sample_rate"):
                return False
            if a.get("channels") != base_a.get("channels"):
                return False
    return True


def merge_videos(
    video_paths: List[Path],
    output_path: Path,
    force_reencode: bool = False,
    nvenc: bool = True,
) -> Path:
    """Merge multiple video clips into one.

    Uses stream-copy if all clips share compatible codecs/resolution,
    otherwise re-encodes to a unified format.
    """
    if len(video_paths) < 2:
        raise DubError(
            code="MERGE_NOT_ENOUGH_FILES",
            user_message_vi="Cần ít nhất 2 video để ghép nối.",
            hint_vi="Vui lòng cung cấp từ 2 tệp video trở lên.",
            details={"count": len(video_paths)},
        )

    for p in video_paths:
        if not p.exists():
            raise DubError(
                code="MERGE_FILE_NOT_FOUND",
                user_message_vi=f"Không tìm thấy tệp video để ghép: {p.name}",
                hint_vi="Kiểm tra lại đường dẫn tệp.",
                details={"file": str(p)},
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    stage_name = "merge"
    emit_event(stage_name, 0.0, f"Bắt đầu ghép {len(video_paths)} video...")

    # Probe all files
    profiles = []
    for idx, p in enumerate(video_paths, 1):
        probe_info = probe_file(p)
        v_prof, a_prof = extract_media_profile(probe_info)
        profiles.append((v_prof, a_prof))
        emit_event(stage_name, round(idx / len(video_paths) * 20.0, 1), f"Đã kiểm tra thông số: {p.name}")

    use_copy = (not force_reencode) and can_stream_copy(profiles)

    if use_copy:
        emit_event(stage_name, 30.0, "Các video có cùng định dạng, thực hiện ghép nhanh (stream copy)...")
        # Build concat list file
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            for p in video_paths:
                escaped_path = str(p.resolve()).replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
            concat_list = Path(f.name)

        try:
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list.resolve()),
                "-c", "copy",
                str(output_path.resolve()),
            ]
            run_command(cmd, description="ghép video stream copy")
        finally:
            concat_list.unlink(missing_ok=True)

    else:
        emit_event(stage_name, 30.0, "Các video khác định dạng hoặc độ phân giải, đang re-encode thống nhất...")
        # Target resolution: take the largest or first video resolution
        target_w = profiles[0][0].get("width") or 1920
        target_h = profiles[0][0].get("height") or 1080

        # Build filter_complex
        filter_parts = []
        concat_inputs = []

        inputs_cmd: List[str] = []
        for idx, p in enumerate(video_paths):
            inputs_cmd.extend(["-i", str(p.resolve())])
            # Normalize video stream
            filter_parts.append(
                f"[{idx}:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
                f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v{idx}]"
            )
            # Normalize audio stream (or generate silence if missing)
            has_audio = bool(profiles[idx][1])
            if has_audio:
                filter_parts.append(f"[{idx}:a]aformat=sample_rates=44100:channel_layouts=stereo[a{idx}]")
            else:
                filter_parts.append(f"aevalsrc=0:d=1[a{idx}]")
            concat_inputs.append(f"[v{idx}][a{idx}]")

        concat_filter = f"{''.join(concat_inputs)}concat=n={len(video_paths)}:v=1:a=1[outv][outa]"
        full_filter = ";".join(filter_parts) + ";" + concat_filter

        encoder = "h264_nvenc" if nvenc else "libx264"
        cmd = [
            "ffmpeg", "-y",
            *inputs_cmd,
            "-filter_complex", full_filter,
            "-map", "[outv]",
            "-map", "[outa]",
            "-c:v", encoder,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_path.resolve()),
        ]

        try:
            run_command(cmd, description=f"ghép video re-encode ({encoder})")
        except DubError as e:
            if encoder == "h264_nvenc":
                emit_event(stage_name, 50.0, "NVENC không khả dụng, chuyển sang libx264...", level="warning")
                cmd[cmd.index("h264_nvenc")] = "libx264"
                run_command(cmd, description="ghép video re-encode (libx264)")
            else:
                raise

    emit_event(stage_name, 100.0, f"Ghép video hoàn tất: {output_path.name}")
    return output_path

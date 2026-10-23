"""Video Trimming / Clipping Tool using ffmpeg with sub-second precision.

Supports fast stream copy (-c copy) for instantaneous cutting without quality loss,
with fallback to NVENC / libx264 re-encoding when cutting non-keyframes.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess

from dubstudio.errors import DubError
from dubstudio.ffmpeg_utils import run_command


def _check_nvenc_available() -> bool:
    try:
        res = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        return "h264_nvenc" in res.stdout
    except Exception:
        return False


def trim_video(
    video_path: Path | str,
    start_s: float,
    end_s: float,
    output_path: Path | str | None = None,
    fast_copy: bool = True,
) -> Path:
    """Trim a video file between start_s and end_s with sub-second accuracy.

    Args:
        video_path: Path to the input video.
        start_s: Start timestamp in seconds (e.g. 12.35).
        end_s: End timestamp in seconds (e.g. 45.60).
        output_path: Optional output path. Defaults to out/trimmed_{name}_{start}_{end}.mp4.
        fast_copy: If True, uses -c copy for instant, lossless cutting.

    Returns:
        Path to the trimmed video file.
    """
    v_path = Path(video_path).resolve()
    if not v_path.exists():
        raise DubError(
            code="FILE_NOT_FOUND",
            user_message_vi=f"Không tìm thấy file video nguồn: {v_path.name}",
            hint_vi="Vui lòng kiểm tra lại đường dẫn video.",
        )

    start_s = max(0.0, float(start_s))
    end_s = max(start_s + 0.1, float(end_s))
    duration = end_s - start_s

    if output_path is None:
        out_dir = Path("out")
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = v_path.stem
        start_tag = f"{int(start_s)}s"
        end_tag = f"{int(end_s)}s"
        target_path = out_dir / f"{stem}_cut_{start_tag}_{end_tag}.mp4"
    else:
        target_path = Path(output_path).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Try fast stream copy (-c copy) first if enabled
    if fast_copy:
        cmd_copy = [
            "ffmpeg",
            "-y",
            "-ss", f"{start_s:.3f}",
            "-to", f"{end_s:.3f}",
            "-i", str(v_path),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            str(target_path),
        ]
        try:
            res = subprocess.run(cmd_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            if res.returncode == 0 and target_path.exists() and target_path.stat().st_size > 1024:
                return target_path
        except Exception:
            pass

    # 2. Re-encode fallback for frame-accurate cuts
    vcodec = "h264_nvenc" if _check_nvenc_available() else "libx264"
    cmd_reencode = [
        "ffmpeg",
        "-y",
        "-ss", f"{start_s:.3f}",
        "-to", f"{end_s:.3f}",
        "-i", str(v_path),
        "-c:v", vcodec,
        "-preset", "p4" if vcodec == "h264_nvenc" else "fast",
        "-c:a", "aac",
        "-b:a", "192k",
        str(target_path),
    ]

    run_command(cmd_reencode, description="cắt video chính xác từng khung hình")

    if not target_path.exists() or target_path.stat().st_size == 0:
        raise DubError(
            code="TRIM_EMPTY_OUTPUT",
            user_message_vi="Quá trình cắt hoàn tất nhưng file kết quả rỗng.",
            hint_vi="Hãy chọn khoảng thời gian hợp lệ bên trong độ dài video.",
        )

    return target_path

"""Utilities for ffmpeg and ffprobe execution and safe argument handling."""
import json
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional
from dubstudio.errors import DubError
from dubstudio.paths import resolve_tool


def run_command(args: List[str], description: str = "lệnh") -> subprocess.CompletedProcess:
    """Run an external command using argument list with safe error reporting."""
    args = list(args)
    if args:
        args[0] = resolve_tool(args[0])

    from dubstudio.packaging import get_subprocess_env, get_subprocess_kwargs
    sub_kwargs = get_subprocess_kwargs()
    sub_env = get_subprocess_env()

    # Isolate working directory to tool binary folder to prevent DLL search collisions (0xc0000142)
    tool_bin = Path(args[0])
    tool_cwd = str(tool_bin.parent.resolve()) if tool_bin.exists() else None

    try:
        result = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            env=sub_env,
            cwd=tool_cwd,
            **sub_kwargs,
        )
    except FileNotFoundError as e:
        raise DubError(
            code="COMMAND_NOT_FOUND",
            user_message_vi=f"Không tìm thấy công cụ cần thiết: {args[0]}",
            hint_vi="Hãy chắc chắn ffmpeg/ffprobe đã được cài đặt và thêm vào PATH.",
            details={"command": args[0], "error": str(e)},
        )

    if result.returncode != 0:
        stderr_tail = "\n".join(result.stderr.splitlines()[-10:])
        raise DubError(
            code="FFMPEG_ERROR",
            user_message_vi=f"Xảy ra lỗi khi thực thi {description}.",
            hint_vi="Kiểm tra lại định dạng tệp đầu vào hoặc quyền ghi thư mục.",
            details={"args": args, "stderr": stderr_tail},
        )
    return result


def probe_file(file_path: Path) -> Dict[str, Any]:
    """Inspect media file streams and format using ffprobe."""
    if not file_path.exists():
        raise DubError(
            code="FILE_NOT_FOUND",
            user_message_vi=f"Không tìm thấy tệp phương tiện: {file_path.name}",
            hint_vi="Kiểm tra đường dẫn tệp.",
            details={"path": str(file_path)},
        )

    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration,size,bit_rate:stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
        "-of", "json",
        str(file_path.resolve()),
    ]
    res = run_command(cmd, description="ffprobe kiểm tra tệp")
    try:
        return json.loads(res.stdout)
    except Exception as e:
        raise DubError(
            code="FFPROBE_PARSE_ERROR",
            user_message_vi="Không thể đọc thông tin phương tiện từ ffprobe.",
            hint_vi="Tệp có thể bị hỏng hoặc định dạng không được hỗ trợ.",
            details={"error": str(e), "raw": res.stdout[:500]},
        )


def extract_audio(
    input_path: Path,
    output_path: Path,
    sample_rate: int = 44100,
    channels: int = 2,
) -> Path:
    """Extract audio track as 44.1kHz stereo WAV for high-fidelity separation and mixing."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Validate that input media contains at least one audio stream
    probe_info = probe_file(input_path)
    streams = probe_info.get("streams", [])
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    if not has_audio:
        raise DubError(
            code="NO_AUDIO_TRACK",
            user_message_vi=f"Tệp video '{input_path.name}' không có âm thanh (video câm/không có tiếng).",
            hint_vi="Quy trình lồng tiếng bắt buộc cần có tiếng gốc để nhận diện và dịch thuật. Vui lòng chọn tệp video có chứa âm thanh.",
            details={"streams": [s.get("codec_type") for s in streams]},
        )

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(input_path.resolve()),
        "-vn",
        "-ar", str(sample_rate),
        "-ac", str(channels),
        "-c:a", "pcm_s16le",
        str(output_path.resolve()),
    ]
    run_command(cmd, description="trích xuất âm thanh từ video")
    return output_path


def cut_clip(
    input_path: Path,
    output_path: Path,
    start_sec: float = 0.0,
    duration_sec: float = 10.0,
) -> Path:
    """Cut a segment from a media file without re-encoding video if possible."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(start_sec),
        "-i", str(input_path.resolve()),
        "-t", str(duration_sec),
        "-c", "copy",
        str(output_path.resolve()),
    ]
    run_command(cmd, description="cắt đoạn video")
    return output_path

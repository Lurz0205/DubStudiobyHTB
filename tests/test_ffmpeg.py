from pathlib import Path
import subprocess
import pytest
from dubstudio.ffmpeg_utils import extract_audio, probe_file


def test_ffmpeg_utils_with_spaces_and_unicode(tmp_path: Path):
    # Create directory with Vietnamese characters and spaces
    nested_dir = tmp_path / "Thư mục video kiểm thử"
    nested_dir.mkdir(parents=True, exist_ok=True)
    video_path = nested_dir / "video mẫu tiếng Việt.mp4"

    # Generate a tiny 1-second synthetic silent video using ffmpeg
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=1",
        "-c:v", "libx264", "-c:a", "aac",
        str(video_path.resolve())
    ]
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode != 0:
        pytest.skip("ffmpeg testsrc not available in environment")

    # Probe
    probe_data = probe_file(video_path)
    assert "streams" in probe_data
    assert len(probe_data["streams"]) >= 1

    # Extract audio to a path that also has unicode
    out_audio = nested_dir / "âm thanh trích xuất.wav"
    extract_audio(video_path, out_audio)

    assert out_audio.exists()
    assert out_audio.stat().st_size > 0

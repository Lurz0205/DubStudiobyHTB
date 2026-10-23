"""Benchmark script comparing h264_nvenc vs libx264 encoding."""
import os
from pathlib import Path
import subprocess
import sys

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Ensure UTF-8 console output
os.environ["PYTHONUTF8"] = "1"
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from scripts.hwprofile import profile_hw



def run_encode(input_video: Path, output_video: Path, encoder: str, crf_or_cq: int) -> None:
    output_video.parent.mkdir(parents=True, exist_ok=True)
    if encoder == "h264_nvenc":
        rate_args = ["-preset", "p5", "-cq", str(crf_or_cq)]
    else:
        rate_args = ["-preset", "medium", "-crf", str(crf_or_cq)]

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_video.resolve()),
        "-c:v", encoder,
        *rate_args,
        "-c:a", "copy",
        str(output_video.resolve()),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def main():
    # Target video: prefer clip_1min.mp4, fallback to tiny.mp4 if 1min is not yet provided
    sample_file = Path("samples/clip_1min.mp4")
    if not sample_file.exists():
        sample_file = Path("samples/tiny.mp4")

    if not sample_file.exists():
        print("Lỗi: Không tìm thấy samples/clip_1min.mp4 hoặc samples/tiny.mp4")
        return

    out_dir = Path("out/bench_render")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== BENCHMARK RENDER ({sample_file.name}) ===")
    results = []

    for enc in ["h264_nvenc", "libx264"]:
        out_file = out_dir / f"{enc}_{sample_file.name}"
        try:
            with profile_hw(interval_sec=0.2) as prof:
                run_encode(sample_file, out_file, enc, 23)

            size_kb = out_file.stat().st_size / 1024
            results.append({
                "tool": enc,
                "clip": sample_file.name,
                "wall_time": f"{prof.wall_time_s:.2f}s",
                "peak_ram": f"{prof.peak_ram_mb:.1f} MB",
                "peak_vram": f"{prof.peak_vram_mb:.1f} MB",
                "file_size": f"{size_kb:.1f} KB",
            })
        except subprocess.CalledProcessError:
            results.append({
                "tool": enc,
                "clip": sample_file.name,
                "wall_time": "FAILED",
                "peak_ram": "N/A",
                "peak_vram": "N/A",
                "file_size": "Nvidia driver < 610.00 (cần cập nhật driver NVIDIA hoặc dùng libx264)",
            })


    print("\n| Tool | Clip | Wall time | Peak RAM | Peak VRAM | File Size |")
    print("|---|---|---|---|---|---|")
    for r in results:
        print(f"| {r['tool']} | {r['clip']} | {r['wall_time']} | {r['peak_ram']} | {r['peak_vram']} | {r['file_size']} |")


if __name__ == "__main__":
    main()

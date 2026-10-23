"""Benchmark BS-RoFormer vocal/BGM separation using audio-separator on CUDA."""
import os
from pathlib import Path
import subprocess
import sys

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["PYTHONUTF8"] = "1"
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from scripts.hwprofile import profile_hw


def run_bs_roformer(input_audio: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    models_dir = Path("models/audio-separator")
    models_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m", "dubstudio.stages.separate",
        "--input", str(input_audio.resolve()),
        "--out-dir", str(out_dir.resolve()),
        "--models-dir", str(models_dir.resolve()),
        "--model", "model_bs_roformer_ep_317_sdr_12.9755.ckpt",
    ]
    subprocess.run(cmd, check=True)


def main():
    clips = [Path("samples/clip_1min.mp4")]
    if Path("samples/clip_10min.mp4").exists():
        clips.append(Path("samples/clip_10min.mp4"))

    out_base = Path("out/bench_separate")
    out_base.mkdir(parents=True, exist_ok=True)

    summary_rows = []

    for clip in clips:
        if not clip.exists():
            continue

        print(f"\n=== BENCHMARK SEPARATION (BS-RoFormer CUDA): {clip.name} ===")
        with profile_hw(interval_sec=0.5) as prof:
            run_bs_roformer(clip, out_base)

        summary_rows.append({
            "tool": "BS-RoFormer (SDR 12.9755 CUDA)",
            "clip": clip.name,
            "wall_time": f"{prof.wall_time_s:.2f}s",
            "peak_ram": f"{prof.peak_ram_mb:.1f} MB",
            "peak_vram": f"{prof.peak_vram_mb:.1f} MB",
        })

    print("\n| Tool | Clip | Wall time | Peak RAM | Peak VRAM |")
    print("|---|---|---|---|---|")
    for r in summary_rows:
        print(f"| {r['tool']} | {r['clip']} | {r['wall_time']} | {r['peak_ram']} | {r['peak_vram']} |")


if __name__ == "__main__":
    main()

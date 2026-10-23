"""Benchmark faster-whisper on Chinese speech clips."""
import os
from pathlib import Path
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["PYTHONUTF8"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Windows CUDA DLL registration for ctranslate2 (AGENTS.md Section 8)
import site
for p in site.getsitepackages():
    cublas_dir = Path(p) / "nvidia" / "cublas" / "bin"
    cudnn_dir = Path(p) / "nvidia" / "cudnn" / "bin"
    if cublas_dir.exists():
        os.add_dll_directory(str(cublas_dir))
    if cudnn_dir.exists():
        os.add_dll_directory(str(cudnn_dir))

from scripts.hwprofile import profile_hw


def format_timestamp(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def transcribe_clip(audio_path: Path, model_size: str = "large-v3-turbo") -> tuple:
    from faster_whisper import WhisperModel
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "int8_float16" if device == "cuda" else "int8"

    print(f"Loading faster-whisper ({model_size}) on {device} ({compute_type})...")
    model = WhisperModel(
        model_size,
        device=device,
        compute_type=compute_type,
        download_root="models",
    )

    print(f"Transcribing {audio_path.name}...")
    segments, info = model.transcribe(
        str(audio_path.resolve()),
        language="zh",
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
    )

    results = []
    for i, seg in enumerate(segments, 1):
        results.append({
            "id": i,
            "start": seg.start,
            "end": seg.end,
            "text": seg.text.strip(),
        })

    return results, info


def main():
    clips = [Path("samples/clip_1min.mp4")]
    if Path("samples/clip_10min.mp4").exists():
        clips.append(Path("samples/clip_10min.mp4"))

    out_dir = Path("out/bench_asr")
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = []

    for clip in clips:
        if not clip.exists():
            continue

        print(f"\n=== BENCHMARK ASR: {clip.name} ===")
        srt_file = out_dir / f"{clip.stem}_zh.srt"

        with profile_hw(interval_sec=0.5) as prof:
            segments, info = transcribe_clip(clip)

        # Write SRT
        with open(srt_file, "w", encoding="utf-8") as f:
            for s in segments:
                f.write(f"{s['id']}\n{format_timestamp(s['start'])} --> {format_timestamp(s['end'])}\n{s['text']}\n\n")

        print(f"\n[SRT Top 10 Segments of {clip.name}]:")
        for s in segments[:10]:
            print(f"[{format_timestamp(s['start'])} -> {format_timestamp(s['end'])}] {s['text']}")

        summary_rows.append({
            "tool": "faster-whisper (large-v3-turbo)",
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

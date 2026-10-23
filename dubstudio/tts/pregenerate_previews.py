"""Pre-generate all voice preview audio files ahead of time.

Ensures that whenever a user previews any voice in Settings,
playback starts instantly with 0ms delay.
"""
from __future__ import annotations

import os
from pathlib import Path
import site
import sys

# Force UTF-8 on Windows console if possible
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Force offline mode
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# Windows DLL directories for cuBLAS / cuDNN
if sys.platform == "win32":
    for p in site.getsitepackages():
        cublas_dir = Path(p) / "nvidia" / "cublas" / "bin"
        cudnn_dir = Path(p) / "nvidia" / "cudnn" / "bin"
        if cublas_dir.exists():
            try:
                os.add_dll_directory(str(cublas_dir))
            except Exception:
                pass
        if cudnn_dir.exists():
            try:
                os.add_dll_directory(str(cudnn_dir))
            except Exception:
                pass

ALL_VOICES = [
    "Minh Đức", "Hải Đăng", "Quốc Tuấn", "Quang Sơn", "Thiện Minh",
    "Minh Triết", "Đức Trí", "Thái Sơn", "Xuân Vĩnh", "Thanh Bình",
    "Phạm Tuyên", "Thiền Tâm Đức", "Adam", "Adam bựa",
    "Quỳnh Anh", "Mai Anh", "Trúc Ly", "Thùy Dung", "Ngọc Huyền",
    "Ngọc Trân", "Ngọc Linh", "Đoan Trang", "Thục Đoan", "Mỹ Duyên", "Kim Thanh",
]


def pregenerate_all_previews(progress_cb=None) -> None:
    """Generate all voice preview WAV files into out/voice_previews/."""
    preview_dir = Path("out/voice_previews")
    preview_dir.mkdir(parents=True, exist_ok=True)

    # Filter voices that still need generation
    needed = [v for v in ALL_VOICES if not (preview_dir / f"{v}.wav").exists()]
    if not needed:
        if progress_cb:
            progress_cb(len(ALL_VOICES), len(ALL_VOICES), "Tất cả các giọng đã có sẵn mẫu nghe thử.")
        return

    from huggingface_hub import snapshot_download
    from vieneu import Vieneu

    try:
        backbone_dir = snapshot_download("pnnbao-ump/VieNeu-TTS-v3-Turbo", local_files_only=True)
        moss_dir = snapshot_download("OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano", local_files_only=True)
    except Exception:
        backbone_dir = "pnnbao-ump/VieNeu-TTS-v3-Turbo"
        moss_dir = "OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano"

    try:
        engine = Vieneu(backbone_repo=backbone_dir, moss_tokenizer=moss_dir, device="cuda")
    except Exception:
        engine = Vieneu(backbone_repo=backbone_dir, moss_tokenizer=moss_dir, device="cpu")

    total = len(ALL_VOICES)
    done_count = total - len(needed)

    for v in needed:
        wav_path = preview_dir / f"{v}.wav"
        sample_text = f"Xin chào, tôi là giọng đọc {v} của DubStudio."
        try:
            audio = engine.infer(sample_text, voice=v)
            engine.save(audio, str(wav_path.resolve()))
        except Exception as e:
            # Fallback to CPU if CUDA issue
            try:
                engine = Vieneu(backbone_repo=backbone_dir, moss_tokenizer=moss_dir, device="cpu")
                audio = engine.infer(sample_text, voice=v)
                engine.save(audio, str(wav_path.resolve()))
            except Exception as e2:
                print(f"Error generating preview for {v}: {e2}", file=sys.stderr)

        done_count += 1
        if progress_cb:
            progress_cb(done_count, total, f"Đã chuẩn bị mẫu giọng: {v}")


if __name__ == "__main__":
    def _print_prog(cur, tot, msg):
        print(f"[{cur}/{tot}] {msg}")

    pregenerate_all_previews(_print_prog)

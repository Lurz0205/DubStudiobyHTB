"""Standalone offline subprocess worker for single-line TTS synthesis.

Runs in an isolated process to guarantee clean CUDA context and zero HF network requests.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
import soundfile as sf

# Force offline mode for Hugging Face & Transformers
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

if sys.platform == "win32":
    import site
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


def synthesize_single_line(text: str, voice: str, speed: float, out_path: Path) -> float:
    """Synthesize text with voice and speed, saving to out_path."""
    from vieneu import Vieneu
    from dubstudio.tts.base import resolve_vieneu_dirs
    from dubstudio.stages.fit import time_stretch_audio

    # Resolve local snapshot directories 100% offline
    backbone_dir, moss_dir = resolve_vieneu_dirs()

    # Try GPU first, fallback to CPU on CUDA error
    engine = None
    try:
        engine = Vieneu(backbone_repo=backbone_dir, moss_tokenizer=moss_dir, device="cuda")
        audio = engine.infer(text, voice=voice)
    except Exception as e:
        # Fallback to CPU on any CUDA or capture error
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
        engine = Vieneu(backbone_repo=backbone_dir, moss_tokenizer=moss_dir, device="cpu", backend="pytorch")
        audio = engine.infer(text, voice=voice)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile("wb", suffix=".wav", delete=False) as tmp:
        raw_wav = Path(tmp.name)

    try:
        engine.save(audio, str(raw_wav.resolve()))
        if abs(speed - 1.0) > 0.02:
            time_stretch_audio(raw_wav, out_path, rate=speed)
        else:
            shutil.copyfile(raw_wav, out_path)
    finally:
        raw_wav.unlink(missing_ok=True)

    info = sf.info(str(out_path))
    return round(info.duration, 3)


def main():
    parser = argparse.ArgumentParser(description="Single TTS synthesizer worker")
    parser.add_argument("--text", required=True, help="Text to speak")
    parser.add_argument("--voice", required=True, help="Voice name")
    parser.add_argument("--speed", type=float, default=1.0, help="Playback speed")
    parser.add_argument("--out", required=True, help="Output wav path")

    args = parser.parse_args()
    out_file = Path(args.out)

    try:
        dur = synthesize_single_line(args.text, args.voice, args.speed, out_file)
        sys.stdout.write(json.dumps({"status": "ok", "duration": dur, "file": str(out_file)}) + "\n")
        sys.stdout.flush()
        sys.exit(0)
    except Exception as e:
        sys.stderr.write(str(e) + "\n")
        sys.exit(1)


if __name__ == "__main__":
    main()

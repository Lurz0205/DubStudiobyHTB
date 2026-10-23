"""Persistent warm worker process for fast VieNeu-TTS inference.

Keeps the model loaded in memory to eliminate the ~12.8s model reload overhead.
Communicates via standard input/output using line-delimited JSON.
"""
import contextlib
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


def init_engine():
    from vieneu import Vieneu
    from dubstudio.tts.base import resolve_vieneu_dirs

    backbone_dir, moss_dir = resolve_vieneu_dirs()

    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass

    try:
        engine = Vieneu(backbone_repo=backbone_dir, moss_tokenizer=moss_dir, device="cuda")
        return engine
    except Exception:
        engine = Vieneu(backbone_repo=backbone_dir, moss_tokenizer=moss_dir, device="cpu", backend="pytorch")
        return engine


def main():
    if sys.stdout:
        sys.stdout.reconfigure(encoding="utf-8")
    if sys.stderr:
        sys.stderr.reconfigure(encoding="utf-8")

    from dubstudio.stages.fit import time_stretch_audio

    try:
        with contextlib.redirect_stdout(sys.stderr):
            engine = init_engine()
        # Signal readiness
        sys.stdout.write(json.dumps({"status": "ready"}) + "\n")
        sys.stdout.flush()
    except Exception as e:
        sys.stdout.write(json.dumps({"status": "error", "error": str(e)}) + "\n")
        sys.stdout.flush()
        sys.exit(1)

    # Process requests loop
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
            cmd = req.get("cmd")
            if cmd == "exit":
                break

            text = req.get("text", "")
            voice = req.get("voice", "Minh Đức")
            speed = float(req.get("speed", 1.0))
            out_path = Path(req.get("out", ""))

            with contextlib.redirect_stdout(sys.stderr):
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
            dur = round(info.duration, 3)

            sys.stdout.write(json.dumps({"status": "ok", "duration": dur, "file": str(out_path)}) + "\n")
            sys.stdout.flush()
        except Exception as e:
            sys.stdout.write(json.dumps({"status": "error", "error": str(e)}) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

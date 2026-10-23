"""Stage: separate. Separates vocals and BGM using audio-separator with Kim_Vocal_2 on CUDA GPU."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Optional

from dubstudio.config import AppConfig
from dubstudio.errors import DubError
from dubstudio.events import emit_event
from dubstudio.jobstate import JobContext, compute_file_hash

DEFAULT_SEPARATION_MODEL = "Kim_Vocal_2.onnx"


def _perform_separation(
    input_audio: Path,
    out_dir: Path,
    models_dir: Path,
    model_name: str = DEFAULT_SEPARATION_MODEL,
    force_cpu: bool = False,
) -> None:
    from dubstudio.packaging import ensure_runtime_paths
    ensure_runtime_paths()

    try:
        import torch
        from audio_separator.separator import Separator
    except (ImportError, ModuleNotFoundError) as e:
        raise DubError(
            code="RUNTIME_MISSING",
            message_vi=f"Không thể khởi chạy bộ tách nhạc vì thiếu thư viện AI PyTorch ({e}).",
            hint_vi="Vui lòng chuyển sang trang Cài đặt để kiểm tra hoặc tải gói AI Runtime.",
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    # Determine architecture params based on model name
    is_mdx = model_name.endswith(".onnx")
    sep_kwargs = {
        "log_level": 20,
        "model_file_dir": str(models_dir.resolve()),
        "output_dir": str(out_dir.resolve()),
        "output_format": "WAV",
        "sample_rate": 44100,
    }
    if is_mdx:
        sep_kwargs["mdx_params"] = {
            "segment_size": 512,
            "hop_length": 1024,
            "batch_size": 1,
            "overlap": 0.25,
        }
    else:
        # BS-RoFormer / Mel-Band RoFormer checkpoint parameters (MDXC)
        sep_kwargs["mdxc_params"] = {
            "segment_size": 256,
            "override_model_segment_size": False,
            "batch_size": 1,
            "overlap": 2,
            "pitch_shift": 0,
        }

    separator = Separator(**sep_kwargs)

    if force_cpu or not torch.cuda.is_available():
        separator.torch_device = torch.device("cpu")
        print(f"[separate] Running {model_name} on CPU fallback", flush=True)
    else:
        separator.torch_device = torch.device("cuda")
        print(f"[separate] Running {model_name} on GPU CUDA ({torch.cuda.get_device_name(0)})", flush=True)

    separator.load_model(model_name)
    output_files = separator.separate(str(input_audio.resolve()))

    # Map output files to vocals.wav and bgm.wav
    vocals_found: Optional[Path] = None
    bgm_found: Optional[Path] = None

    for fname in output_files:
        fpath = out_dir / fname
        if not fpath.exists():
            continue
        fl_lower = fname.lower()
        if "(vocals)" in fl_lower or "vocals" in fl_lower:
            vocals_found = fpath
        elif "(instrumental)" in fl_lower or "instrumental" in fl_lower or "no_vocals" in fl_lower or "inst" in fl_lower:
            bgm_found = fpath

    dest_vocals = out_dir / "vocals.wav"
    dest_bgm = out_dir / "bgm.wav"

    if vocals_found and vocals_found.exists():
        if vocals_found.resolve() != dest_vocals.resolve():
            if dest_vocals.exists():
                dest_vocals.unlink()
            shutil.move(str(vocals_found), str(dest_vocals))

    if bgm_found and bgm_found.exists():
        if bgm_found.resolve() != dest_bgm.resolve():
            if dest_bgm.exists():
                dest_bgm.unlink()
            shutil.move(str(bgm_found), str(dest_bgm))

    if not dest_vocals.exists() or not dest_bgm.exists():
        raise RuntimeError(f"Không tạo đủ vocals.wav và bgm.wav từ kết quả: {output_files}")

    print(f"[separate] Separation complete: {dest_vocals} ({dest_vocals.stat().st_size} bytes), {dest_bgm} ({dest_bgm.stat().st_size} bytes)", flush=True)


def run(job: JobContext, cfg: AppConfig, input_audio: Path) -> None:
    """Stage runner: executes Kim_Vocal_2 separation in an isolated subprocess."""
    stage_name = "separate"
    emit_event(stage_name, 0.0, "Bắt đầu tách giọng thoại (vocals) và nhạc nền (BGM) bằng Kim_Vocal_2")

    audio_dir = job.workspace / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    vocals_dest = audio_dir / "vocals.wav"
    bgm_dest = audio_dir / "bgm.wav"

    input_hash = compute_file_hash(input_audio)
    if job.is_stage_done(stage_name, input_hash):
        emit_event(stage_name, 100.0, "Giai đoạn tách âm thanh đã hoàn thành (bỏ qua)")
        return

    if vocals_dest.exists() and bgm_dest.exists() and vocals_dest.stat().st_size > 1000 and bgm_dest.stat().st_size > 1000:
        emit_event(stage_name, 100.0, "Giai đoạn tách âm thanh đã hoàn thành (bỏ qua)")
        job.start_stage(stage_name, input_hash)
        job.finish_stage(stage_name, ["audio/vocals.wav", "audio/bgm.wav"])
        return

    job.start_stage(stage_name, input_hash)

    from dubstudio.paths import get_models_dir
    models_dir = get_models_dir() / "audio-separator"
    sep_model = getattr(getattr(cfg, "separation", None), "model_name", None) or DEFAULT_SEPARATION_MODEL
    local_models = Path("models/audio-separator")
    if local_models.exists() and (local_models / sep_model).exists():
        models_dir = local_models
    else:
        models_dir.mkdir(parents=True, exist_ok=True)

    from dubstudio.packaging import get_runtime_python, get_subprocess_env, get_subprocess_kwargs
    cmd = [
        str(get_runtime_python()),
        "-m", "dubstudio.stages.separate",
        "--input", str(input_audio.resolve()),
        "--out-dir", str(audio_dir.resolve()),
        "--models-dir", str(models_dir.resolve()),
        "--model", sep_model,
    ]

    emit_event(stage_name, 20.0, f"Đang nạp mô hình tách nhạc {sep_model}...")
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            env=get_subprocess_env(),
            **get_subprocess_kwargs(),
        )

        if proc.returncode != 0:
            tail = "\n".join(proc.stderr.splitlines()[-15:])
            raise DubError(
                code="SEPARATION_FAILED",
                user_message_vi="Lỗi khi chạy mô hình Kim_Vocal_2 tách nhạc nền.",
                hint_vi="Kiểm tra bộ nhớ GPU/RAM hoặc định dạng tệp âm thanh.",
                details={"stderr": tail, "stdout": proc.stdout[-500:]},
            )
    except Exception as e:
        job.fail_stage(stage_name, str(e))
        raise

    if not vocals_dest.exists() or not bgm_dest.exists():
        raise DubError(
            code="STEMS_NOT_FOUND",
            user_message_vi="Không tìm thấy tệp vocals.wav hoặc bgm.wav sau khi tách.",
            hint_vi="Kiểm tra lại quyền ghi thư mục workspace.",
        )

    emit_event(stage_name, 100.0, "Tách giọng và nhạc nền bằng Kim_Vocal_2 hoàn tất")
    job.finish_stage(stage_name, ["audio/vocals.wav", "audio/bgm.wav"])


def main():
    parser = argparse.ArgumentParser(description="Run Kim_Vocal_2 separation in isolated subprocess")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--models-dir", required=True, type=Path)
    parser.add_argument("--model", default=DEFAULT_SEPARATION_MODEL)
    parser.add_argument("--force-cpu", action="store_true")
    args = parser.parse_args()

    try:
        _perform_separation(
            input_audio=args.input,
            out_dir=args.out_dir,
            models_dir=args.models_dir,
            model_name=args.model,
            force_cpu=args.force_cpu,
        )
    except Exception as e:
        err_msg = str(e).lower()
        if not args.force_cpu and ("out of memory" in err_msg or "cuda oom" in err_msg):
            print("[separate] WARNING: CUDA OOM during separation, retrying with CPU fallback...", file=sys.stderr)
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            _perform_separation(
                input_audio=args.input,
                out_dir=args.out_dir,
                models_dir=args.models_dir,
                model_name=args.model,
                force_cpu=True,
            )
        else:
            raise


if __name__ == "__main__":
    main()

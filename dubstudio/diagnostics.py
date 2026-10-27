"""System diagnostics, prerequisite verification, and log bundle exporter."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
import time
import zipfile
from typing import Tuple

from dubstudio.paths import (
    is_packaged, get_app_dir, get_user_base_dir, get_models_dir,
    get_workspace_dir, get_logs_dir, get_bin_dir, resolve_tool
)


def check_system_prerequisites(task: str = "subtitles") -> Tuple[bool, str, str]:
    """
    Verify core prerequisites before executing pipeline tasks.
    Returns: (is_ready, title_vi, message_vi)
    """
    # 1. FFmpeg & FFprobe check
    try:
        resolve_tool("ffmpeg")
        resolve_tool("ffprobe")
    except Exception as e:
        return (
            False,
            "Thiếu công cụ xử lý âm thanh / video (FFmpeg)",
            f"DubStudio không tìm thấy ffmpeg hoặc ffprobe ({e}). "
            "Vui lòng đảm bảo thư mục 'bin' chứa ffmpeg.exe và ffprobe.exe.",
        )

    # 2. Check PyTorch runtime if packaged
    if is_packaged():
        try:
            import torch
        except Exception:
            runtime_site = get_user_base_dir() / "runtime" / "site-packages"
            if not (runtime_site / "torch").exists():
                return (
                    False,
                    "Chưa cài đặt môi trường AI (PyTorch Runtime)",
                    "DubStudio chưa tìm thấy thư viện AI PyTorch để xử lý tách nhạc và nhận dạng giọng.\n\n"
                    "👉 Vui lòng chuyển sang tab 'Cài đặt' -> mục 'Quản lý Gói mô hình AI' để tải gói Runtime.",
                )

    # 3. Check Models depending on task
    from dubstudio.components import is_component_ready, is_pkg_downloading
    from dubstudio.config import AppConfig

    cfg = AppConfig.load()
    asr_val = os.getenv("WHISPER_MODEL", "") or os.getenv("ASR_MODEL", "") or cfg.asr.model_size or "sensevoice-small"
    is_sensevoice = "sensevoice" in str(asr_val).lower()
    asr_pkg = "sensevoice_small" if is_sensevoice else "whisper_large_v3"
    asr_name = "SenseVoice-Small" if is_sensevoice else "faster-whisper large-v3"

    if task in ("subtitles", "all"):
        if is_pkg_downloading(asr_pkg):
            return (
                False,
                "Mô hình nhận diện đang tải dở",
                f"Mô hình '{asr_name}' đang trong quá trình tải về máy.\n\n"
                f"⏳ Vui lòng đợi quá trình tải hoàn tất 100% trước khi bấm tạo phụ đề!",
            )
        ok, _ = is_component_ready(asr_pkg)
        if not ok:
            return (
                False,
                "Chưa tải mô hình nhận diện giọng nói",
                f"DubStudio chưa tìm thấy mô hình nhận diện '{asr_name}' trên đĩa.\n\n"
                f"👉 Vui lòng chuyển sang tab 'Cài đặt' -> mục 'Quản lý Gói mô hình AI' để tải hoàn tất mô hình trước khi tạo phụ đề.",
            )

    if task in ("dub", "all"):
        if is_pkg_downloading("vieneu_tts_voices"):
            return (
                False,
                "Mô hình giọng đọc đang tải dở",
                "Mô hình giọng đọc VieNeu-TTS v3 đang trong quá trình tải về máy.\n\n"
                "⏳ Vui lòng đợi quá trình tải hoàn tất 100% trước khi bấm tạo lồng tiếng!",
            )
        ok, _ = is_component_ready("vieneu_tts_voices")
        if not ok:
            return (
                False,
                "Chưa tải mô hình giọng đọc thuyết minh tiếng Việt",
                "DubStudio chưa tìm thấy mô hình VieNeu-TTS v3 trên đĩa.\n\n"
                "👉 Vui lòng chuyển sang tab 'Cài đặt' -> mục 'Quản lý Gói mô hình AI' để tải mô hình VieNeu-TTS (~280 MB).",
            )

    return True, "", ""


def generate_selftest_report() -> dict:
    """Generate self-test report without printing to console."""
    import subprocess
    results = {
        "status": "ok",
        "packaged": is_packaged(),
        "python": str(sys.executable),
        "app_dir": str(get_app_dir()),
        "user_base_dir": str(get_user_base_dir()),
        "models_dir": str(get_models_dir()),
        "workspace_dir": str(get_workspace_dir()),
        "logs_dir": str(get_logs_dir()),
        "bin_dir": str(get_bin_dir()),
        "ffmpeg": None,
        "ffprobe": None,
        "cuda_available": False,
        "errors": [],
    }

    try:
        ffmpeg_bin = resolve_tool("ffmpeg")
        proc = subprocess.run([str(ffmpeg_bin), "-version"], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0:
            results["ffmpeg"] = {"path": str(ffmpeg_bin), "version": proc.stdout.splitlines()[0] if proc.stdout else ""}
        else:
            results["status"] = "error"
            results["errors"].append(f"ffmpeg returned code {proc.returncode}")
    except Exception as e:
        results["status"] = "error"
        results["errors"].append(f"ffmpeg: {e}")

    try:
        ffprobe_bin = resolve_tool("ffprobe")
        proc = subprocess.run([str(ffprobe_bin), "-version"], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0:
            results["ffprobe"] = {"path": str(ffprobe_bin), "version": proc.stdout.splitlines()[0] if proc.stdout else ""}
        else:
            results["status"] = "error"
            results["errors"].append(f"ffprobe returned code {proc.returncode}")
    except Exception as e:
        results["status"] = "error"
        results["errors"].append(f"ffprobe: {e}")

    try:
        import torch
        results["cuda_available"] = bool(torch.cuda.is_available())
        if results["cuda_available"]:
            results["gpu_name"] = torch.cuda.get_device_name(0)
    except Exception:
        results["cuda_available"] = False

    return results


def collect_system_summary() -> dict:
    """Collect non-sensitive system environment summary (OS, Python, CUDA, FFmpeg)."""
    import platform
    import subprocess

    summary = {
        "os": {
            "platform": sys.platform,
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
        },
        "python": {
            "version": sys.version,
            "executable": str(sys.executable),
            "packaged": is_packaged(),
        },
        "cuda": {
            "available": False,
            "device_name": None,
        },
        "ffmpeg": {
            "available": False,
            "path": None,
            "version": None,
        },
        "ffprobe": {
            "available": False,
            "path": None,
            "version": None,
        },
        "paths": {
            "app_dir": str(get_app_dir()),
            "user_base_dir": str(get_user_base_dir()),
            "models_dir": str(get_models_dir()),
            "logs_dir": str(get_logs_dir()),
        },
    }

    try:
        ffmpeg_bin = resolve_tool("ffmpeg")
        proc = subprocess.run([str(ffmpeg_bin), "-version"], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0:
            summary["ffmpeg"]["available"] = True
            summary["ffmpeg"]["path"] = str(ffmpeg_bin)
            summary["ffmpeg"]["version"] = proc.stdout.splitlines()[0] if proc.stdout else ""
    except Exception:
        pass

    try:
        ffprobe_bin = resolve_tool("ffprobe")
        proc = subprocess.run([str(ffprobe_bin), "-version"], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0:
            summary["ffprobe"]["available"] = True
            summary["ffprobe"]["path"] = str(ffprobe_bin)
            summary["ffprobe"]["version"] = proc.stdout.splitlines()[0] if proc.stdout else ""
    except Exception:
        pass

    try:
        import torch
        summary["cuda"]["available"] = bool(torch.cuda.is_available())
        if summary["cuda"]["available"]:
            summary["cuda"]["device_name"] = torch.cuda.get_device_name(0)
    except Exception:
        pass

    return summary


def export_diagnostics_bundle(output_zip: Path | None = None) -> Path:
    """
    Export all system logs and diagnostics into a zip file.
    Always includes system_summary.json and logs without leaking any secrets.
    """
    if output_zip is None:
        target_dir = Path.home() / "Desktop"
        if not target_dir.exists():
            target_dir = get_user_base_dir()
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        out_zip = target_dir / f"DubStudio_Diagnostic_{timestamp}.zip"
    else:
        out_zip = Path(output_zip)

    out_zip.parent.mkdir(parents=True, exist_ok=True)
    summary_data = collect_system_summary()
    logs_dir = get_logs_dir()

    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. System summary json
        zf.writestr("system_summary.json", json.dumps(summary_data, ensure_ascii=False, indent=2))

        # 2. Main app log
        app_log = logs_dir / "app.log"
        if app_log.exists():
            try:
                zf.write(app_log, arcname="logs/app.log")
            except Exception:
                pass

        # 3. Stage logs
        stage_dir = logs_dir / "stages"
        if stage_dir.exists():
            for sf in stage_dir.glob("*.log"):
                try:
                    zf.write(sf, arcname=f"logs/stages/{sf.name}")
                except Exception:
                    pass

        # 4. Sanitized config
        cfg_path = get_app_dir() / "config" / "default.toml"
        if cfg_path.exists():
            try:
                lines = cfg_path.read_text(encoding="utf-8", errors="ignore").splitlines()
                sanitized = []
                for line in lines:
                    if any(k in line.lower() for k in ("api_key", "secret", "password", "token")):
                        parts = line.split("=", 1)
                        if len(parts) == 2:
                            sanitized.append(f"{parts[0]}= \"[REDACTED]\"")
                            continue
                    sanitized.append(line)
                zf.writestr("config_sanitized.toml", "\n".join(sanitized))
            except Exception:
                pass

    return out_zip


export_diagnostic_zip = export_diagnostics_bundle
export_diagnostic_bundle = export_diagnostics_bundle

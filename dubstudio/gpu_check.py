"""GPU and driver diagnostic utility without PyTorch dependencies (NVML / nvidia-smi)."""
from __future__ import annotations
import re
import shutil
import subprocess
from typing import Dict, Optional, Tuple

MIN_NVIDIA_DRIVER_VERSION = "528.33"  # Minimum required for PyTorch CUDA 12.1+


class GPUStatus:
    NO_NVIDIA = "NO_NVIDIA"
    DRIVER_OUTDATED_OR_MISSING = "DRIVER_OUTDATED_OR_MISSING"
    VRAM_LOW = "VRAM_LOW"
    OK_CUDA = "OK_CUDA"


def _parse_version_tuple(v_str: str) -> Tuple[int, ...]:
    """Parse string version like '535.104.05' into integer tuple for accurate comparison."""
    clean = re.sub(r"[^\d.]", "", v_str.strip())
    parts = clean.split(".")
    try:
        return tuple(int(p) for p in parts if p)
    except Exception:
        return (0,)


def is_driver_compatible(current_driver: str, min_driver: str = MIN_NVIDIA_DRIVER_VERSION) -> bool:
    """Compare driver version numbers accurately."""
    cur_tup = _parse_version_tuple(current_driver)
    min_tup = _parse_version_tuple(min_driver)
    return cur_tup >= min_tup


def detect_nvidia_gpu_nvml() -> Optional[Dict[str, str | int | float]]:
    """Query NVIDIA GPU info via NVML (pynvml / nvidia-ml-py)."""
    try:
        import pynvml
        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        if device_count == 0:
            pynvml.nvmlShutdown()
            return None

        # Take primary device (index 0)
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        name_raw = pynvml.nvmlDeviceGetName(handle)
        card_name = name_raw.decode("utf-8") if isinstance(name_raw, bytes) else str(name_raw)

        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        total_vram_mb = int(mem_info.total / (1024 * 1024))

        driver_raw = pynvml.nvmlSystemGetDriverVersion()
        driver_ver = driver_raw.decode("utf-8") if isinstance(driver_raw, bytes) else str(driver_raw)

        pynvml.nvmlShutdown()
        return {
            "name": card_name,
            "vram_mb": total_vram_mb,
            "vram_gb": round(total_vram_mb / 1024, 2),
            "driver_version": driver_ver,
            "method": "nvml",
        }
    except Exception:
        return None


def detect_nvidia_gpu_smi() -> Optional[Dict[str, str | int | float]]:
    """Query NVIDIA GPU info via nvidia-smi CLI fallback."""
    smi_path = shutil.which("nvidia-smi")
    if not smi_path:
        # Common default Windows location
        candidate = r"C:\Windows\System32\DriverStore\FileRepository\nv_dispi.inf_amd64_*\nvidia-smi.exe"
        import glob
        matches = glob.glob(candidate)
        if matches:
            smi_path = matches[0]

    if not smi_path:
        return None

    try:
        cmd = [
            smi_path,
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader,nounits",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=3, check=False)
        if res.returncode != 0 or not res.stdout.strip():
            return None

        lines = res.stdout.strip().splitlines()
        first_line = lines[0].split(",")
        if len(first_line) >= 3:
            card_name = first_line[0].strip()
            total_vram_mb = int(float(first_line[1].strip()))
            driver_ver = first_line[2].strip()
            return {
                "name": card_name,
                "vram_mb": total_vram_mb,
                "vram_gb": round(total_vram_mb / 1024, 2),
                "driver_version": driver_ver,
                "method": "nvidia-smi",
            }
    except Exception:
        pass

    return None


def inspect_gpu_and_driver(min_driver: str = MIN_NVIDIA_DRIVER_VERSION) -> Dict[str, any]:
    """
    Perform complete GPU inspection and classify into one of the 4 standard states:
    - NO_NVIDIA
    - DRIVER_OUTDATED_OR_MISSING
    - VRAM_LOW
    - OK_CUDA
    """
    info = detect_nvidia_gpu_nvml()
    if not info:
        info = detect_nvidia_gpu_smi()

    if not info:
        return {
            "status": GPUStatus.NO_NVIDIA,
            "card_name": "Không tìm thấy card NVIDIA",
            "vram_mb": 0,
            "vram_gb": 0.0,
            "driver_version": "N/A",
            "min_driver_required": min_driver,
            "recommended_mode": "cpu",
        }

    card_name = str(info["name"])
    vram_mb = int(info["vram_mb"])
    driver_ver = str(info["driver_version"])

    if not driver_ver or not is_driver_compatible(driver_ver, min_driver):
        return {
            "status": GPUStatus.DRIVER_OUTDATED_OR_MISSING,
            "card_name": card_name,
            "vram_mb": vram_mb,
            "vram_gb": round(vram_mb / 1024, 2),
            "driver_version": driver_ver or "Chưa cài đặt",
            "min_driver_required": min_driver,
            "recommended_mode": "cpu",
        }

    if vram_mb < 3800:  # Under 4GB threshold
        return {
            "status": GPUStatus.VRAM_LOW,
            "card_name": card_name,
            "vram_mb": vram_mb,
            "vram_gb": round(vram_mb / 1024, 2),
            "driver_version": driver_ver,
            "min_driver_required": min_driver,
            "recommended_mode": "cpu",
        }

    return {
        "status": GPUStatus.OK_CUDA,
        "card_name": card_name,
        "vram_mb": vram_mb,
        "vram_gb": round(vram_mb / 1024, 2),
        "driver_version": driver_ver,
        "min_driver_required": min_driver,
        "recommended_mode": "cuda",
    }

"""Environment verification script for Phase 0."""
import os
import shutil
import subprocess
import sys


def check_python() -> bool:
    v = sys.version_info
    ver_str = f"{v.major}.{v.minor}.{v.micro}"
    if v.major == 3 and v.minor == 11:
        print(f"[OK] Python version: {ver_str} (3.11 required)")
        return True
    print(f"[FAIL] Python version: {ver_str} (Expected 3.11)")
    return False


def check_torch() -> bool:
    try:
        import torch
        ver = torch.__version__
        cuda_avail = torch.cuda.is_available()
        gpu_name = torch.cuda.get_device_name(0) if cuda_avail else "N/A"
        if cuda_avail:
            print(f"[OK] PyTorch: {ver} | CUDA Available: True | GPU: {gpu_name}")
            return True
        else:
            print(f"[FAIL] PyTorch: {ver} | CUDA Available: False")
            return False
    except ImportError:
        print("[FAIL] PyTorch is not installed")
        return False
    except Exception as e:
        print(f"[FAIL] PyTorch error: {e}")
        return False


def check_ffmpeg() -> bool:
    try:
        res = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, check=True)
        first_line = res.stdout.splitlines()[0] if res.stdout else "Unknown"
        print(f"[OK] ffmpeg: {first_line}")
        return True
    except FileNotFoundError:
        print("[FAIL] ffmpeg not found in PATH")
        return False
    except Exception as e:
        print(f"[FAIL] ffmpeg error: {e}")
        return False


def check_nvenc() -> bool:
    try:
        res = subprocess.run(["ffmpeg", "-encoders"], capture_output=True, text=True, check=True)
        if "h264_nvenc" in res.stdout:
            print("[OK] h264_nvenc encoder: Available")
            return True
        else:
            print("[WARN/FAIL] h264_nvenc encoder not found in ffmpeg -encoders")
            return False
    except Exception as e:
        print(f"[FAIL] Could not verify h264_nvenc: {e}")
        return False


def check_nvidia_smi() -> bool:
    try:
        res = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
                             capture_output=True, text=True, check=True)
        summary = res.stdout.strip()
        print(f"[OK] nvidia-smi: {summary}")
        return True
    except FileNotFoundError:
        print("[WARN] nvidia-smi not found in PATH")
        return False
    except Exception as e:
        print(f"[FAIL] nvidia-smi error: {e}")
        return False


def check_disk_space() -> bool:
    try:
        usage = shutil.disk_usage(os.getcwd())
        free_gb = usage.free / (1024 ** 3)
        if free_gb >= 15.0:
            print(f"[OK] Free disk space: {free_gb:.1f} GB (>= 15 GB)")
            return True
        else:
            print(f"[FAIL/WARN] Free disk space low: {free_gb:.1f} GB (< 15 GB required)")
            return False
    except Exception as e:
        print(f"[FAIL] Could not check disk space: {e}")
        return False


def check_ram() -> bool:
    try:
        import psutil
        mem = psutil.virtual_memory()
        total_gb = mem.total / (1024 ** 3)
        avail_gb = mem.available / (1024 ** 3)
        print(f"[OK] RAM Total: {total_gb:.1f} GB | Available: {avail_gb:.1f} GB")
        return True
    except ImportError:
        print("[WARN] psutil not installed yet, skipping detailed RAM check")
        return True
    except Exception as e:
        print(f"[FAIL] Could not check RAM: {e}")
        return False


def main():
    print("=== DUBSTUDIO ENVIRONMENT CHECK (PHASE 0) ===")
    results = [
        check_python(),
        check_torch(),
        check_ffmpeg(),
        check_nvenc(),
        check_nvidia_smi(),
        check_disk_space(),
        check_ram(),
    ]
    print("=============================================")
    if all(results):
        print("RESULT: ALL CHECKS PASSED.")
    else:
        print("RESULT: SOME CHECKS FAILED OR WARNED. Review output above.")


if __name__ == "__main__":
    main()

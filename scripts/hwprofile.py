"""Hardware resource profiler sampling RAM and VRAM."""
import contextlib
import threading
import time
from typing import Generator
import psutil
import pynvml


class ProfilerResult:
    def __init__(self) -> None:
        self.wall_time_s: float = 0.0
        self.peak_ram_mb: float = 0.0
        self.peak_vram_mb: float = 0.0
        self.baseline_ram_mb: float = 0.0
        self.baseline_vram_mb: float = 0.0


@contextlib.contextmanager
def profile_hw(interval_sec: float = 0.5) -> Generator[ProfilerResult, None, None]:
    """Context manager measuring wall time, peak RAM (MB), and peak VRAM (MB)."""
    res = ProfilerResult()
    has_nvml = False

    try:
        pynvml.nvmlInit()
        gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        has_nvml = True
    except Exception:
        gpu_handle = None

    stop_event = threading.Event()

    def get_vram_mb() -> float:
        if has_nvml and gpu_handle:
            try:
                mem = pynvml.nvmlDeviceGetMemoryInfo(gpu_handle)
                return mem.used / (1024 * 1024)
            except Exception:
                pass
        return 0.0

    def get_ram_mb() -> float:
        return psutil.virtual_memory().used / (1024 * 1024)

    res.baseline_ram_mb = get_ram_mb()
    res.baseline_vram_mb = get_vram_mb()
    res.peak_ram_mb = res.baseline_ram_mb
    res.peak_vram_mb = res.baseline_vram_mb

    def monitor():
        while not stop_event.is_set():
            ram = get_ram_mb()
            vram = get_vram_mb()
            if ram > res.peak_ram_mb:
                res.peak_ram_mb = ram
            if vram > res.peak_vram_mb:
                res.peak_vram_mb = vram
            stop_event.wait(interval_sec)

    t = threading.Thread(target=monitor, daemon=True)
    start_time = time.perf_counter()
    t.start()

    try:
        yield res
    finally:
        end_time = time.perf_counter()
        stop_event.set()
        t.join(timeout=1.0)
        res.wall_time_s = end_time - start_time
        if has_nvml:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass

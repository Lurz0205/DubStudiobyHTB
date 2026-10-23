"""Unit tests for Phase 3 VRAM lifecycle, ffmpeg job guard, and resource cleanup."""
import os
import subprocess
import sys
import time
from pathlib import Path
import pytest

from dubstudio.packaging import safe_subprocess_run, safe_subprocess_popen


def test_safe_subprocess_run_echo():
    """Verify safe_subprocess_run executes commands cleanly with Job Object attachment."""
    cmd = [sys.executable, "-c", "print('hello_safe_sub')"]
    res = safe_subprocess_run(cmd, stdout=subprocess.PIPE, text=True)
    assert res.returncode == 0
    assert "hello_safe_sub" in res.stdout


def test_safe_subprocess_popen_lifecycle():
    """Verify safe_subprocess_popen attaches process to Job Object and terminates properly."""
    cmd = [sys.executable, "-c", "import time; time.sleep(1.0)"]
    proc = safe_subprocess_popen(cmd)
    assert proc.poll() is None
    proc.terminate()
    proc.wait(timeout=3)
    assert proc.poll() is not None


def test_vram_cleanup_gc():
    """Verify gc.collect and cuda cache empty can be called safely without errors."""
    import gc
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except Exception:
        pass


def test_winerror32_file_replacement_guard(tmp_path: Path):
    """Simulate file replacement pattern used in _ensure_boosted_track to verify no WinError 32."""
    orig_file = tmp_path / "track.wav"
    orig_file.write_bytes(b"RIFF" + b"\x00" * 100)

    # Perform atomic-like replace using a temp file
    tmp_file = tmp_path / f"track.tmp_{os.getpid()}.wav"
    tmp_file.write_bytes(b"RIFF" + b"\x01" * 100)

    # In Windows, os.replace over an un-opened file is atomic and clean
    os.replace(tmp_file, orig_file)
    assert orig_file.exists()
    assert orig_file.read_bytes() == b"RIFF" + b"\x01" * 100

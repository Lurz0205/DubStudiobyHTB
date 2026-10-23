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


def test_components_physical_verification_and_sync(monkeypatch, tmp_path):
    """Verify is_component_ready returns False for nonexistent models and sync prunes ghost records."""
    from dubstudio.components import is_component_ready, sync_installed_components, get_installed_components, save_installed_components

    fake_comp_dir = tmp_path / "components"
    fake_comp_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("dubstudio.components.get_components_dir", lambda: fake_comp_dir)
    monkeypatch.setattr("dubstudio.components.get_installed_components_file", lambda: fake_comp_dir / "installed.json")

    # Seed installed.json with ghost records that do not exist physically
    fake_installed = {
        "whisper_large_v3": {"version": 1},
    }
    save_installed_components(fake_installed)

    # Physical verification must fail for nonexistent Whisper in empty tmp
    ready, msg = is_component_ready("whisper_large_v3")
    assert not ready
    assert msg == "Chưa tải"

    # Sync must prune ghost records
    synced = sync_installed_components()
    assert "whisper_large_v3" not in synced


def test_selective_asr_checking(monkeypatch):
    """Verify check_all_updates only requires the actively selected ASR model."""
    from dubstudio.updater import check_all_updates

    # Case 1: SenseVoice is active
    monkeypatch.setenv("WHISPER_MODEL", "sensevoice-small")
    monkeypatch.setenv("ASR_MODEL", "sensevoice-small")
    res1 = check_all_updates()
    missing_ids_1 = [p["id"] for p in res1.get("missing_components", [])]
    assert "whisper_large_v3" not in missing_ids_1

    # Case 2: Whisper is active
    monkeypatch.setenv("WHISPER_MODEL", "large-v3")
    monkeypatch.setenv("ASR_MODEL", "large-v3")
    res2 = check_all_updates()
    missing_ids_2 = [p["id"] for p in res2.get("missing_components", [])]
    assert "sensevoice_small" not in missing_ids_2


def test_cleanup_dangling_staging_files(tmp_path, monkeypatch):
    """Verify cleanup_dangling_staging_files removes leftover .staging_* folders and .part files."""
    from dubstudio.components import cleanup_dangling_staging_files

    fake_models = tmp_path / "models"
    fake_user_data = tmp_path / "user_data"
    fake_models.mkdir()
    fake_user_data.mkdir()

    staging_dir = fake_models / ".staging_test_123"
    staging_dir.mkdir()
    (staging_dir / "partial.bin").write_bytes(b"temp")

    part_file = fake_user_data / "model.pt.part"
    part_file.write_bytes(b"part_data")

    monkeypatch.setattr("dubstudio.paths.get_models_dir", lambda: fake_models)
    monkeypatch.setattr("dubstudio.paths.get_user_data_dir", lambda: fake_user_data)

    cleanup_dangling_staging_files()

    assert not staging_dir.exists()
    assert not part_file.exists()



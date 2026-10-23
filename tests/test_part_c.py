"""Unit tests for Part C: packaging mode, GPU detection, components management, and migrations."""
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from dubstudio.components import (
    APP_REQUIRED_COMPONENTS,
    check_for_component_updates,
    fetch_components_manifest,
    get_installed_components,
    install_package_atomic,
    is_component_ready,
    verify_file_sha256,
)
from dubstudio.gpu_check import GPUStatus, inspect_gpu_and_driver, is_driver_compatible
from dubstudio.migration import migrate_config_dict, migrate_job_state
from dubstudio.packaging import get_models_dir, get_runtime_python, get_user_data_dir, is_packaged


# ─── C1: Packaging Detection ───

def test_packaging_dev_vs_forced_mode(monkeypatch):
    """Verify is_packaged returns False in dev, True when DUBSTUDIO_FORCE_PACKAGED=1."""
    monkeypatch.delenv("DUBSTUDIO_FORCE_PACKAGED", raising=False)
    assert not is_packaged()

    monkeypatch.setenv("DUBSTUDIO_FORCE_PACKAGED", "1")
    assert is_packaged()

    # User data directory should be outside repository
    user_dir = get_user_data_dir()
    assert "DubStudio" in str(user_dir)


# ─── C3: GPU Detection (NVML / nvidia-smi without PyTorch) ───

def test_driver_compatible_comparison():
    assert is_driver_compatible("535.104.05", "528.33") is True
    assert is_driver_compatible("528.33", "528.33") is True
    assert is_driver_compatible("470.120", "528.33") is False
    assert is_driver_compatible("512.77", "528.33") is False


def test_gpu_inspection_no_nvidia():
    with patch("dubstudio.gpu_check.detect_nvidia_gpu_nvml", return_value=None), \
         patch("dubstudio.gpu_check.detect_nvidia_gpu_smi", return_value=None):
        res = inspect_gpu_and_driver()
        assert res["status"] == GPUStatus.NO_NVIDIA
        assert res["recommended_mode"] == "cpu"


def test_gpu_inspection_driver_outdated():
    fake_info = {
        "name": "NVIDIA GeForce RTX 2050",
        "vram_mb": 4096,
        "driver_version": "512.77",
    }
    with patch("dubstudio.gpu_check.detect_nvidia_gpu_nvml", return_value=fake_info):
        res = inspect_gpu_and_driver()
        assert res["status"] == GPUStatus.DRIVER_OUTDATED_OR_MISSING
        assert res["recommended_mode"] == "cpu"
        assert res["driver_version"] == "512.77"


def test_gpu_inspection_vram_low():
    fake_info = {
        "name": "NVIDIA GeForce MX450",
        "vram_mb": 2048,
        "driver_version": "535.104",
    }
    with patch("dubstudio.gpu_check.detect_nvidia_gpu_nvml", return_value=fake_info):
        res = inspect_gpu_and_driver()
        assert res["status"] == GPUStatus.VRAM_LOW
        assert res["recommended_mode"] == "cpu"


def test_gpu_inspection_ok_cuda():
    fake_info = {
        "name": "NVIDIA GeForce RTX 4060",
        "vram_mb": 8192,
        "driver_version": "550.54",
    }
    with patch("dubstudio.gpu_check.detect_nvidia_gpu_nvml", return_value=fake_info):
        res = inspect_gpu_and_driver()
        assert res["status"] == GPUStatus.OK_CUDA
        assert res["recommended_mode"] == "cuda"


# ─── C4: Components Lifecycle ───

def test_components_manifest_and_update_check(tmp_path, monkeypatch):
    monkeypatch.setattr("dubstudio.components.get_components_dir", lambda: tmp_path)

    manifest = fetch_components_manifest()
    assert "packages" in manifest
    assert len(manifest["packages"]) >= 2

    # Should detect update since nothing installed
    updates = check_for_component_updates()
    assert len(updates) > 0
    assert any(u["package"]["id"] == "vieneu_tts_voices" for u in updates)


def test_components_atomic_install_and_ready_check(tmp_path, monkeypatch):
    monkeypatch.setattr("dubstudio.components.get_components_dir", lambda: tmp_path)

    # Test file and checksum
    dummy_zip = tmp_path / "test_pkg.zip"
    dummy_content = b"sample_package_data_for_test"
    dummy_zip.write_bytes(dummy_content)

    import hashlib
    sha = hashlib.sha256(dummy_content).hexdigest()

    pkg = {
        "id": "vieneu_tts_voices",
        "name": "VieNeu Voices",
        "version": 1,
        "sha256": sha,
    }

    # Install package atomically
    success = install_package_atomic(pkg, dummy_zip)
    assert success is True

    # Ready check should now succeed
    ready, msg = is_component_ready("vieneu_tts_voices")
    assert ready is True
    assert "sẵn sàng" in msg.lower()


# ─── C4: Schema Migration ───

def test_config_migration():
    v1_config = {
        "schema_version": 1,
        "downloader": {"quality": "1080p"},
        "translation": {"model": "old-model"},
    }
    migrated = migrate_config_dict(v1_config)
    assert migrated["schema_version"] == 2
    assert "downloader" not in migrated
    assert migrated["translation"]["provider"] == "gemini_web"


def test_job_state_migration(tmp_path):
    ws = tmp_path / "job_legacy"
    ws.mkdir()
    state_file = ws / "state.json"
    segments_file = ws / "segments.json"

    state_file.write_text(json.dumps({
        "schema_version": 1,
        "stages": {"download": {"status": "done"}, "asr": {"status": "done"}}
    }), encoding="utf-8")

    segments_file.write_text(json.dumps({
        "schema_version": 1,
        "segments": [{"id": 1, "start": 0.0, "end": 2.0, "vi_text": "Chào bạn"}]
    }), encoding="utf-8")

    changed = migrate_job_state(ws)
    assert changed is True

    # Verify migrated state
    new_state = json.loads(state_file.read_text(encoding="utf-8"))
    assert new_state["schema_version"] == 2
    assert "download" not in new_state["stages"]

    new_segs = json.loads(segments_file.read_text(encoding="utf-8"))
    assert new_segs["schema_version"] == 2
    assert "cues" in new_segs["segments"][0]

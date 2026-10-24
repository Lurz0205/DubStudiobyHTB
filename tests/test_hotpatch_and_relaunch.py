"""Tests for Job Object Breakaway, Hot-Patch Dynamic Override, and SHA-256 Checksum Integrity."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

from dubstudio.hotpatch import (
    HotpatchMetaPathFinder,
    apply_hotpatches,
    verify_patch_manifest,
)
from dubstudio.updater import verify_file_checksum
from dubstudio.win_job import (
    CREATE_BREAKAWAY_FROM_JOB,
    DETACHED_PROCESS,
    JOB_OBJECT_LIMIT_BREAKAWAY_OK,
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    init_job_object,
    launch_breakaway_process,
)


def test_win_job_breakaway_flags_and_launch():
    """Verify Job Object limit flags combine KILL_ON_JOB_CLOSE and BREAKAWAY_OK."""
    expected_limit = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_BREAKAWAY_OK
    assert expected_limit == (0x00002000 | 0x00000800)
    assert CREATE_BREAKAWAY_FROM_JOB == 0x01000000
    assert DETACHED_PROCESS == 0x00000008

    # Test initialization
    h_job = init_job_object()
    if sys.platform == "win32":
        assert h_job is not None

    # Test launch_breakaway_process spawning a trivial process
    proc = launch_breakaway_process([sys.executable, "-c", "import sys; sys.exit(0)"])
    proc.wait(timeout=5)
    assert proc.returncode == 0


def test_verify_file_checksum(tmp_path: Path):
    """Verify SHA-256 and byte-size integrity checks."""
    dummy_file = tmp_path / "test_artifact.bin"
    content = b"DubStudio Velopack Release Artifact Verification Test 12345"
    dummy_file.write_bytes(content)

    correct_sha = hashlib.sha256(content).hexdigest()
    correct_size = len(content)

    # 1. Matching size and SHA-256
    assert verify_file_checksum(dummy_file, expected_sha256=correct_sha, expected_size=correct_size) is True

    # 2. Matching SHA-256 case-insensitively without size
    assert verify_file_checksum(dummy_file, expected_sha256=correct_sha.upper()) is True

    # 3. Mismatched size
    assert verify_file_checksum(dummy_file, expected_sha256=correct_sha, expected_size=correct_size + 10) is False

    # 4. Mismatched SHA-256
    wrong_sha = "0000000000000000000000000000000000000000000000000000000000000000"
    assert verify_file_checksum(dummy_file, expected_sha256=wrong_sha, expected_size=correct_size) is False


def test_hotpatch_manifest_verification(tmp_path: Path):
    """Verify hot-patch integrity validation against patch_manifest.json."""
    patch_dir = tmp_path / "1.1.2"
    patch_dir.mkdir(parents=True, exist_ok=True)

    code_file = patch_dir / "dubstudio" / "dummy_mod.py"
    code_file.parent.mkdir(parents=True, exist_ok=True)
    code_bytes = b"DUMMY_VALUE = 42\n"
    code_file.write_bytes(code_bytes)

    sha = hashlib.sha256(code_bytes).hexdigest()
    manifest_data = {
        "base_version": "1.1.2",
        "patch_id": "patch_001",
        "files": {
            "dubstudio/dummy_mod.py": sha
        }
    }
    (patch_dir / "patch_manifest.json").write_text(json.dumps(manifest_data), encoding="utf-8")

    # Correct version and hashes
    assert verify_patch_manifest(patch_dir, "1.1.2") is True

    # Wrong version (e.g. upgraded to 1.1.3)
    assert verify_patch_manifest(patch_dir, "1.1.3") is False

    # Tampered file
    code_file.write_bytes(b"TAMPERED = 999\n")
    assert verify_patch_manifest(patch_dir, "1.1.2") is False


def test_hotpatch_meta_path_finder(tmp_path: Path):
    """Verify HotpatchMetaPathFinder intercepts and loads modules ahead of frozen archive."""
    patch_dir = tmp_path / "patch_root"
    mod_dir = patch_dir / "dubstudio"
    mod_dir.mkdir(parents=True, exist_ok=True)

    patched_file = mod_dir / "patched_feature.py"
    patched_file.write_text("FEATURE_FLAG = 'HOTPATCH_ACTIVE'\n", encoding="utf-8")

    finder = HotpatchMetaPathFinder(patch_dir)
    sys.meta_path.insert(0, finder)

    try:
        import dubstudio.patched_feature  # type: ignore
        assert getattr(dubstudio.patched_feature, "FEATURE_FLAG") == "HOTPATCH_ACTIVE"
    finally:
        if finder in sys.meta_path:
            sys.meta_path.remove(finder)
        sys.modules.pop("dubstudio.patched_feature", None)


def test_active_models_status_dynamic_choice(monkeypatch):
    """Verify _get_active_models_status checks ONLY the active models selected by the user."""
    from ui.main_window import MainWindow
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    # 1. SenseVoice-Small chosen
    monkeypatch.setenv("WHISPER_MODEL", "sensevoice-small")
    monkeypatch.setenv("SEPARATION_MODEL", "Kim_Vocal_2.onnx")

    win = MainWindow()
    _, info, missing = win._get_active_models_status()
    assert info["asr_pkg"] == "sensevoice_small"
    assert info["asr_name"] == "SenseVoice-Small"
    assert info["sep_pkg"] == "kim_vocal_2"
    assert not any("large-v3" in m for m in missing)
    assert not any("BS-RoFormer" in m for m in missing)

    # 2. User switches dropdown to faster-whisper large-v3 and BS-RoFormer
    idx_asr = win._settings_page._combo_asr_model.findData("large-v3")
    win._settings_page._combo_asr_model.setCurrentIndex(idx_asr)
    idx_sep = win._settings_page._combo_sep_model.findData("model_bs_roformer_ep_317_sdr_12.9755.ckpt")
    win._settings_page._combo_sep_model.setCurrentIndex(idx_sep)

    _, info2, _ = win._get_active_models_status()
    assert info2["asr_pkg"] == "whisper_large_v3"
    assert info2["asr_name"] == "faster-whisper large-v3"
    assert info2["sep_pkg"] == "bs_roformer"
    assert info2["sep_name"] == "BS-RoFormer EP 317"

    win.close()

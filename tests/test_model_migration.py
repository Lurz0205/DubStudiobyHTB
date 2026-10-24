"""Tests for Smart Multi-Path Model Migration and Path Rebinding."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import pytest

from dubstudio.paths import (
    migrate_legacy_user_data,
    get_model_search_paths,
    find_model_file,
    find_model_dir,
)
from dubstudio.components import is_component_ready, get_installed_components


def test_merge_move_model_migration_and_cleanup(tmp_path: Path):
    """
    Test migrating legacy models to DubStudioData:
    - Avoids FileExistsError when target folder already exists.
    - Successfully moves models file-by-file.
    - Deletes source files and cleans up empty legacy directories (zero disk bloat).
    """
    legacy_dir = tmp_path / "AppData" / "Local" / "DubStudio"
    target_dir = tmp_path / "AppData" / "Local" / "DubStudioData"

    # Pre-create target models folder (simulate app already started once)
    (target_dir / "models").mkdir(parents=True, exist_ok=True)

    # Create dummy legacy model: SenseVoiceSmall/model.pt (size = 105 MB dummy)
    legacy_model_dir = legacy_dir / "models" / "SenseVoiceSmall"
    legacy_model_dir.mkdir(parents=True, exist_ok=True)
    legacy_model_file = legacy_model_dir / "model.pt"

    # Write a dummy model file > 100MB using seek to be fast and sparse
    with open(legacy_model_file, "wb") as f:
        f.seek(101 * 1024 * 1024 - 1)
        f.write(b"\0")

    # Create legacy installed.json pointing to legacy path
    legacy_components_dir = legacy_dir / "components"
    legacy_components_dir.mkdir(parents=True, exist_ok=True)
    legacy_installed_file = legacy_components_dir / "installed.json"
    legacy_installed_data = {
        "sensevoice_small": {
            "version": 1,
            "path": str((legacy_dir / "models" / "SenseVoiceSmall").resolve()),
            "status": "ready"
        }
    }
    legacy_installed_file.write_text(json.dumps(legacy_installed_data), encoding="utf-8")

    # Run migration explicitly between mock folders
    migrate_legacy_user_data(legacy_dir=legacy_dir, target_dir=target_dir)

    # 1. Assert target file exists and is intact
    target_model_file = target_dir / "models" / "SenseVoiceSmall" / "model.pt"
    assert target_model_file.exists(), "Model file was not moved to target directory!"
    assert target_model_file.stat().st_size == 101 * 1024 * 1024

    # 2. Assert legacy model file and folder were wiped out (preventing duplicate disk usage)
    assert not legacy_model_file.exists(), "Legacy model file was not removed!"
    assert not legacy_model_dir.exists(), "Legacy model directory was not cleaned up!"

    # 3. Assert path rebinding in installed.json
    target_installed_file = target_dir / "components" / "installed.json"
    assert target_installed_file.exists(), "installed.json was not migrated!"
    rebound_data = json.loads(target_installed_file.read_text(encoding="utf-8"))
    rebound_path = rebound_data["sensevoice_small"]["path"]
    assert "DubStudioData" in rebound_path, f"Path was not rebound: {rebound_path}"
    assert "DubStudio\\models" not in rebound_path


def test_size_aware_merge_preserves_larger_file(tmp_path: Path):
    """
    If destination already has an incomplete/smaller file, the larger source file overwrites it.
    If destination has equal or larger file, the source file is deleted.
    """
    legacy_dir = tmp_path / "legacy"
    target_dir = tmp_path / "target"

    legacy_model = legacy_dir / "models" / "test.onnx"
    legacy_model.parent.mkdir(parents=True, exist_ok=True)
    legacy_model.write_bytes(b"A" * 2000)

    # Case 1: Target has 100 bytes (incomplete download)
    target_model = target_dir / "models" / "test.onnx"
    target_model.parent.mkdir(parents=True, exist_ok=True)
    target_model.write_bytes(b"B" * 100)

    migrate_legacy_user_data(legacy_dir=legacy_dir, target_dir=target_dir)

    assert target_model.exists()
    assert target_model.stat().st_size == 2000
    assert not legacy_model.exists()

    # Case 2: Target already has larger file (3000 bytes)
    target_model.write_bytes(b"C" * 3000)
    legacy_model.parent.mkdir(parents=True, exist_ok=True)
    legacy_model.write_bytes(b"D" * 500)

    migrate_legacy_user_data(legacy_dir=legacy_dir, target_dir=target_dir)

    assert target_model.stat().st_size == 3000
    assert not legacy_model.exists()


def test_get_model_search_paths_includes_all_candidates():
    """Verify get_model_search_paths returns prioritized non-empty list."""
    paths = get_model_search_paths()
    assert len(paths) >= 1
    # First candidate should always be get_models_dir()
    from dubstudio.paths import get_models_dir
    assert paths[0].resolve() == get_models_dir().resolve()


def test_find_model_file_helper(tmp_path: Path, monkeypatch):
    """Test helper find_model_file locates model across candidate paths."""
    mock_models_dir = tmp_path / "mock_models"
    mock_models_dir.mkdir(parents=True, exist_ok=True)
    test_file = mock_models_dir / "my_model.bin"
    test_file.write_bytes(b"dummy")

    monkeypatch.setattr("dubstudio.paths.get_model_search_paths", lambda: [mock_models_dir])

    found = find_model_file("my_model.bin")
    assert found is not None
    assert found.resolve() == test_file.resolve()

    not_found = find_model_file("non_existent.bin")
    assert not_found is None


def test_is_component_ready_with_fallback_search(tmp_path: Path, monkeypatch):
    """Verify is_component_ready detects models placed in legacy fallback search paths."""
    legacy_models = tmp_path / "legacy_search" / "models"
    sensevoice_dir = legacy_models / "SenseVoiceSmall"
    sensevoice_dir.mkdir(parents=True, exist_ok=True)
    model_file = sensevoice_dir / "model.pt"

    with open(model_file, "wb") as f:
        f.seek(101 * 1024 * 1024 - 1)
        f.write(b"\0")

    monkeypatch.setattr(
        "dubstudio.paths.get_model_search_paths",
        lambda: [tmp_path / "empty_models", legacy_models]
    )

    ready, msg = is_component_ready("sensevoice_small")
    assert ready is True
    assert msg == "Đã sẵn sàng"

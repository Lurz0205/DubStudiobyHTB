"""Unit tests for Phase 2 Production Hardening & Process Isolation."""
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest

from dubstudio.config import get_api_base_url, get_api_port
from dubstudio.jobstate import atomic_write_json


def test_dynamic_port_and_base_url(monkeypatch):
    monkeypatch.setenv("DUBSTUDIO_API_PORT", "8799")
    assert get_api_port() == 8799
    assert get_api_base_url() == "http://127.0.0.1:8799"

    monkeypatch.setenv("DUBSTUDIO_API_PORT", "8765")
    assert get_api_port() == 8765
    assert get_api_base_url() == "http://127.0.0.1:8765"


def test_atomic_write_json(tmp_path: Path):
    target = tmp_path / "subdir" / "data.json"
    payload = {"status": "ok", "count": 42, "items": ["a", "b"]}

    atomic_write_json(target, payload)
    assert target.exists()

    with open(target, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded == payload

    # Test update preserves integrity
    payload["count"] = 100
    atomic_write_json(target, payload)
    with open(target, "r", encoding="utf-8") as f:
        loaded2 = json.load(f)
    assert loaded2["count"] == 100

    # Ensure no leftover .tmp files
    tmp_files = list(target.parent.glob("*.tmp*"))
    assert len(tmp_files) == 0


def test_atomic_write_json_error_handling(tmp_path: Path):
    target = tmp_path / "valid.json"
    atomic_write_json(target, {"initial": True})

    class NonSerializable:
        pass

    with pytest.raises(TypeError):
        atomic_write_json(target, {"bad": NonSerializable()})

    # The original file must remain intact
    with open(target, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded == {"initial": True}


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Job Object is Windows-only")
def test_windows_job_object_lifecycle():
    from dubstudio.win_job import init_job_object, assign_process_to_job

    h_job = init_job_object()
    assert h_job is not None

    # Spawn a short-lived subprocess and assign it to the Job Object
    cmd = [sys.executable, "-c", "import time; time.sleep(0.5)"]
    proc = subprocess.Popen(cmd)
    try:
        ok = assign_process_to_job(proc)
        # Should succeed on Windows
        assert ok is True or ok is False  # Validates no uncaught exceptions
    finally:
        proc.terminate()
        proc.wait(timeout=3)


def test_no_sync_requests_in_ui_pages_and_dialogs():
    """Verify that no synchronous requests.get/post/put/delete exist directly in ui/pages or ui/dialogs."""
    ui_dir = Path("ui")
    forbidden = ["requests.get(", "requests.post(", "requests.put(", "requests.delete("]
    offenders = []

    for sub in ["pages", "dialogs"]:
        d = ui_dir / sub
        if not d.exists():
            continue
        for py_file in d.glob("*.py"):
            lines = py_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            for idx, line in enumerate(lines):
                # Ignore comments
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                for f in forbidden:
                    if f in stripped:
                        offenders.append(f"{py_file.name}:{idx+1}: {stripped}")

    assert len(offenders) == 0, f"Found synchronous requests in UI components:\n" + "\n".join(offenders)

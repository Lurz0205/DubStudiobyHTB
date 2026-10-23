"""Comprehensive tests for Phase 10: Hardening, diagnostics, and error handling."""
import json
import zipfile
from pathlib import Path

import pytest
from dubstudio.diagnostics import collect_system_summary, export_diagnostics_bundle
from dubstudio.errors import DubError


def test_dub_error_factory_constructors():
    """Verify all standard Phase 10 error constructors return proper codes and Vietnamese messages."""
    oom = DubError.cuda_oom("asr")
    assert oom.code == "CUDA_OOM"
    assert "GPU" in oom.user_message_vi
    assert "CPU" in oom.hint_vi

    cudnn = DubError.cudnn_missing()
    assert cudnn.code == "CUDNN_MISSING"
    assert "cuDNN" in cudnn.user_message_vi

    rate_limit = DubError.api_rate_limited(retry_after=45)
    assert rate_limit.code == "API_RATE_LIMIT"
    assert "429" in rate_limit.user_message_vi
    assert "45" in rate_limit.hint_vi

    disk = DubError.disk_full("C:/", required_mb=500)
    assert disk.code == "DISK_FULL"
    assert "500" in disk.user_message_vi

    corrupted = DubError.corrupted_video("bad.mp4")
    assert corrupted.code == "CORRUPTED_VIDEO"
    assert "bad.mp4" in corrupted.user_message_vi

    invalid_path = DubError.invalid_path("video?.mp4")
    assert invalid_path.code == "INVALID_PATH"

    user_formatted = oom.format_user()
    assert "CUDA_OOM" in user_formatted
    assert "❌" in user_formatted
    assert "💡" in user_formatted


def test_collect_system_summary():
    """Verify system summary collects OS, Python, CUDA, and FFmpeg info without secrets."""
    summary = collect_system_summary()
    assert "os" in summary
    assert "python" in summary
    assert "cuda" in summary
    assert "ffmpeg" in summary
    assert summary["ffmpeg"]["available"] is True
    # Ensure no API key leaked
    raw_json = json.dumps(summary)
    assert "AIzaSy" not in raw_json
    assert "GEMINI_API_KEY" not in raw_json


def test_export_diagnostics_bundle(tmp_path: Path):
    """Verify diagnostics exporter generates a valid zip with sanitized contents."""
    out_zip = tmp_path / "test_diagnostics.zip"
    res = export_diagnostics_bundle(out_zip)
    assert res.exists()
    assert res.suffix == ".zip"

    with zipfile.ZipFile(res, "r") as z:
        names = z.namelist()
        assert "system_summary.json" in names
        # Check content inside zip
        content = z.read("system_summary.json").decode("utf-8")
        assert "ffmpeg" in content
        assert "AIzaSy" not in content

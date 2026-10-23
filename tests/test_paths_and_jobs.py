"""Unit tests for centralized paths, bundled external tools, and system diagnostics."""
from pathlib import Path
import pytest

from dubstudio.paths import (
    get_app_dir,
    get_bin_dir,
    get_logs_dir,
    get_models_dir,
    get_workspace_dir,
    resolve_tool,
)
from dubstudio.diagnostics import check_system_prerequisites, collect_system_summary


def test_paths_resolution():
    """Verify paths resolve to valid directories without crashing."""
    assert get_app_dir().exists()
    assert get_logs_dir().exists()
    assert get_models_dir().exists()
    assert get_workspace_dir().exists()


def test_bundled_tools_resolution():
    """Verify ffmpeg and ffprobe resolve to bundled bin/ executables."""
    ffmpeg_exe = Path(resolve_tool("ffmpeg"))
    ffprobe_exe = Path(resolve_tool("ffprobe"))
    assert ffmpeg_exe.exists()
    assert ffprobe_exe.exists()
    assert ffmpeg_exe.name.lower().startswith("ffmpeg")
    assert ffprobe_exe.name.lower().startswith("ffprobe")


def test_check_system_prerequisites():
    """Verify prerequisite checks pass when components are ready, and fail gracefully when missing."""
    from unittest.mock import patch
    with patch("dubstudio.components.is_component_ready", return_value=(True, "Đã sẵn sàng")):
        ok, title, msg = check_system_prerequisites(task="subtitles")
        assert ok is True
        assert title == ""

    with patch("dubstudio.components.is_component_ready", return_value=(False, "Chưa tải")):
        ok, title, msg = check_system_prerequisites(task="subtitles")
        assert ok is False
        assert "Chưa tải mô hình" in title


def test_collect_system_summary_structure():
    """Verify system summary contains all required keys and valid tool paths."""
    summary = collect_system_summary()
    assert summary["ffmpeg"]["available"] is True
    assert summary["ffprobe"]["available"] is True
    assert Path(summary["ffmpeg"]["path"]).exists()
    assert Path(summary["ffprobe"]["path"]).exists()

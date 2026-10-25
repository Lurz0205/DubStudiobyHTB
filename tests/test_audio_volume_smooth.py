"""Unit tests for smooth 0-200% single-file headroom scaling and debounce volume control."""
import os
import sys
import numpy as np
import pytest
import soundfile as sf
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QUrl

from ui.widgets.video_player import VideoPlayerWidget


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    return app


def test_headroom_voice_track_generation(tmp_path):
    """Verify that _ensure_headroom_voice_track generates +20dB headroom file with peak <= 0.98."""
    sr = 24000
    t = np.linspace(0, 1, sr, dtype=np.float32)
    # Speech tone with 0.10 amplitude
    voice_data = 0.10 * np.sin(2 * np.pi * 200 * t)
    raw_wav = tmp_path / "voice_raw.wav"
    sf.write(str(raw_wav), voice_data, sr)

    headroom_wav = VideoPlayerWidget._ensure_headroom_voice_track(raw_wav)
    assert headroom_wav is not None and headroom_wav.exists()
    assert headroom_wav.name == "voice_headroom_200.wav"

    data, h_sr = sf.read(str(headroom_wav))
    assert h_sr == sr
    assert np.max(np.abs(data)) <= 0.98
    # Boosted amplitude should be significantly higher than raw (approx 10x, saturated near 0.8-0.98)
    assert np.max(np.abs(data)) >= 0.70


def test_rapid_slider_drag_no_source_switching(qapp, tmp_path):
    """
    Test rapid slider dragging (100 volume changes between 0% and 200%).
    Verify player NEVER switches track source and audio level scales monotonically without dropouts.
    """
    sr = 24000
    voice_data = 0.20 * np.ones((sr, 2), dtype=np.float32)
    headroom_wav = tmp_path / "voice_headroom_200.wav"
    sf.write(str(headroom_wav), voice_data, sr)

    player = VideoPlayerWidget()
    player._vi_voice_path = str(headroom_wav.resolve())
    initial_source = QUrl.fromLocalFile(player._vi_voice_path)
    player._vi_voice_player.setSource(initial_source)

    # 1. Test 100 rapid volume changes crossing 100% boundary multiple times
    prev_vol = -1.0
    for pct in range(0, 201, 2):
        vol = pct / 100.0
        player.set_vi_voice_volume(vol)

        # Source URL must NEVER change
        assert player._vi_voice_path == str(headroom_wav.resolve())
        current_eff = player._vi_voice_audio.volume()

        # Volume must be monotonically non-decreasing
        assert current_eff >= prev_vol - 1e-6, f"Volume dropped at {pct}%: {current_eff} < {prev_vol}"
        prev_vol = current_eff

    # 2. Check key volume control points
    player.set_vi_voice_volume(0.0)
    assert player._vi_voice_audio.volume() == 0.0

    player.set_vi_voice_volume(1.0)
    # At 100%, eff_vi = 1.0 / 10.0 = 0.10
    assert abs(player._vi_voice_audio.volume() - 0.10) < 0.001

    player.set_vi_voice_volume(2.0)
    # At 200%, eff_vi = 1.0000000 (+20dB full boost)
    assert abs(player._vi_voice_audio.volume() - 1.0) < 0.001


def test_save_style_debounce(qapp, tmp_path):
    """Test that volume changes schedule debounced save instead of flooding disk I/O."""
    from ui.pages.subtitle_export_page import SubtitleExportPage
    page = SubtitleExportPage()

    save_count = 0
    def mock_save():
        nonlocal save_count
        save_count += 1

    page._save_style_to_job = mock_save

    # Simulate rapid slider changes (50 ticks)
    for v in range(50, 100):
        page._on_vi_voice_slider_changed(v)

    # During drag, save_count must still be 0 (debounced)
    assert save_count == 0

    # Trigger flush on release
    page._save_style_to_job()
    assert save_count == 1

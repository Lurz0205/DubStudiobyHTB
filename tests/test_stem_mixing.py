import numpy as np
import pytest
import soundfile as sf
from pathlib import Path
from PyQt6.QtWidgets import QApplication
import sys

from ui.widgets.video_player import VideoPlayerWidget


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_boosted_tracks_generation_and_stem_volumes(tmp_path, qapp):
    sr = 24000
    dur = 1.0
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    sine = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

    raw_voice = tmp_path / "voice_raw.wav"
    sf.write(str(raw_voice), sine, sr)

    bgm_wav = tmp_path / "bgm.wav"
    sf.write(str(bgm_wav), np.column_stack([sine, sine]), sr)

    # 1. Test voice headroom generator
    boosted_voice = VideoPlayerWidget._ensure_boosted_voice_track(raw_voice)
    assert boosted_voice is not None
    assert boosted_voice.exists()
    assert "200" in boosted_voice.name

    # 2. Test bgm track generator
    boosted_bgm = VideoPlayerWidget._ensure_boosted_bgm_track(bgm_wav)
    assert boosted_bgm is not None
    assert boosted_bgm.exists()

    # 3. Test volume math on player (Single-file headroom scaling)
    player = VideoPlayerWidget()
    player._vi_voice_path = str(boosted_voice)
    player._orig_bgm_path = str(boosted_bgm)

    # Test vi_voice: at 100% (nominal reference), volume is 0.10 (100% raw amplitude). At 200%, volume is 1.0 (+20dB boost)
    player.set_vi_voice_volume(1.0)
    assert abs(player._vi_voice_audio.volume() - 0.10) < 0.01

    player.set_vi_voice_volume(1.5)
    assert player._vi_voice_audio.volume() > 0.10 and player._vi_voice_audio.volume() < 1.0

    player.set_vi_voice_volume(2.0)
    assert abs(player._vi_voice_audio.volume() - 1.0) < 0.01

    player.set_vi_voice_volume(0.0)
    assert player._vi_voice_audio.isMuted() or abs(player._vi_voice_audio.volume() - 0.0) < 0.01

    # On raw track, 100% -> exactly 1.0 (100% original amplitude, no attenuation)
    player._vi_voice_path = str(raw_voice)
    player._vi_voice_raw_path = str(raw_voice)
    player.set_vi_voice_volume(1.0)
    assert abs(player._vi_voice_audio.volume() - 1.0) < 0.01

    # Test BGM 80% vs 100% vs 200%
    player.set_orig_bgm_volume(0.8)
    assert abs(player._orig_bgm_audio.volume() - 0.8) < 0.02

    player.set_orig_bgm_volume(1.0)
    assert abs(player._orig_bgm_audio.volume() - 1.0) < 0.02

    player.set_orig_bgm_volume(2.0)
    assert abs(player._orig_bgm_audio.volume() - 1.0) < 0.01

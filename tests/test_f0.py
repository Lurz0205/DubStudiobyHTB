import numpy as np
import pytest
import soundfile as sf
from dubstudio.audio.f0 import detect_gender_from_f0, estimate_median_f0


def test_f0_gender_detection(tmp_path):
    sr = 16000
    dur = 1.0
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)

    # 1. Male pitch: 120 Hz sine wave
    male_wave = 0.5 * np.sin(2 * np.pi * 120.0 * t)
    male_file = tmp_path / "male_120hz.wav"
    sf.write(str(male_file), male_wave, sr)

    male_f0 = estimate_median_f0(str(male_file), 0.0, dur, sr_target=sr)
    assert 110.0 <= male_f0 <= 130.0
    assert detect_gender_from_f0(male_f0) == "male"

    # 2. Female pitch: 220 Hz sine wave
    female_wave = 0.5 * np.sin(2 * np.pi * 220.0 * t)
    female_file = tmp_path / "female_220hz.wav"
    sf.write(str(female_file), female_wave, sr)

    female_f0 = estimate_median_f0(str(female_file), 0.0, dur, sr_target=sr)
    assert 210.0 <= female_f0 <= 230.0
    assert detect_gender_from_f0(female_f0) == "female"

"""F0 fundamental frequency estimation using autocorrelation for speaker gender detection."""
import numpy as np
import soundfile as sf


def estimate_median_f0(audio_path: str, start_sec: float, end_sec: float, sr_target: int = 16000) -> float:
    """Estimate median fundamental frequency (F0 in Hz) using autocorrelation."""
    try:
        data, sr = sf.read(audio_path)
    except Exception:
        return 0.0

    if data.ndim > 1:
        data = data.mean(axis=1)

    start_idx = max(0, int(start_sec * sr))
    end_idx = min(len(data), int(end_sec * sr))
    chunk = data[start_idx:end_idx]

    if len(chunk) < int(0.1 * sr):  # require at least 100ms
        return 0.0

    # Frame-based autocorrelation
    frame_len = int(0.04 * sr)  # 40ms frame
    hop_len = int(0.02 * sr)    # 20ms hop
    f0_list = []

    # Human voice F0 search range: 60 Hz to 400 Hz
    min_lag = int(sr / 400)
    max_lag = int(sr / 60)

    for i in range(0, len(chunk) - frame_len, hop_len):
        frame = chunk[i:i + frame_len]
        # Energy check: skip silence
        if np.mean(frame ** 2) < 1e-4:
            continue

        # Autocorrelation
        corr = np.correlate(frame, frame, mode="full")
        corr = corr[len(frame) - 1:]

        if max_lag >= len(corr):
            continue

        # Search peak within [min_lag, max_lag]
        search_region = corr[min_lag:max_lag]
        if len(search_region) == 0:
            continue

        peak_idx = np.argmax(search_region) + min_lag
        # Check if peak is significant compared to lag 0
        if corr[0] > 0 and (corr[peak_idx] / corr[0]) > 0.3:
            f0 = sr / peak_idx
            f0_list.append(f0)

    if not f0_list:
        return 0.0

    return float(np.median(f0_list))


def detect_gender_from_f0(median_f0: float, threshold_hz: float = 165.0) -> str:
    """Classify gender: male if F0 < threshold_hz, female if F0 >= threshold_hz, or unknown if 0."""
    if median_f0 <= 0.0:
        return "unknown"
    return "female" if median_f0 >= threshold_hz else "male"

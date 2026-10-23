"""Benchmark VieNeu-TTS preset voices on 5 standard Vietnamese sentences."""
import os
from pathlib import Path
import sys
import time
import soundfile as sf

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["PYTHONUTF8"] = "1"
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from scripts.hwprofile import profile_hw

SENTENCES = [
    "Xin chào các bạn, hôm nay chúng ta sẽ cùng khám phá một vùng đất mới.",
    "Bộ phim này kể về cuộc đời đầy sóng gió của một vị tướng tài ba thời xưa.",
    "Dự báo thời tiết ngày mai khu vực phía Bắc có mưa rào và dông vài nơi.",
    "Công nghệ trí tuệ nhân tạo đang thay đổi cách con người làm việc và giải trí mỗi ngày.",
    "Cảm ơn quý vị khán giả đã chú ý theo dõi video của chúng tôi, hẹn gặp lại!",
]


def main():
    try:
        from vieneu import Vieneu
    except ImportError:
        print("Lỗi: Chưa cài đặt thư viện 'vieneu'. Hãy chạy: pip install vieneu")
        return

    out_dir = Path("out/bench_tts")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Đang khởi tạo mô hình VieNeu-TTS...")
    engine = Vieneu()

    # Get available preset voices from engine
    if hasattr(engine, "_preset_voices") and engine._preset_voices:
        voices = list(engine._preset_voices.keys()) if isinstance(engine._preset_voices, dict) else list(engine._preset_voices)
    else:
        voices = ["Quỳnh Anh", "Mai Anh", "Minh Đức", "Hải Đăng"]

    print(f"Danh sách giọng nói có sẵn: {voices}")

    # Select representative voices (both female and male)
    selected_voices = [v for v in ["Quỳnh Anh", "Mai Anh", "Minh Đức", "Hải Đăng"] if v in voices]
    if not selected_voices:
        selected_voices = voices[:4]

    summary_rows = []
    total_chars = sum(len(s) for s in SENTENCES)

    for voice_name in selected_voices:

        print(f"\n--- Benchmark giọng: {voice_name} ---")
        voice_out_dir = out_dir / voice_name.replace(" ", "_")
        voice_out_dir.mkdir(parents=True, exist_ok=True)

        total_audio_sec = 0.0

        with profile_hw(interval_sec=0.2) as prof:
            for i, sent in enumerate(SENTENCES, 1):
                t0 = time.perf_counter()
                audio = engine.infer(sent, voice=voice_name)
                t_gen = time.perf_counter() - t0

                wav_path = voice_out_dir / f"sent_{i}.wav"
                engine.save(audio, str(wav_path))

                # Calculate duration of output audio
                info = sf.info(str(wav_path))
                total_audio_sec += info.duration
                print(f"  Câu {i} ({len(sent)} ký tự) -> {info.duration:.2f}s âm thanh (tạo mất {t_gen:.2f}s)")

        cps = total_chars / total_audio_sec if total_audio_sec > 0 else 0.0
        summary_rows.append({
            "voice": voice_name,
            "wall_time": f"{prof.wall_time_s:.2f}s",
            "audio_duration": f"{total_audio_sec:.2f}s",
            "chars_per_sec": f"{cps:.2f} chars/s",
            "peak_ram": f"{prof.peak_ram_mb:.1f} MB",
            "peak_vram": f"{prof.peak_vram_mb:.1f} MB",
        })

    print("\n| Giọng nói | Wall time | Tổng âm thanh | Tốc độ (chars/s) | Peak RAM | Peak VRAM |")
    print("|---|---|---|---|---|---|")
    for r in summary_rows:
        print(f"| {r['voice']} | {r['wall_time']} | {r['audio_duration']} | {r['chars_per_sec']} | {r['peak_ram']} | {r['peak_vram']} |")


if __name__ == "__main__":
    main()

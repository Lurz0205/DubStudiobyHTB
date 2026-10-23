# PROGRESS.md — DubStudio Progress

## Đã hoàn thành (Done)
- **Giai đoạn 1 & 2:**
  - Tách rời môi trường `start.bat` & `DubStudio.exe`.
  - Sửa lỗi tốc độ giọng đọc, đồng bộ phụ đề 100%, dọn ổ đĩa > 6.1 GB.
  - Windows Job Object kernel (`KILL_ON_JOB_CLOSE`), Dynamic Port & Readiness Gate, loại bỏ hoàn toàn requests đồng bộ trên UI, Atomic JSON Write.
- **Giai đoạn 3 (VRAM Lifecycle, FFmpeg Job Guard & Release Pipeline):**
  - Mở rộng Job Guard 100% cho `ffmpeg`/`ffprobe` qua `safe_subprocess_run`/`safe_subprocess_popen` (`packaging.py`, `ffmpeg_utils.py`, `render.py`, `mix.py`).
  - Stage Mutex trên 4GB VRAM: giải phóng persistent TTS worker trước khi chạy `separate`/`asr`, gọi `gc.collect()` + `torch.cuda.empty_cache()` sau mỗi stage nặng.
  - Chống lỗi `WinError 32`: ghi audio preview qua file tạm + replace nguyên tử, tự động dọn dẹp file `.tmp` khi đóng job (`video_player.py`).
  - Tối ưu đóng gói: chặn `modelscope`, `funasr`, `torch`... trong `DubStudio.spec`, đưa Watchdog về nhịp 250ms (0% CPU khi app nghỉ).
  - 139/139 unit tests pass 100% (`pytest tests/ -q`). Đã đóng gói lại `dist\DubStudio\DubStudio.exe`, selftest code 0, đã push GitHub `main` (commit `cf158b9`).

## Tiếp theo (Next)
- Người dùng kiểm tra trực tiếp trên bản build mới nhất `dist\DubStudio\DubStudio.exe`.

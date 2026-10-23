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
  - Khắc phục trạng thái mô hình: kiểm tra vật lý tệp mô hình trên đĩa (`components.py`), tự động dọn bản ghi rác trong `installed.json`.
  - Nâng cấp nút "Kiểm tra cập nhật": kiểm tra GitHub release, kiểm tra gói cập nhật, và xác thực trực tiếp xem các mô hình đang chọn làm việc trong Cài đặt (ASR, tách nhạc, TTS) đã tải chưa. Cảnh báo và chuyển hướng 1-click vào Cài đặt nếu thiếu.
  - Hỗ trợ tải tự động trọn gói cho `whisper_large_v3` & `sensevoice_small` qua HuggingFace Hub snapshot.
  - 140/140 unit tests pass 100% (`pytest tests/ -q`). Rebuild `dist\DubStudio\DubStudio.exe` hoàn tất, selftest code 0 (Commit `eb21870`).
- **Giai đoạn 4 & Bản phát hành v1.1.0 (Beta Release):**
  - Khắc phục triệt để `[WinError 10013]` qua `WindowsSelectorEventLoopPolicy` & `asyncio.new_event_loop()` riêng trong thread uvicorn, loại bỏ lỗi socketpair/Proactor.
  - Sửa lỗi mất tiếng preview video: Khi tạo dự án mới chưa có track tách nhạc/lồng tiếng, tự động giữ nguyên âm thanh gốc của video ở mức 100% thay vì mute nhầm sang chế độ multi-track.
  - Pre-flight Model Gate: Kiểm tra tính sẵn sàng thực tế của `model.pt` (>100MB), chặn ngay từ UI nếu đang tải dở hoặc chưa tải, loại bỏ hoàn toàn hiện tượng trọng số ngẫu nhiên sinh text ảo.
  - Khóa tải đơn tiến trình toàn cục (`_GLOBAL_DOWNLOADING_LOCK`): Triệt tiêu nguy cơ tải trùng lặp hoặc xung đột đa tiến trình khi người dùng tương tác liên tục.
  - Tải streaming 256KB trực tiếp vào thư mục tạm `.staging_*`, hủy tức thì <0.1s, dọn sạch rác khi tắt/mở app.
  - Nâng cấp phiên bản lên `v1.1.0`, build lại `dist\DubStudio\DubStudio.exe` hoàn chỉnh (Selftest Exit Code: 0).
  - Đạt 145/145 unit tests passed (100%). Đẩy commit `0d3a78f` và Tag `v1.1.0` lên GitHub Actions Azure để tự động đóng gói Velopack.

## Tiếp theo (Next)
- Bạn có thể chạy thử trực tiếp `dist\DubStudio\DubStudio.exe` trên máy để nghiệm thu.

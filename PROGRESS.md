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
- **Giai đoạn 4 (Đồng bộ Bản vá Thực tế & Đại trùng tu Giao diện Cinema Dark Studio):**
  - Đồng bộ và bảo vệ 100% bản vá thực tế của chủ dự án, mở rộng guard chặn tải ngầm ở cả `separate` (`DubError("MODEL_NOT_FOUND")`).
  - Đại trùng tu toàn diện giao diện "Cinema Dark Studio" (`ui/theme.py`): chuẩn màu `#0B0D13`, `#11141D`, `#171B26`, Accent Indigo `#6366F1`, Emerald `#10B981`, viền mảnh `#262C3A`, bo góc 10px, typography Segoe UI Variable / Inter.
  - Nâng cấp bảng `SubtitleEditor`: hàng 38px chuẩn tiếng Việt, kẻ ngang siêu mảnh, màu xen kẽ, highlight dòng đang phát.
  - Nâng cấp `VideoPlayerWidget`: khung video đen tuyền `#000000`, controls bar dạng Card studio đồng bộ.
  - Benchmark chuyển tab đạt hiệu năng cao (< 35 ms, 0% CPU khi nghỉ).
  - 143/143 unit tests pass 100% (`pytest tests/ -q`). Rebuild `dist\DubStudio\DubStudio.exe`, selftest code 0 (Commit `9b7c14d`).

## Tiếp theo (Next)
- Người dùng kiểm tra trực tiếp trên bản build mới nhất `dist\DubStudio\DubStudio.exe`.

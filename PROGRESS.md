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
- **Giai đoạn 4 (Bản phát hành v1.1.0 & Fix lỗi ASR SenseVoice):**
  - Khắc phục triệt để `[WinError 10013]` socketpair, sửa lỗi mất tiếng preview video (`video_player.py`), chặn tiền kiểm tạo lồng tiếng khi chưa có phụ đề.
  - Sửa lỗi `[ASR_FAILED]` của SenseVoice (`NOT_FOUND: "None"`): Tự động nạp `bpemodel` (`chn_jpn_yue_eng_ko_spectok.bpe.model`), đồng bộ `bpe.model` và tích hợp VAD offline cục bộ (`fsmn-vad`).
  - Dọn dẹp 100% cache cũ, chuyển cache dịch thuật & co giãn sang phạm vi dự án (`job.workspace/.cache`) giúp xóa dự án là xóa sạch cache, không bị lưu phụ đề cũ.
  - Đạt 145/145 unit tests passed (100%). Đã đồng bộ trực tiếp vào `dist\DubStudio\DubStudio.exe`. Chế độ đóng gói độc lập pass `sim_user_machine.ps1`.

## Quy trình Phát hành & Cập nhật vi sai (Release & Patch Workflow)
- **Bản gốc Baseline:** `v1.1.0` đã được đóng gói đầy đủ trên GitHub Releases (`Setup.exe`, `full.nupkg`).
- **Môi trường phát triển:** Mọi commit sửa lỗi hàng ngày chỉ đẩy lên branch `main` (`push_code_to_github.py`), tuyệt đối **không tự ý tạo tag hay ghi đè bản release cũ**.
- **Quy trình xuất bản Patch:** Khi tích lũy đủ các bản sửa lỗi, chỉ cần nâng version (ví dụ `1.1.1`) và chạy `python scripts/push_code_to_github.py --tag v1.1.1`. GitHub Actions sẽ tự động tạo `delta.nupkg` để máy người dùng tự động cập nhật vi sai nhẹ nhàng qua Velopack.

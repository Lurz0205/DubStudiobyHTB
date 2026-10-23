# PROGRESS.md — DubStudio Progress

## Đã hoàn thành (Done)
- **Giai đoạn 1 & Hotfixes:**
  - Tách rời triệt để môi trường `start.bat` (dev) và `DubStudio.exe` (packaged).
  - Sửa lỗi âm thanh đọc lúc nhanh lúc chậm (bỏ slowdown 0.90x, clamp 1.10x).
  - Sửa lỗi lệch/mất phụ đề khi dịch (`_persist_disk` đồng bộ 100% `segments.json`).
  - Dọn dẹp ổ đĩa giải phóng > 6.1 GB.
- **Giai đoạn 2 (Production Hardening & Process Isolation):**
  - Quản lý vòng đời tiến trình con qua Windows Job Object (`dubstudio/win_job.py`, `KILL_ON_JOB_CLOSE` 0x2000), chống rò rỉ VRAM/tiến trình mồ côi.
  - Tự động gán Job Object cho TTS worker server và background pipeline subprocesses.
  - Dynamic Port & Readiness Gate: loại bỏ URL fix cứng, thêm retry thông minh cho các lỗi kết nối/500 lúc server khởi động.
  - Loại bỏ 100% các lệnh `requests.*` đồng bộ trên toàn bộ `ui/` (`manual_translate_dialog`, `welcome_tutorial_dialog`, `settings_page`).
  - Bảo toàn dữ liệu dự án: chuẩn hóa `atomic_write_json` (ghi `.tmp` -> `fsync` -> `os.replace`), chống file JSON 0 byte.
  - Bắt lỗi toàn cục `setup_global_exception_handler()` (`sys.excepthook`) ghi log và hiện thông báo thân thiện.
  - 135/135 unit tests pass (`pytest tests/ -q`). Đã đóng gói lại `dist\DubStudio\DubStudio.exe`, selftest code 0, đã push GitHub `main` (commit `090226a`).

## Tiếp theo (Next)
- Người dùng kiểm tra thực tế trên `dist\DubStudio\DubStudio.exe`.

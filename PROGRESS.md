# PROGRESS.md — DubStudio Progress

## Đã hoàn thành (Done)
- **Cơ chế Nhắc nhở Mô hình Chính xác theo Người dùng Chọn:**
  - Nhận diện đúng mô hình người dùng chọn trong Hướng dẫn (Tutorial) và Cài đặt (Settings), chỉ kiểm tra và cảnh báo đúng mô hình đó.
  - Khi người dùng đổi sang mô hình khác (SenseVoice <-> Whisper, Kim Vocal 2 <-> BS-RoFormer) mà chưa tải, hệ thống lập tức thông báo nhắc tải gói tương ứng.
- **Hot-Patch System & Safe Relaunch (Agent B Architecture):**
  - **Mở khóa Breakaway Job Object (`dubstudio/win_job.py`):** Bật `JOB_OBJECT_LIMIT_BREAKAWAY_OK`, cho phép tiến trình cập nhật/khởi động lại sống sót độc lập sau khi app chính thoát.
  - **Hot-Patch nạp động ngoài `_internal/` (`dubstudio/hotpatch.py`):** Lưu tại `%LocalAppData%\DubStudioData\hotpatch\<VERSION>`, ưu tiên nạp qua `HotpatchMetaPathFinder` vượt `PyiFrozenImporter`.
  - **Xác thực SHA-256 & Kích thước (`dubstudio/updater.py`):** Kiểm tra mã băm và dung lượng trước khi giải nén/chạy Setup.exe, hủy bỏ ngay nếu rớt mạng hỏng file.
  - **Graceful Shutdown & Wait-for-PID:** Dừng worker, media player, chờ PID cũ biến mất khỏi Windows kernel (tối đa 10s) rồi mới chạy `Setup.exe -s` và bật lại app.
  - Đạt 100% unit tests (`tests/test_hotpatch_and_relaunch.py`, `tests/test_fit.py`, `tests/test_api.py`).

## Tiếp theo (Next)
- Đợi lệnh của người dùng để build/đẩy bản vá lên GitHub khi sẵn sàng.

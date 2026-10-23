# PROGRESS.md — DubStudio Progress

## Đã hoàn thành (Done)
- **Giai đoạn 1, 2 & 3:**
  - Tách rời `start.bat` & `DubStudio.exe`. Windows Job Object kernel (`KILL_ON_JOB_CLOSE`), Dynamic Port & Readiness Gate, Atomic JSON Write.
  - Stage Mutex trên 4GB VRAM, chống lỗi `WinError 32`, tự động tải mô hình qua HuggingFace Hub.
- **Giai đoạn 4 (Patch v1.1.0 & v1.1.1):**
  - Khắc phục `[WinError 10013]` socketpair, sửa lỗi mất tiếng preview video (`video_player.py`), chặn tiền kiểm tạo lồng tiếng khi chưa có phụ đề.
  - Dọn dẹp cache cũ, chuyển cache dịch sang phạm vi dự án (`job.workspace/.cache`).
- **Giai đoạn 5 (Patch v1.1.2 — Trình cập nhật chuẩn & Ổn định ASR):**
  - **Trình cập nhật 3 tầng (Triple-Tier Fallback Updater):** Chạy ngầm `CheckUpdatesWorker` không đơ UI, so sánh phiên bản chuẩn SemVer `parse_semver`, Velopack delta patch + tự động stream tải `Setup.exe` nguyên tử kèm thanh tiến trình `0% - 100%` (MB/MB) và hộp thoại xác nhận khởi động lại ứng dụng.
  - **Khắc phục SenseVoice & Kiểm tra mô hình:** Tắt triệt để thông báo nhắc tải Whisper khi người dùng đang chọn SenseVoice. Chuyển language="zh" tối ưu tiếng Trung có code-switching tiếng Anh.
  - **Khôi phục Fit Rewriter:** Tự động kích hoạt CDP nền với Edge/Chrome khi sửa các đoạn TTS bị chèn nhau.
  - **Ghim phiên bản cố định:** Hiển thị v{VERSION} (Dev / Packaged) ở góc dưới thanh trạng thái.
  - Đạt 150/150 unit tests pass 100% (`pytest tests/ -q`).

## Quy trình Phát hành & Cập nhật vi sai (Release & Patch Workflow)
- **Bản gốc Baseline:** `v1.1.0` đã được phát hành trên GitHub.
- **Bản Patch v1.1.2:** Đẩy code lên `main` và gắn tag `v1.1.2`, kích hoạt GitHub Actions build `DubStudio-1.1.2-delta.nupkg` và `DubStudio-win-Setup.exe`.
- **Người dùng bản cũ (v1.1.0 / v1.1.1):** Trình updater mới tải trực tiếp Setup.exe hoặc chạy installer cài đè mượt mà không mất dữ liệu, từ bản v1.1.2 trở đi ứng dụng sẽ tự động vá vi sai mượt mà.

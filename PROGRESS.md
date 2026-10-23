# PROGRESS.md — v1.0.1 Freeze & Watchdog Fixes

## Đã hoàn thành (Done)
- Áp dụng trọn vẹn 5 giải pháp khử đơ Main Thread:
  - Thêm `get_shared_session()` với `trust_env=False` và Connection Pooling chống quét Windows Proxy Registry.
  - Tắt `access_log=False` trong Uvicorn FastAPI để không nghẽn stream I/O trên Windows subsystem.
  - Cố định `QT_MEDIA_BACKEND=windows` và `NO_PROXY=127.0.0.1,localhost` tại đầu `start_app.py`.
  - Bổ sung `stdin=subprocess.DEVNULL` và `CREATE_NO_WINDOW` vào `get_subprocess_kwargs()`.
  - Tích hợp `start_gui_freeze_watchdog(threshold_sec=0.5)` tự động ghi log `gui_freeze_dump.log` nếu GUI bị khựng > 0.5s.
- Fix Gemini Web CDP: quét trực tiếp khối code `<pre>` JSON từ DOM, bỏ điều kiện cứng đếm panel.
- Đồng bộ toàn bộ mã nguồn lên GitHub `main` và cập nhật trực tiếp vào `dist\DubStudio`.
- Kiểm thử máy khách: `DubStudio Selftest: OK` (Exit Code: 0).

## Tiếp theo (Next)
- Người dùng test mở `DubStudio.exe` trong `dist` và thực hiện dịch video để kiểm tra độ mượt.



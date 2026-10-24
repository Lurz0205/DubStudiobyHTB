# PROGRESS.md — DubStudio Progress

## Đã hoàn thành (Done)
- **Sửa dứt điểm lỗi xuất video (500 Server Error) & lỗi port 127.0.0.1:**
  - Tìm ra nguyên nhân: Hàm `render_job_video` trong `dubstudio/api/app.py` thiếu khai báo `cfg = AppConfig.load()`, làm phát sinh ngoại lệ `NameError: name 'cfg' is not defined` khi lấy đường dẫn xuất video.
  - Sửa toàn diện `app.py`: Đã bổ sung `cfg = AppConfig.load()` cho tất cả các endpoint liên quan (`render_job_video`, `split_segment`, `regenerate_segment_tts`) và thay thế `logger` bằng `_api_logger`.
  - Khắc phục `ui/workers.py`:
    + Cấu hình `TestClient(app, raise_server_exceptions=False)` trong In-Memory ASGI Bridge, trả về đầy đủ mã lỗi và dữ liệu phản hồi thay vì làm sập tiến trình gọi hoặc fallback sang TCP socket.
    + Trích xuất thông điệp tiếng Việt thân thiện (`message_vi`) và loại bỏ hoàn toàn các chuỗi URL IP/Port khỏi thông báo lỗi người dùng.
- **Xác thực toàn diện quy trình:**
  - Test trực tiếp 5 luồng cốt lõi (Cài đặt, Danh sách tác vụ, Chi tiết tác vụ, Quản lý phụ đề, Xuất video) đều đạt 200 OK.
  - Video mẫu `out/24102026_vi.mp4` được kết xuất hoàn chỉnh thành công.
- 100% kiểm thử tự động đã vượt qua (`164/164 passed`). Đã đồng bộ mã nguồn sang `dist/`.

## Tiếp theo (Next)
- Đóng gói và phát hành bản vá mới khi người dùng yêu cầu.

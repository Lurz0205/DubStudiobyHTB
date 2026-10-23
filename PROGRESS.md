# PROGRESS.md — v1.0.1 Patch

## Đã hoàn thành (Done)
- **Khôi phục triệt để cơ chế chống đè giọng TTS (Anti-Overlap)**:
  - Khôi phục tính năng xê dịch các cặp câu bị đè cô lập tới lui tối đa 0.5s (`resolve_isolated_pair_shifts`) tận dụng khoảng lặng trước và sau.
  - Cắt và vuốt đuôi âm thanh mượt mà 50ms (`enforce_audio_boundary`), triệt tiêu 100% hiện tượng nói đè giọng trên timeline ở cả `fit.py`, `mix.py`, `video_player.py` và `app.py`.
  - Cập nhật bản thảo Release Note v1.0.1 trên GitHub ngắn gọn, súc tích.
- **Sửa triệt để lỗi Port [WinError 10013] & Xử lý Tiến trình Zombie**:
  - Tự động dò tìm cổng khả dụng với `find_available_port(8765)`.
  - `closeEvent` gọi `os._exit(0)` đảm bảo đóng app là tắt sạch 100% tiến trình con.
- **Tối ưu dung lượng & Dọn dẹp dự án**:
  - Xóa hơn 2.5 GB rác build tạm thời (`build/`, `dist/DubStudio/`, `__pycache__`).
  - Toàn bộ 130/130 unit tests vượt qua 100%.

## Tiếp theo (Next)
- Người dùng kiểm tra nghe thử trên app, sau đó tiến hành build và upload bản phát hành v1.0.1.

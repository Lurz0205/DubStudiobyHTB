# PROGRESS.md — DubStudio Progress

## Đã hoàn thành (Done)
- **1. Sửa lỗi lặp vô hạn dịch/tạo lại TTS câu 27 28:**
  - `fit.py`: Tính toán và lưu đúng `tts_hash = _calc_seg_hash(...)` và `tts_file` khi viết lại câu (`fit_rewrite`) thay vì đặt `tts_hash = None`, chấm dứt vòng lặp bị `tts.py` đánh dấu bẩn (dirty) ở lần chạy sau.
  - `fit.py`: Bỏ ghi đè dữ liệu đoạn thoại vào `units.json` (ngăn làm sai lệch input_hash của bước dịch `translate.py`).
  - `start_app.py`: Chuẩn hóa khoảng trắng (`re.sub(r'\s+', ' ', ...)`) khi kiểm tra `text_changed`, tránh nhận nhầm việc xuống dòng phụ đề thành thay đổi nội dung; tự động phục hồi `tts_hash` khi tệp WAV đã tồn tại hợp lệ.
  - `tts.py`: Bổ sung cơ chế tự phục hồi (self-healing), tự động gán `tts_hash` nếu tệp WAV trên ổ đĩa đã có sẵn và hợp lệ.
- **2. Xóa sạch dự án cũ theo yêu cầu:**
  - Đã xóa hoàn toàn thư mục `%LocalAppData%\DubStudioData\workspace\douyinsaver_com-7700450994269719843_1793271092`.
- **3. Kiểm thử & Đóng gói:**
  - `pytest tests/ -q` đạt 100% PASS (191 passed, 10 skipped).
  - Đóng gói hoàn tất `dist\DubStudio\DubStudio.exe`, selftest passed (Exit 0).

## Tiếp theo (Next)
- Theo dõi trải nghiệm thực tế khi người dùng chạy các video mới.

## Vấn đề mở (Open issues)
- Không có lỗi tồn đọng.

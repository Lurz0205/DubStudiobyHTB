# DubStudio v2.0.3 — Bản Vá Lỗi Toàn Diện: Khắc Phục Lặp Dịch & Tạo Lại TTS, Bảo Toàn Bộ Nhớ Đệm Âm Thanh

Bản cập nhật bảo trì **DubStudio v2.0.3** tập trung khắc phục triệt để lỗi logic phát sinh khi xử lý các câu thoại bị tràn thời lượng âm thanh, đảm bảo quy trình lồng tiếng và dịch thuật không bị lặp đi lặp lại những câu không thay đổi:

---

### 🌟 Các Điểm Nâng Cấp & Sửa Lỗi Chính Trên v2.0.3:

#### 1. Triệt Tiêu Lỗi Lặp Dịch & Tạo Lại TTS Đối Với Câu Tràn Thời Lượng
- **Nguyên nhân:** Khi một câu thoại có độ dài âm thanh vượt ngưỡng an toàn (>1.18x), thuật toán `fit.py` kích hoạt cơ chế rút gọn câu (`fit_rewrite`). Sau khi tạo âm thanh mới, hệ thống đặt `seg["tts_hash"] = None`. Ở lần bấm "Tạo lồng tiếng" kế tiếp, `tts.py` thấy mã băm bị rỗng nên đánh dấu câu là bị "bẩn" (dirty) và tổng hợp lại âm thanh, tạo ra vòng lặp vô tận khiến câu đó luôn bị đem ra xử lý lại.
- **Giải pháp trên v2.0.3:**
  - Bổ sung hàm băm `_calc_seg_hash` trực tiếp vào `fit.py`. Ngay sau khi câu thoại được viết lại và tạo âm thanh mới, hệ thống tính toán và lưu trữ chính xác `tts_hash` cùng đường dẫn `tts_file`.
  - Loại bỏ hoàn toàn thao tác ghi đè mảng `segments` vào `units.json` trong `fit.py`, ngăn chặn việc làm sai lệch mã băm kiểm toán `input_hash` của bước dịch thuật `translate.py`.

#### 2. Chuẩn Hóa So Khớp Lời Thoại Khi Đồng Bộ Dự Án (`save_project_segments`)
- **Nguyên nhân:** Việc so sánh chuỗi nguyên bản giữa giao diện và tệp trên đĩa vô tình xem các ký tự ngắt dòng `\n` của dòng phụ đề là sự thay đổi nội dung, dẫn đến việc xóa bỏ bộ nhớ đệm âm thanh và mã băm `tts_hash` của câu thoại.
- **Giải pháp trên v2.0.3:** Sử dụng biểu thức chuẩn hóa khoảng trắng (`re.sub(r'\s+', ' ', ...)`) trước khi xác định cờ thay đổi `text_changed`. Đồng thời bổ sung cơ chế tự động khôi phục `tts_hash` nếu tệp âm thanh `.wav` trên đĩa đã tồn tại và hợp lệ.

#### 3. Cơ Chế Tự Phục Hồi Bộ Nhớ Đệm Âm Thanh (Self-Healing TTS Cache)
- Tại `tts.py`, nếu tệp `.wav` đã tồn tại và có kích thước hợp lệ trên đĩa nhưng vì lý do nào đó `tts_hash` bị trống, hệ thống sẽ tự động gán mã băm tương ứng và đánh dấu đoạn thoại là sạch (clean), tránh gọi lại mô hình AI tổng hợp âm thanh không cần thiết.

---

### 📋 Hướng Dẫn Cập Nhật & Nâng Cấp:
- **Tự động cập nhật:** Ứng dụng tích hợp công nghệ cập nhật thông minh (Velopack). Khi mở ứng dụng, hệ thống sẽ tự động thông báo và tải gói nâng cấp delta nhỏ gọn.
- **Người dùng mới hoặc cài lại:** Tải tệp `DubStudio-win-Setup.exe` ở phần Assets bên dưới và cài đặt tự động trong 1 click. Toàn bộ các dự án và mô hình AI đã tải trong máy đều được giữ nguyên 100% tại `%LocalAppData%\DubStudioData`.

---

### 🛡️ Bảng Kiểm Toán & Thông Số Kỹ Thuật (Technical Audit & Checksums)

- **Phiên bản:** `v2.0.3`
- **Mốc so sánh đối chiếu:** `v2.0.2`
- **Kiến trúc:** Windows 64-bit (x64) | Local-first Desktop Application
- **Công nghệ cốt lõi:** PyWebView + React 19 + Tailwind CSS v4 + FastAPI In-Memory Bridge + Windows Native GDI + FFmpeg 7.1 + Velopack
- **Trạng thái kiểm thử:** 191 passed, 10 skipped (100% Test Suite Passed)

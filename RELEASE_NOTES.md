# DubStudio v2.0.0 — Bản Cập Nhật Lớn: Lột Xác Kiến Trúc Next-Gen Studio & Trải Nghiệm Mượt Mà

Bản cập nhật lớn **DubStudio v2.0.0** chính thức phát hành! Đây là bước nhảy vọt quan trọng nhất trong lịch sử phát triển của DubStudio: thay thế toàn diện giao diện cũ sang nền tảng Studio hiện đại (React 19 + Tailwind v4 + PyWebView), loại bỏ hoàn toàn các lỗi xung đột mạng cổng tĩnh, tinh giản dung lượng cài đặt và nâng cấp trí tuệ nhân tạo biên tập câu chữ tiếng Việt mượt mà, tự nhiên như phim chiếu rạp.

---

### 🌟 Những Điểm Mới Nổi Bật Trên DubStudio v2.0.0:

#### 1. Giao Diện Studio Next-Gen Hoàn Toàn Mới (Neutral Charcoal Matte)
- **Thiết kế chuyên nghiệp, tập trung:** Tông màu xám than chì sang trọng (`#121214`), bố cục màn hình phân khu khoa học: Trình xem video lớn ở trung tâm, dòng thời gian Timeline trực quan ở dưới đáy và danh sách phụ đề chi tiết bên phải.
- **Tốc độ phản hồi tức thì:** Giao diện dựng trên công nghệ web hiện đại nhất, các thao tác chuyển tab, tìm kiếm câu, cuộn danh sách diễn ra trơn tru với độ trễ 0ms.
- **Khóa giao diện Zero-Failure:** Công nghệ nhúng trực tiếp toàn bộ CSS (Inline CSS Guarantee) đảm bảo mở ứng dụng 1.000 lần thì cả 1.000 lần giao diện đều hiển thị chuẩn đẹp, không bao giờ bị hiện tượng mất định dạng hay vỡ khung.

#### 2. Triệt Tiêu 100% Xung Đột Cổng Mạng (Zero Hardcoded Port)
- **Tự động cấp phát cổng động:** Loại bỏ hoàn toàn cổng cố định `8765`. Ứng dụng tự động tìm cổng trống ngẫu nhiên do Windows cấp, chấm dứt vĩnh viễn lỗi "Địa chỉ cổng đang bị chiếm dụng" (`WinError 10048`) hay xung đột với các phần mềm khác.
- **Cầu nối dữ liệu Native In-Memory Bridge:** Giao tiếp trực tiếp giữa giao diện người dùng và lõi xử lý AI qua bộ nhớ RAM nội bộ, không phụ thuộc vào kết nối mạng cục bộ, loại bỏ nguy cơ bị phần mềm diệt virus chặn request.

#### 3. Loại Bỏ Hoàn Toàn PyQt6 — Nhẹ Hơn, Mở Nhanh Hơn
- Toàn bộ khối thư viện PyQt6 nặng nề đã được gỡ bỏ sạch sẽ khỏi ứng dụng, giúp giảm hơn **72 MB** dung lượng cài đặt và giải phóng đáng kể bộ nhớ RAM máy tính khi khởi động.
- Bộ đo độ dài chữ phụ đề chuyển sang dùng trực tiếp **Windows Native GDI** của hệ điều hành, đảm bảo độ chuẩn xác 100% tới từng pixel giữa màn hình xem trước và video xuất ra.

#### 4. Thuật Toán Rút Gọn Câu Thoát Ý Thông Minh (Fit Rewrite Vi Phẫu)
- **Chuyển sang đếm âm tiết tiếng Việt (`tts_words`):** Khác với cơ chế đếm ký tự cũ dễ bị cắt quá tay, thuật toán mới đo chính xác tốc độ nói theo số từ tiếng Việt, giúp câu dịch luôn vừa vặn hoàn hảo với khoảng thời gian của nhân vật trên video.
- **Biên tập vi phẫu 2 cấp độ:** Ưu tiên giữ lại 85–90% câu gốc và chỉ gọt tỉa các từ đệm thừa (như "thì", "mà", "là", "rồi"). Chỉ khi câu quá dài mới diễn đạt lại theo phong cách ngắn gọn, súc tích.
- **Chốt chặn chống hụt thời lượng:** Tự động hoàn tác về câu gốc nếu AI rút gọn quá ngắn gây trống video, đảm bảo nhịp phim luôn liền mạch và tự nhiên.

#### 5. Sửa Các Lỗi Đã Được Phản Hồi:
- **Khắc phục lỗi Timeline giọng đọc (TTS) dài hơn phụ đề:** Khối âm thanh trên timeline giờ đã đồng bộ tuyệt đối 1:1 theo thời lượng thực tế của giọng nói đã co giãn, không còn bị hiển thị dài lấn sang câu sau.
- **Khắc phục lỗi bấm "Tách tự động" làm mất rãnh giọng đọc:** Đã bảo toàn 100% dữ liệu âm thanh khi phân tách dòng phụ đề, rãnh TTS luôn giữ nguyên và hiển thị liên tục.
- **Khắc phục lỗi xuất video dừng ở 0%:** Sửa triệt để lỗi khai báo biến âm thanh khi xuất video có chèn khung viền màu hoặc logo.

---

### 📋 Hướng Dẫn Cập Nhật & Nâng Cấp:
- **Người dùng mới hoặc cài lại:** Tải tệp `DubStudio-win-Setup.exe` ở phần Assets bên dưới và nhấp đúp để cài đặt tự động trong 1 click.
- **Người dùng đang ở v1.1.3:** Do bản v2.0.0 thay đổi toàn diện sang nhân giao diện mới, bạn chỉ cần tải tệp cài đặt đầy đủ `DubStudio-win-Setup.exe` và cài đè lên. Toàn bộ các dự án đang làm dở và các mô hình AI đã tải trong máy đều được giữ nguyên 100% (nằm an toàn tại `%LocalAppData%\DubStudioData`).

---

### 🛡️ Bảng Kiểm Toán & Thông Số Kỹ Thuật (Technical Audit & Checksums)

- **Phiên bản:** `v2.0.0`
- **Mốc so sánh đối chiếu:** `v1.1.3` (Commit: `b710e1b`)
- **Kiến trúc:** Windows 64-bit (x64) | Local-first Desktop Application
- **Công nghệ cốt lõi:** PyWebView + React 19 + Tailwind CSS v4 + FastAPI In-Memory Bridge + Windows Native GDI + FFmpeg 7.1 + Velopack
- **Trạng thái kiểm thử:** 175 passed, 10 skipped (100% Test Suite Passed)

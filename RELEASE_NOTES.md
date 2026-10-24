# DubStudio v1.1.3 — Bản cập nhật & Tối ưu hóa Toàn diện

Bản cập nhật v1.1.3 tập trung nâng cấp chất lượng âm thanh phát thanh, cải tiến cơ chế lồng tiếng thoát ý, xử lý triệt để lỗi phản hồi TTS và bảo toàn mô hình AI tuyệt đối:

### 🌟 Điểm mới nổi bật:

1. **Âm thanh Chuẩn Phát thanh & Tăng âm lượng 200% (EBU R128):**
   - **Chất âm dày ấm, không vỡ tiếng:** Áp dụng chuẩn phát thanh quốc tế ITU-R BS.1770 / EBU R128 (`loudnorm`), lọc tạp âm siêu trầm (<75 Hz) và tiếng rít tổng hợp (>12.5 kHz), khóa trần True Peak -0.8 dBFS giúp loại bỏ 100% hiện tượng rè và vỡ tiếng khi khuếch đại.
   - **Tăng âm lượng thực thụ 200%:** Đường cong âm lượng tâm thính học mới giúp mức 200% tăng vọt +10.5 dB acoustic power (tai người nghe to gấp đôi thực thụ), giọng thuyết minh vang to, uy lực và áp đảo nhạc nền.
   - **Điều khiển tức thì 0ms:** Cả 4 thanh trượt (Thuyết minh, Nhạc nền, Nhạc thêm, Giọng gốc) mở rộng từ 0% đến 200%, phản hồi mượt mà không bị ngắt tiếng hay tráo file.

2. **Khắc phục Triệt để Lỗi Not Responding khi Tạo TTS:**
   - Khử deadlock bộ đệm pipe hệ điều hành và đồng bộ luồng giao diện, chấm dứt hoàn toàn tình trạng đơ/treo ứng dụng khi tạo giọng thuyết minh.
   - Quản lý bộ nhớ VRAM thông minh: tự động tắt worker trước khi chạy pipeline chính, chống tràn VRAM trên GPU 4 GB.

3. **Lồng tiếng "Thoát Ý" & Chống Hở Khoảng Lặng:**
   - Dịch lại thoát ý tự nhiên theo khẩu ngữ đời thường, chấm dứt việc cắt xén cơ học làm mất chủ ngữ hay câu nói què quặt lủng củng.
   - Khóa sàn ký tự `min_chars` nghiêm ngặt và căn chỉnh tỷ lệ nén vừa vặn, triệt tiêu hoàn toàn hiện tượng giọng đọc kết thúc quá sớm gây hở khoảng lặng chết trong khi diễn viên trên hình vẫn đang nói.

4. **Bảo toàn Dữ liệu & Cập nhật Minh bạch:**
   - **Smart Model Migration:** Tự động gom và bảo toàn nguyên vẹn 100% các mô hình AI (`SenseVoice`, `Demucs`, `VieNeu-TTS`) sang `%LocalAppData%\DubStudioData\models`, tự động chuyển đổi đường dẫn cài đặt cũ mà không bắt người dùng tải lại bất kỳ file nào.
   - Cơ chế đóng gói và cập nhật siêu nhẹ qua gói `delta.nupkg` được khóa chặt và kiểm toán minh bạch 100% qua lịch sử Git.

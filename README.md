# DubStudio — Trình Lồng Tiếng Video AI (Trung -> Việt)

**DubStudio** là ứng dụng desktop Windows giúp tự động chuyển đổi video tiếng Trung sang video lồng tiếng Việt kèm phụ đề tự động (ASS). Toàn bộ các mô hình AI hạng nặng (nhận dạng giọng nói faster-whisper, tách nhạc nền BS-RoFormer, tạo giọng đọc AI VieNeu-TTS) đều hoạt động trực tiếp, tối ưu hóa phần cứng GPU cục bộ, đảm bảo tính riêng tư và miễn phí.

---

## Tính năng nổi bật trong bản v1.0.0 Beta

- **Nhận dạng giọng nói ASR chuẩn xác**:
  - Hỗ trợ mô hình **`faster-whisper large-v3`** (khuyên dùng): Cho độ chính xác rất cao, cần thời gian xử lí lâu.
  - Hỗ trợ mô hình **`faster-whisper large-v3-turbo`**: Xử lý nhanh gấp 2 lần, nhẹ RAM/VRAM cho video dài.
  - Xem chi tiết so sánh hai mô hình trong mục **Cài đặt**.
- **Dịch thuật AI linh hoạt theo ngữ cảnh**:
  - **Gemini Web (Trình duyệt độc lập)**: Hoạt động bằng gemini web, miễn phí không cần API Key.
  - **Groq Cloud API**: Tốc độ dịch nhanh với Qwen 2.5 nhưng thỉnh thoảng bị lỗi Timeout do API giới hạn số lần yêu cầu trong một khoảng thời gian.
- **Thuyết minh AI VieNeu-TTS Offline**:
  - Tích hợp sẵn nhiều giọng đọc Nam/Nữ Bắc - Nam, chạy hoàn toàn offline không tốn phí.
  - Tự động cân chỉnh tempo, chống đè giọng và tái tạo câu thoại thông minh.
- **Biên tập Phụ đề & Video chuyên nghiệp**:
  - Tự do kéo thả, định vị phụ đề, che chữ gốc với khối màu, khắc cứng phụ đề ASS chất lượng cao.
  - Cắt ghép nhiều video, khuếch đại âm lượng thoại rõ nét.

---

## Yêu cầu hệ thống

- **Hệ điều hành**: Windows 10 hoặc Windows 11 (64-bit).
- **Bộ nhớ (RAM)**: Tối thiểu 8 GB (khuyến nghị 12 GB trở lên).
- **Đồ họa (GPU)**: Khuyến nghị card NVIDIA (RTX 2050 / GTX 1650 trở lên với CUDA) để đạt tốc độ xử lý nhanh nhất. Máy không có GPU rời vẫn chạy được chế độ CPU.

---

## Hướng dẫn cài đặt & Khởi động nhanh

1. **Cài đặt**:
   - Tải file **`DubStudio-win-Setup.exe`** từ mục [Releases](https://github.com/Lurz0205/DubStudiobyHTB/releases) và nhấp đúp để cài đặt.
   - Ứng dụng tự động tạo lối tắt trên Desktop và Menu Start.
2. **Hướng dẫn thiết lập ban đầu**:
   - Khi mở ứng dụng lần đầu, giao diện hướng dẫn sẽ xuất hiện để bạn chọn mô hình nhận dạng giọng nói (`large-v3` hoặc `large-v3-turbo`) và phương thức dịch thuật mong muốn.
3. **Thực hiện lồng tiếng**:
   - Vào tab **Dự án**, bấm **`Tạo dự án mới`** để chọn video tiếng Trung từ máy tính.
   - Nhấn **`Chạy lồng tiếng`** để AI tự động thực hiện bóc băng, dịch thuật và đọc thuyết minh.
   - Chỉnh sửa phụ đề/giọng đọc theo ý thích và bấm **`Xuất video`**.

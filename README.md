# DubStudio — Trình Lồng Tiếng & Biên Tập Video AI (Trung -> Việt)

**DubStudio** là ứng dụng desktop chuyên nghiệp giúp chuyển đổi video tiếng Trung sang video lồng tiếng Việt kèm phụ đề tự động. Toàn bộ các mô hình AI (nhận dạng lời nói ASR, tách giọng vocal/BGM, tổng hợp giọng nói TTS, căn khớp khẩu hình) đều **chạy offline hoàn toàn trên máy tính cá nhân**, chỉ sử dụng mạng duy nhất cho API dịch thuật (Google Gemini).

---

## 🚀 Tính năng nổi bật

- 🎙️ **Mô hình TTS Tiếng Việt Offline (VieNeu-TTS v3 Turbo)**: Tích hợp sẵn 25 giọng đọc tự nhiên (Nam/Nữ, 3 miền Bắc - Trung - Nam) chạy siêu tốc với cơ chế Warm Worker (~1s/câu).
- 🎬 **Giao diện Desktop Chuyên Nghiệp (PyQt6 NLE Style)**:
  - **Màn hình xem trước**: Trình phát video đồng bộ âm thanh chuẩn `QtMultimedia`.
  - **Bảng phụ đề chi tiết**: Cho phép gõ sửa văn bản, đổi giọng đọc, chỉnh tốc độ phát từng câu và bấm tạo lại âm thanh ngay lập tức.
  - **Timeline trực quan**: Thước đo thời gian kéo thả dời mốc bắt đầu/kết thúc câu thoại và giọng đọc.
  - **Khung phụ đề trên video**: Kéo thả chuột tự do (Drag & Drop) và co dãn kích thước trực tiếp, tùy biến nền mờ (Backdrop blur).
- 📥 **Bộ công cụ tích hợp**:
  - Tải video từ YouTube, Douyin, Bilibili (hỗ trợ cookies).
  - Ghép nối nhiều clip video với tính năng sắp xếp thứ tự và stream copy hoặc re-encode.
- ⚙️ **Quản lý cài đặt an toàn**: Cấu hình API Key Gemini và giọng đọc mặc định được lưu vĩnh viễn, bảo mật (ẩn key).

---

## 💻 Yêu cầu hệ thống

- **Hệ điều hành**: Windows 10/11 64-bit.
- **Python**: Phiên bản **Python 3.11** (Bắt buộc).
- **Phần cứng**:
  - RAM: Tối thiểu 8 GB - 12 GB.
  - GPU: Card đồ họa NVIDIA (khuyến nghị RTX 2050 4GB VRAM trở lên) có hỗ trợ CUDA.
- **Công cụ phụ trợ**: `ffmpeg` đã được thêm vào biến môi trường PATH.

---

## 🛠️ Hướng dẫn cài đặt từ đầu (Fresh Clone)

### 1. Tạo môi trường ảo Python 3.11
Mở PowerShell tại thư mục dự án:
```powershell
py -3.11 -m venv .venv
```

### 2. Cài đặt PyTorch CUDA
```powershell
.venv\Scripts\pip.exe install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

### 3. Cài đặt các thư viện phụ thuộc
```powershell
.venv\Scripts\pip.exe install -r requirements.txt
```

### 4. Kiểm tra môi trường
```powershell
.venv\Scripts\python.exe scripts/check_env.py
```

---

## 🎯 Hướng dẫn khởi chạy ứng dụng

### Cách 1: Bấm đúp chuột 1-Click (Khuyến nghị)
Nhấp đúp chuột vào file:
👉 **`start.bat`**

### Cách 2: Khởi chạy bằng dòng lệnh
```powershell
.venv\Scripts\python.exe start_app.py
```

---

## 📖 Hướng dẫn quy trình sử dụng

1. **Thiết lập API Key dịch thuật**:
   - Chuyển sang tab **Cài đặt (⚙️)**.
   - Nhập Gemini API Key từ Google AI Studio (bắt đầu bằng `AIzaSy...`).
   - Chọn giọng Nam và giọng Nữ mặc định, sau đó nhấn **Lưu cài đặt**.
2. **Thêm video cần lồng tiếng**:
   - Ở tab **Studio (🎬)**, nhấn nút **`+ Thêm video`** và chọn file video `.mp4` hoặc `.mkv` trên máy tính.
   - Hoặc dùng tab **Tải xuống (⬇️)** dán link Bilibili/Douyin/YouTube để tải về thư mục `samples`.
3. **Chạy lồng tiếng tự động**:
   - Nhấn **`⚡ Chạy lồng tiếng`** trên thanh công cụ Studio.
   - Hệ thống sẽ tự động tách âm thanh -> nhận dạng tiếng Trung -> AI phân tích ngữ cảnh -> dịch thuật -> tạo giọng đọc tiếng Việt -> căn khớp nhịp điệu và xuất video thành phẩm vào thư mục `out/`.
4. **Biên tập & Tinh chỉnh (Fine-tuning)**:
   - Nghe thử từng câu trong bảng phụ đề.
   - Nếu muốn câu nào đọc giọng khác hoặc nhanh/chậm hơn, chỉnh lại ở cột **Giọng** hoặc **Tốc độ**, sau đó bấm nút **`🔄 Tạo`**.
   - Dùng chuột kéo các thanh phụ đề trên **Timeline** ở nửa dưới để khớp chuẩn xác nhất với hình ảnh.

---

## 🩺 Xử lý sự cố & Xuất chẩn đoán (Diagnostics)

Mọi lỗi phát sinh đều hiển thị thông báo tiếng Việt kèm gợi ý khắc phục cụ thể:
- **Lỗi CUDA OOM (Tràn VRAM)**: Hệ thống tự động chuyển tải xuống CPU. Hãy đóng các app đồ họa nặng khác.
- **Lỗi 429 Rate Limit**: Chờ 1-2 phút hoặc đổi API key Gemini khác trong tab Cài đặt.
- **Xuất file chẩn đoán gửi hỗ trợ**:
  Chạy lệnh sau để tạo file `out/diagnostics_dubstudio.zip` (đã tự động lọc sạch toàn bộ API key nhạy cảm):
  ```powershell
  .venv\Scripts\python.exe -c "from dubstudio.diagnostics import export_diagnostics_bundle; export_diagnostics_bundle()"
  ```

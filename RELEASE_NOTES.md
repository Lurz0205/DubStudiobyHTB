# DubStudio v2.0.2 — Bản Vá Lỗi Toàn Diện: Thước Đo Timeline, Giữ Âm Gốc & Tách Phụ Đề Chuẩn Ngữ Pháp

Bản cập nhật bảo trì **DubStudio v2.0.2** mang đến hàng loạt cải tiến cốt lõi về trải nghiệm người dùng, sửa chữa triệt để hiện tượng rò rỉ vùng âm thanh gốc giữa các dự án và nâng cấp thuật toán tách phụ đề DP:

---

### 🌟 Các Điểm Nâng Cấp & Sửa Lỗi Chính Trên v2.0.2:

#### 1. Thước Đo Timeline Tinh Giản 5 Giây / Nhãn (Ruler 5s)
- **Cải tiến:** Nhãn mốc thời gian trên thước đo Timeline được chuẩn hóa hiển thị cố định **5 giây 1 số** (`00:00`, `00:05`, `00:10`, `00:15`...) theo định dạng `MM:SS`. 
- **Lợi ích:** Loại bỏ tình trạng nhãn số xuất hiện dày đặc từng giây (gây rối mắt khi phóng to Timeline), đồng thời giữ lại các vạch khấc phụ 1s tinh tế giúp người dùng căn chỉnh trực quan và dễ chịu nhất.

#### 2. Triệt Tiêu Lỗi Rò Rỉ Vùng Giữ Âm Gốc Giữa Các Dự Án ("Ghost Ranges")
- **Nguyên nhân:** Khi tạo hoặc mở một dự án mới chưa từng đánh dấu "Giữ âm thanh gốc", biến trạng thái giao diện vô tình giữ lại mốc thời gian của dự án dài trước đó. Dẫn đến khi xuất video, hệ thống phát thông báo *"Đang hòa âm 2 đoạn giữ âm thanh gốc..."* dù người dùng không hề chọn.
- **Giải pháp trên v2.0.2:** Đặt lại trạng thái `keep_original_ranges = []` triệt để tại `App.tsx`, `StudioWorkspace.tsx` và `MergeExportView.tsx`. Bổ sung bộ lọc an toàn tại `mix.py` tự động loại bỏ bất kỳ mốc giữ âm gốc nào vượt quá độ dài video thực tế.

#### 3. Nâng Cấp Thuật Toán Tách Phụ Đề DP Chuẩn Ngữ Pháp Tiếng Việt
- **Cải tiến:**
  - Loại bỏ hoàn toàn các giới từ (*"với", "cho", "để", "trong"...*) khỏi danh sách khởi đầu mệnh đề, bảo vệ trọn vẹn các cụm vị ngữ và cụm từ cố định tiếng Việt (ví dụ: *"không thẹn với lòng,"*).
  - Tăng mạnh điểm thưởng ưu tiên ngắt tự nhiên tại dấu phẩy (`-180.0 điểm`) kết hợp dung sai độ dài linh hoạt (`target_n + 2`).
  - Ngăn chặn triệt để tình trạng câu bị cắt ngắt ngứ bỏ lại 1–2 từ đuôi rớt xuống dòng dưới trước dấu phẩy.

#### 4. Tự Động Co Giãn Tỷ Lệ Thời Gian Lát Cắt Khi Sửa Độ Dài Câu
- Khi người dùng thay đổi thời gian bắt đầu/kết thúc của một câu phụ đề, hệ thống tự động co giãn tỷ lệ thời gian hiển thị của các lát cắt phụ bên trong tương ứng theo độ dài mới mà không cần phải bấm lại nút "Tách tự động".

#### 5. Chống Giật Tua Video Khi Kéo Thanh Cuộn Ngang Timeline & Ẩn Phụ Đề Khi Dừng
- Ngăn chặn hoàn toàn sự kiện tua video (seek) khi người dùng nhấp hoặc kéo thanh cuộn ngang ở đáy Timeline.
- Phụ đề xem trước chỉ hiển thị khi con trỏ phát thực sự nằm trong khoảng thời gian có thoại; tự động ẩn khi dừng tại khoảng lặng.

#### 6. Đồng Bộ Nhãn Dán Phiên Bản Động Trên Giao Diện
- Nhãn phiên bản ở góc trái dưới cùng của thanh điều hướng Sidebar (`DubStudio v2.0.2 Stable`) được liên kết trực tiếp qua Native Bridge với lõi backend, luôn đồng bộ chính xác với phiên bản phát hành mới nhất.

---

### 📋 Hướng Dẫn Cập Nhật & Nâng Cấp:
- **Tự động cập nhật:** Ứng dụng tích hợp công nghệ cập nhật thông minh (Velopack). Khi mở ứng dụng, hệ thống sẽ tự động thông báo và tải gói nâng cấp delta nhỏ gọn.
- **Người dùng mới hoặc cài lại:** Tải tệp `DubStudio-win-Setup.exe` ở phần Assets bên dưới và cài đặt tự động trong 1 click. Toàn bộ các dự án và mô hình AI đã tải trong máy đều được giữ nguyên 100% tại `%LocalAppData%\DubStudioData`.

---

### 🛡️ Bảng Kiểm Toán & Thông Số Kỹ Thuật (Technical Audit & Checksums)

- **Phiên bản:** `v2.0.2`
- **Mốc so sánh đối chiếu:** `v2.0.1`
- **Kiến trúc:** Windows 64-bit (x64) | Local-first Desktop Application
- **Công nghệ cốt lõi:** PyWebView + React 19 + Tailwind CSS v4 + FastAPI In-Memory Bridge + Windows Native GDI + FFmpeg 7.1 + Velopack
- **Trạng thái kiểm thử:** 191 passed, 10 skipped (100% Test Suite Passed)

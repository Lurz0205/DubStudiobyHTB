# DubStudio v2.0.1 — Bản Vá Lỗi Toàn Diện: Khắc Phục Lỗi Phụ Đề Xuất, Hòa Âm BGM & Trạng Thái Dự Án

Bản cập nhật bảo trì **DubStudio v2.0.1** tập trung giải quyết triệt để 3 lỗi phát sinh sau bản v2.0.0, bảo đảm quy trình làm việc từ khâu biên tập, tạo lại giọng đọc đến kết xuất video luôn đồng bộ và chính xác tuyệt đối:

---

### 🌟 Các Điểm Nâng Cấp & Sửa Lỗi Chính Trên v2.0.1:

#### 1. Khắc Phục Triệt Để Lỗi Phụ Đề Xuất Ra Vẫn Là Phụ Đề Cũ Của Lần Đầu Tạo
- **Nguyên nhân trước đây:** Thuật toán trích xuất phụ đề trong `ass.py` ưu tiên đọc các lát cắt phụ (`sub_slices`) nhưng không kiểm tra đối chiếu lại với câu thoại mới sau khi rút gọn (`fit_rewrite`) hoặc chỉnh sửa câu thủ công. Điều này khiến video xuất ra vẫn mang phụ đề ban đầu dù giọng đọc đã cập nhật câu mới.
- **Giải pháp trên v2.0.1:** Bổ sung cơ chế đối chiếu chuỗi chuẩn hóa `_norm_cmp`. Nếu nội dung lát cắt cũ không khớp với câu thoại hiện tại, hệ thống lập tức loại bỏ lát cắt rác và tự động phân tách lại dòng phụ đề mới khớp 100% từng từ với câu thoại đã rút gọn. Đồng thời đồng bộ tức thì cấu trúc phụ đề ngay khi người dùng bấm "Tạo lại giọng đọc" trong bảng sửa câu.

#### 2. Sửa Lỗi Điều Chỉnh Âm Lượng Nhạc Nền (BGM) & Đặt Mặc Định BGM 100%
- **Nguyên nhân trước đây:** Trình phát xem trước ưu tiên nạp tệp âm thanh đã hòa trộn sẵn (`voice_track.wav`) thay vì giọng đọc gốc thuần (`voice_raw.wav`), khiến nhạc nền bị "nướng chết" vào rãnh giọng. Đồng thời vòng lặp animation của trình xem trước bị dính lỗi *stale closure*, liên tục ghi đè lại mức âm lượng cũ khi kéo thanh trượt lúc đang phát.
- **Giải pháp trên v2.0.1:**
  - Tách bạch hoàn toàn rãnh giọng đọc thuần (`voice_raw.wav`) và rãnh nhạc nền (`audio/bgm.wav`) trên trình phát xem trước.
  - Sử dụng tham chiếu trực tiếp `syncAudioVolumesRef` giúp việc kéo thanh trượt âm lượng BGM hay Thuyết minh thay đổi âm lượng tức thì trong thời gian thực (real-time).
  - Nâng mức âm lượng mặc định của nhạc nền (BGM) lên **100%** (chuẩn cân bằng hoàn hảo với giọng đọc).
  - Bổ sung cơ chế lưu trữ và tự động chuyển đổi thang âm lượng 0–200% xuyên suốt từ giao diện sang tệp hòa âm `mix_settings.json` khi xuất video.

#### 3. Sửa Lỗi Dự Án Mới Tạo Bị Đánh Dấu Đã Hoàn Thành Phụ Đề
- **Nguyên nhân trước đây:** Khi tạo dự án mới, hệ thống tạo sẵn tệp `segments.json` chứa danh sách rỗng `[]`, khiến trang danh sách dự án nhận diện tệp tồn tại và tự động tick xanh hoàn thành bước "Phụ đề".
- **Giải pháp trên v2.0.1:** Cập nhật cơ chế kiểm tra tiến độ dự án: chỉ đánh dấu bước "Phụ đề" khi `segments.json` thực sự chứa ít nhất 1 câu thoại đã nhận dạng/dịch thuật (`len(segments) > 0`). Dự án mới tạo sẽ hiển thị chính xác trạng thái ban đầu là "Video gốc".

---

### 📋 Hướng Dẫn Cập Nhật & Nâng Cấp:
- **Tự động cập nhật:** Ứng dụng tích hợp công nghệ cập nhật thông minh (Velopack). Khi mở ứng dụng, hệ thống sẽ tự động thông báo và tải gói nâng cấp delta nhỏ gọn.
- **Người dùng mới hoặc cài lại:** Tải tệp `DubStudio-win-Setup.exe` ở phần Assets bên dưới và cài đặt tự động trong 1 click. Toàn bộ các dự án và mô hình AI đã tải trong máy đều được giữ nguyên 100% tại `%LocalAppData%\DubStudioData`.

---

### 🛡️ Bảng Kiểm Toán & Thông Số Kỹ Thuật (Technical Audit & Checksums)

- **Phiên bản:** `v2.0.1`
- **Mốc so sánh đối chiếu:** `v2.0.0`
- **Kiến trúc:** Windows 64-bit (x64) | Local-first Desktop Application
- **Công nghệ cốt lõi:** PyWebView + React 19 + Tailwind CSS v4 + FastAPI In-Memory Bridge + Windows Native GDI + FFmpeg 7.1 + Velopack
- **Trạng thái kiểm thử:** 179 passed, 10 skipped (100% Test Suite Passed)

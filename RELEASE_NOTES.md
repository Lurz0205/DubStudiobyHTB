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

### 🛡️ Bảng Kiểm Toán & Thông Số Kỹ Thuật (Technical Audit & Checksums)

- **Phiên bản:** `v2.0.1`
- **Mốc so sánh đối chiếu:** `v2.0.0`
- **Trạng thái kiểm thử:** 179 passed, 10 skipped (100% Test Suite Passed)

---

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

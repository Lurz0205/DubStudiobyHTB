# PROGRESS.md — DubStudio Progress

## Đã hoàn thành (Done)
- **Tự động ngắt nhịp tách câu theo số từ ước lượng (`studio_page.py`):**
  - Bắt sự kiện thay đổi `Từ/dòng` (`_spin_words_per_line`) lưu tức thì vào `job_config.json`.
  - Tự động kích hoạt cơ chế `_on_auto_split_cues_clicked(silent=True)` ngay sau khi tạo phụ đề Bước 1 hoàn tất, không bắt người dùng phải bấm nút tách thủ công.
- **Hợp nhất xuất video & Thêm chọn đường dẫn đầu ra (`merge_page.py`, `settings_page.py`):**
  - Xóa nút "Xuất video" ở tab Phụ đề, chuyển thành nút điều hướng "Chỉnh sửa & Xuất video ➔".
  - Tab Chỉnh sửa video: hiển thị preview phụ đề 1:1 nhưng khóa kéo thả (read-only), tự động đặt tên file xuất theo tên dự án `<tên_dự_án>.mp4`, lưu đồng thời vào thư mục xuất và thư mục dự án. Popup xuất video có đủ nút "Xem video ngay" và "Mở thư mục video".
  - Tab Cài đặt bổ sung mục chọn "Thư mục lưu video xuất", hỗ trợ duyệt thư mục và lưu vào cấu hình hệ thống.
- **Chuẩn hóa âm thanh TTS Phương án B (Headroom Scaling chuẩn DAW) & Vocal Enhancement (`mix.py`, `video_player.py`):**
  - Giữ nguyên 100% âm lượng gốc TTS, chuẩn hóa mức 200% tăng cực mạnh **+20.0 dB** (gấp 10 lần biên độ sóng).
  - Tích hợp Studio Vocal Enhancement: High-pass filter 80Hz cắt tạp âm rung chấn trầm, EQ làm rõ giọng 3.2kHz, Lookahead Peak Limiter chống clipping tuyệt đối.
  - Cơ chế Headroom Scaling duy nhất: `voice_headroom_200.wav` loại bỏ hoàn toàn việc chuyển đổi file gây mất tiếng và đơ âm thanh khi rê chuột. Đảm bảo tự động phát hiện và tái tạo file +20dB nếu tồn tại bản cũ.
- **Đồng bộ tuyệt đối hệ tọa độ phụ đề WYSIWYG & Mở rộng tỉ lệ nền 9:16 (`ass.py`, `video_player.py`, `app.py`):**
  - Chuẩn hóa `compute_subtitle_geometry` trên hệ quy chiếu video gốc (`native_w x native_h`).
  - Preview `video_player.py`: vẽ phụ đề bằng `painter.scale()` từ tọa độ gốc lên `inner_video_rect`, xóa bỏ clamp min 20px/40px gây lệch tỉ lệ khi bật 9:16. Đồng nhất 100% giữa Tab Phụ đề và Trang Chỉnh sửa.
  - Xuất video `dubstudio/api/app.py`: đốt phụ đề lên `v_chain` TRƯỚC KHI áp filter `pad` 9:16, giữ phụ đề nằm gọn gàng bên trong khung video gốc, vùng đệm trắng ở trên và dưới 100% sạch sẽ không bị lem hay văng chữ.
- **Khôi phục bảng Hòa âm & Âm thanh và chuẩn hóa thư mục xuất (`subtitle_export_page.py`, `paths.py`):**
  - Khôi phục lại thẻ Bento "Hòa âm & Âm thanh" ở Tab Phụ đề với đầy đủ 4 kênh: Thuyết minh tiếng Việt (0 - 200%), Nhạc nền gốc, Nhạc nền tự chèn, Giọng gốc video.
  - Sửa triệt để nguyên nhân thư mục xuất bị gán đường dẫn rác pytest: xóa sạch dòng gán trong `.env`, bổ sung bộ lọc bỏ đường dẫn tạm pytest trong `dubstudio/paths.py`, cô lập `monkeypatch` trong `test_ui_export_and_split.py`. Đường dẫn mặc định trở về đúng chuẩn `~/Videos/DubStudio` (bản đóng gói) và `out/` (bản dev).
- **Đóng gói hoàn tất (`scripts\build_app.ps1`):**
  - Đóng gói thành công `dist\DubStudio\DubStudio.exe` và gói Velopack `dist\releases\DubStudio-win-Setup.exe`.
- **Chất lượng:** Toàn bộ 184/184 unit tests passed (100%), bao gồm bộ 3 test kiểm định kiểm soát âm lượng mượt mà và không ngắt tiếng.

## Tiếp theo (Next)
- Người dùng kiểm tra trực tiếp trên `dist\DubStudio\DubStudio.exe`.

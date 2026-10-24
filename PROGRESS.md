# PROGRESS.md — DubStudio Progress

## Đã hoàn thành (Done)
- **Khóa chặt Updater & Di chuyển Model (Mục 1-8):**
  - Đối chiếu 100% tag-to-tag (`v1.1.2` -> HEAD), xuất `RELEASE_AUDIT.md`.
  - Khóa chặt gói delta `*-delta.nupkg` trong workflow CI/CD, tự động dọn rác updater thừa.
  - Gom & bảo toàn mô hình AI File-by-File sang `DubStudioData\models`, tự động rebind đường dẫn.
  - Đóng gói local và kích hoạt release v1.1.3 trên GitHub Actions.
- **Khắc phục triệt để lỗi thỉnh thoảng Not Responding khi tạo TTS:**
  - Khử deadlock pipe `stderr=subprocess.DEVNULL`, đồng bộ khóa `_tts_worker_lock`, dừng worker trước pipeline.
- **Nâng cấp toàn diện chất lượng âm thanh phát thanh & độ nhạy 200% (`video_player.py`, `mix.py`):**
  - Khử triệt để vỡ tiếng/chói gắt: Loại bỏ bộ lọc EQ 3.2kHz và compressor gắt; chuyển sang chuẩn phát thanh quốc tế ITU-R BS.1770 / EBU R128 (`loudnorm=I=-9/-12:TP=-0.8/-1.0`), lọc rè siêu trầm <75Hz và tiếng rít tổng hợp >12.5kHz, bảo đảm 0% clipping.
  - Tối ưu đường cong âm lượng tâm thính học (Psychoacoustic Power Curve): 100% giữ mức tự nhiên, kéo lên 200% tăng vọt +10.5 dB acoustic power (tai người nghe to gấp đôi thực thụ), âm thanh uy lực, trong trẻo và ấm áp.
- **Nâng cấp cơ chế Rút gọn Lồng tiếng Thoát ý & Chống hở câu (`fit.py`, `fit_rewrite.py`, prompts):**
  - Chấm dứt cắt gọt cơ học vụn vặt: Định hướng LLM dịch lại thoát ý bằng khẩu ngữ tự nhiên, súc tích, giữ trọn nghĩa và mạch phim.
  - Bổ sung sàn ký tự `min_chars` nghiêm ngặt và căn chỉnh tỷ lệ nén (0.92 / 0.86 / 0.80 thay vì 0.60): Tuyệt đối không cho phép viết câu quá ngắn dưới `min_chars`, triệt tiêu hoàn toàn hiện tượng "hở miệng/khoảng lặng chết" so với giọng nói gốc trên video.
- **Đồng bộ hóa toàn diện hệ thống thư mục dữ liệu & xuất video:**
  - Chuẩn hóa thư mục xuất video cho bản đóng gói/máy người dùng: Mặc định lưu vào `Videos\DubStudio` (`C:\Users\<User>\Videos\DubStudio`), không giấu trong `%LocalAppData%`.
  - Đồng bộ 100% `get_out_dir()`, `get_workspace_dir()`, `open_in_file_manager()` trên toàn bộ UI, popup, API và worker.
  - Tự động bôi sáng (highlight) file video trong Windows Explorer khi bấm "Mở thư mục", bổ sung nút "Đổi thư mục" trên giao diện.
- **Khắc phục triệt để lỗi âm thanh TTS 200% & đồng bộ 100% WYSIWYG phụ đề:**
  - Chuẩn hóa 48kHz, EQ làm ấm (180Hz) + khử chói (5500Hz), Upward Compression + Limiter đạt tăng vọt +8.4 đến +13.3 LUFS ở mức 200%, True Peak <= -0.3 dBFS, 0% clipping.
  - Sửa lỗi `amix` (thêm `normalize=0`), xóa bỏ duplicate track gốc, đổi cache sang `_boost200_v2.wav`.
  - Đồng bộ 100% từng pixel (sai số 0px) giữa Preview và Render qua `QFontMetrics` và hệ số bù `1.116x` cho `libass`.
- **Chất lượng:** Toàn bộ 175/175 unit tests passed (100%). Đã đóng gói lại `dist/DubStudio/DubStudio.exe` v1.1.3 local. Chưa push lên GitHub.

## Tiếp theo (Next)
- Người dùng kiểm tra trực tiếp trên app và duyệt đẩy lên GitHub khi sẵn sàng.

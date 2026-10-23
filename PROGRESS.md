# PROGRESS.md — Phase 1 Performance & Decoupling Overhaul

## Đã hoàn thành (Done)
- Chuyển `QT_MEDIA_BACKEND` sang `ffmpeg` (thay thế WMF COM lock).
- Tách rời triệt để môi trường: `start.bat` (dev: `workspace/`) và `DubStudio.exe` (packaged: `%LocalAppData%\DubStudio\workspace`). Không xung đột chéo dữ liệu.
- Sửa lỗi không nghe tiếng TTS khi preview: gắn `_apply_stem_volumes()` đúng thời điểm, xuất cả `voice_track.wav` và `voice_raw.wav` trong rebuild, sửa lệnh remux ffmpeg `preview_dubbed.mp4`.
- Bảng phụ đề: hiện icon nghe (volume-2) rõ nét, nhấp vào tự động phát hoặc tổng hợp TTS tức thì theo yêu cầu.
- Trang Xuất video: fix cảnh báo ảo thiếu file TTS (`tts/`, `tts_stretched/`), fix 404 `input.mp4` tại endpoint `/api/jobs/{id}/render`.
- 100% unit tests passed (`pytest tests/ -q`: 130/130 passed).
- Đã đồng bộ mã nguồn vào `dist\DubStudio\_internal\` để kiểm thử ngay.

## Tiếp theo (Next)
- Đẩy commit lên GitHub `main` qua `scripts/push_code_to_github.py`.
- Người dùng chạy kiểm tra thực tế trên `dist\DubStudio\DubStudio.exe`: xem preview video có tiếng TTS lồng tiếng và bấm icon Nghe từng câu.

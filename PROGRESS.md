# PROGRESS.md — DubStudio Progress

## Đã hoàn thành (Done)
- **Khắc phục triệt để lỗi âm thanh TTS 200% & đồng bộ 100% WYSIWYG phụ đề:**
  - Chuẩn hóa 48kHz, EQ làm ấm (180Hz) + khử chói (5500Hz), Upward Compression + Limiter đạt tăng vọt +8.4 đến +13.3 LUFS ở mức 200%, True Peak <= -0.3 dBFS, 0% clipping.
  - Sửa lỗi `amix` (thêm `normalize=0`), xóa bỏ duplicate track gốc, đổi cache sang `_boost200_v2.wav`.
  - Đồng bộ 100% từng pixel (sai số 0px) giữa Preview và Render qua `QFontMetrics` và hệ số bù `1.116x` cho `libass`.
- **Đồng bộ hóa toàn diện hệ thống thư mục dữ liệu & xuất video:**
  - Chuẩn hóa thư mục xuất video cho bản đóng gói: Mặc định lưu vào `Videos\DubStudio` (`C:\Users\<User>\Videos\DubStudio`).
  - Đồng bộ `get_out_dir()`, `get_workspace_dir()`, `open_in_file_manager()` (`explorer /select`).
- **Khóa cứng mốc so sánh Release < CURRENT_VERSION:**
  - Khóa vĩnh viễn mốc so sánh tag-to-tag (`v1.1.2` làm chuẩn cho `v1.1.3`) trong `scripts/audit_release_diff.py` và `AGENTS.md` (R14).
  - Tự động xóa sạch release/tag cũ của cùng phiên bản trước khi đóng gói delta và audit.
  - Đã xuất bản `RELEASE_AUDIT.md` đối chiếu 100% 46 file modified và 7 file added so với commit `4d50c5a` của `v1.1.2`.
- **Đã kiểm thử & phát hành GitHub:**
  - 175/175 tests pass (100%). Commit `a7ccb10` và tag `v1.1.3` đã đẩy lên GitHub `main`.
  - GitHub Actions đang tự động cắt delta package từ `v1.1.2` và đóng gói `Setup.exe` trên Azure.

## Tiếp theo (Next)
- Theo dõi GitHub Actions hoàn tất và phát hành gói update `v1.1.3` chính thức.

# PROGRESS.md — DubStudio Progress

## Đã hoàn thành (Done)
- **Kiểm toán minh bạch Tag-to-Tag & Khóa chặt Delta Updater (Mục 1-7):**
  - Hoàn thành `scripts/audit_release_diff.py`: Đối chiếu 100% mã nguồn tag-to-tag (`v1.1.2` -> HEAD), tự động xuất `RELEASE_AUDIT.md`.
  - Tích hợp kiểm toán vào `scripts/push_code_to_github.py` và Verification Gate bắt buộc có `*-delta.nupkg` trong GitHub Actions.
  - Bảo vệ `current/` với `PYTHONDONTWRITEBYTECODE=1`; phân luồng updater độc lập cho Velopack Delta; cơ chế tự dọn rác thừa `cleanup_update_artifacts()`.
  - Thực nghiệm đóng gói với `vpk`: Gói delta đạt 3.06 KB (tiết kiệm 99.9% dung lượng), tái tạo nhị phân khớp 100% SHA-256.
- **Bảo toàn & Di chuyển Mô hình AI Đa Đường Dẫn (Mục 8):**
  - Nâng cấp `migrate_legacy_user_data` trong `dubstudio/paths.py`: Quét & gom File-by-File an toàn từ `%LocalAppData%\DubStudio` và `current\models` sang `%LocalAppData%\DubStudioData`.
  - Chống `FileExistsError`, so sánh kích thước file (giữ bản lớn/đầy đủ hơn, xóa file thừa tránh nhân đôi dung lượng), dọn sạch thư mục cũ.
  - Path Rebinding: Tự động viết lại đường dẫn tuyệt đối trong `installed.json`, `config.toml`, `settings.json` và đồng bộ registry.
  - Fallback Đa Đường Dẫn: Bổ sung `get_model_search_paths()`, `find_model_file()`, `find_model_dir()`, cập nhật `separate.py`, `asr.py`, `components.py`.
  - Tạo 5 bài test tự động `tests/test_model_migration.py`.
- **Chất lượng:** Toàn bộ bộ kiểm thử 171/171 tests passed (100%). Đã đồng bộ sang `dist/`.

## Tiếp theo (Next)
- Đóng gói và phát hành bản vá mới khi người dùng yêu cầu.

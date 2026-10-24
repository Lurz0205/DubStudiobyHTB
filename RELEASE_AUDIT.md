# DubStudio Release Audit — Tag-to-Tag Comparison

- **Mục tiêu phát hành:** `v1.1.3`
- **Phiên bản gốc đối chiếu:** `v1.1.2`
- **Thời gian kiểm toán:** `2026-10-24 15:36:05`
- **Tổng số file thay đổi:** `39` (34 sửa đổi, 5 thêm mới, 0 đã xóa)

---

## 1. Tổng hợp toàn diện các tính năng & Lỗi đã sửa từ `v1.1.2`

1. **Chuỗi Xử lý Âm thanh Studio Mastering & Sửa lỗi âm lượng 200%:**
   - Tái cấu trúc chuỗi bộ lọc âm thanh giọng đọc tiếng Việt: lọc rung sub-bass (high-pass 80Hz), tăng cường 2 dải EQ trong trẻo phát âm tiếng Việt (+3dB ở 3.2kHz, +1.5dB ở 120Hz), broadcast compressor.
   - Đưa bộ tăng âm sau compressor đạt chuẩn âm học +6.01 dBFS ở 200% kèm true-peak alimiter chống vỡ tiếng.
   - Tích hợp tính năng **Auto-Ducking thông minh (`sidechaincompress`)**: Tự động giảm nhạc nền BGM xuống ~10 dB khi có giọng đọc và trả về êm ái khi dứt câu.
   - Trình phát video preview điều khiển độc lập 4 luồng âm thanh mượt mà.

2. **Khắc phục triệt để lỗi kết xuất video (500 Server Error):**
   - Sửa lỗi thiếu khai báo `cfg = AppConfig.load()` trong endpoint `/api/jobs/{job_id}/render`, `/split`, `/segments/tts`.
   - Cấu hình In-Memory ASGI Bridge trả về phản hồi lỗi JSON tiếng Việt rõ ràng, loại bỏ hoàn toàn các chuỗi URL loopback/port khỏi giao diện người dùng.

3. **Kiến trúc Cập nhật An toàn & Bảo toàn Dữ liệu:**
   - Tách biệt thư mục cài đặt `%LocalAppData%\DubStudio` và dữ liệu `%LocalAppData%\DubStudioData`.
   - Cho phép cài đè không bao giờ bị xung đột hoặc mất các mô hình AI đã tải.
   - Mở khóa cờ `JOB_OBJECT_LIMIT_BREAKAWAY_OK` và khởi động lại độc lập bằng PowerShell wait-for-PID chống lỗi khóa file `WinError 32`.
   - Xác thực toàn vẹn mã băm SHA-256 và kích thước byte trước khi áp dụng cập nhật.

4. **Tối ưu hóa Vòng lặp Khớp Thoại (Fit Stage):**
   - Cân bằng thời lượng 2 chiều (`shorter` cho câu bị đè, `longer` cho câu quá ngắn) qua 1 lượt gọi LLM duy nhất.
   - Tận dụng Persistent TTS Warm Worker tổng hợp âm thanh từng câu chỉ mất ~0.4s.
   - Sửa triệt để lỗi xung đột keyword argument `stdin` trong subprocess Popen.

---

## 2. Bảng Danh mục Chi tiết Các File Thay đổi (`v1.1.2..HEAD`)

| Trạng thái | Đường dẫn File | SHA cũ (v1.1.2) | SHA mới (HEAD) |
|:---|:---|:---|:---|
| **Modified** | `.github/workflows/build_release.yml` | `a42b286` | `dffc8e2` |
| **Modified** | `DubStudio.spec` | `eb97325` | `571f302` |
| **Modified** | `PROGRESS.md` | `8b98e6d` | `92f4030` |
| **Modified** | `RELEASE_NOTES.md` | `3437d7f` | `d2ef779` |
| **Modified** | `config/subtitle_preset.json` | `bfaaf0b` | `8ea2b4a` |
| **Modified** | `dubstudio/api/app.py` | `678225e` | `aebc064` |
| **Modified** | `dubstudio/components.py` | `f0c242f` | `30eaf30` |
| **Modified** | `dubstudio/llm/cdp_gemini.py` | `ca65a02` | `7d5b40c` |
| **Modified** | `dubstudio/llm/fit_rewrite.py` | `ccda274` | `b02f474` |
| **Modified** | `dubstudio/llm/prompts/fit_rewrite.md` | `c7102ab` | `a4dbff7` |
| **Modified** | `dubstudio/packaging.py` | `89647bc` | `058616e` |
| **Modified** | `dubstudio/paths.py` | `d0ef149` | `c4eba77` |
| **Modified** | `dubstudio/stages/asr.py` | `13e9389` | `f73e0ec` |
| **Modified** | `dubstudio/stages/fit.py` | `b90a1d4` | `0de5d08` |
| **Modified** | `dubstudio/stages/mix.py` | `a99f618` | `f6b897f` |
| **Modified** | `dubstudio/stages/separate.py` | `fc2e15e` | `614d68a` |
| **Modified** | `dubstudio/subtitles/sentence_align.py` | `49f8c58` | `21aa067` |
| **Modified** | `dubstudio/updater.py` | `8f89485` | `614aa10` |
| **Modified** | `dubstudio/version.py` | `92ed50d` | `0ed62e0` |
| **Modified** | `dubstudio/win_job.py` | `c564d6e` | `57b5253` |
| **Modified** | `scripts/build_app.ps1` | `c211d51` | `37db4a8` |
| **Modified** | `scripts/push_code_to_github.py` | `0b2ed38` | `eb47954` |
| **Modified** | `scripts/sim_user_machine.ps1` | `9898e47` | `3c0c5f1` |
| **Modified** | `start_app.py` | `2378504` | `8aa6f48` |
| **Modified** | `tests/test_api.py` | `5ee1602` | `42b9528` |
| **Modified** | `tests/test_fit.py` | `40c55f7` | `abb1b28` |
| **Modified** | `tests/test_part_c.py` | `55789e8` | `7893da1` |
| **Modified** | `tests/test_phase4_studio_ui.py` | `c016f0b` | `869501b` |
| **Modified** | `tests/test_updater.py` | `e4f345a` | `a6e9b63` |
| **Modified** | `ui/app.py` | `ac0ae63` | `476dba6` |
| **Modified** | `ui/main_window.py` | `2760c6e` | `024233c` |
| **Modified** | `ui/pages/settings_page.py` | `f3c2ba1` | `b94caf4` |
| **Modified** | `ui/widgets/video_player.py` | `28c07a5` | `d4deb2b` |
| **Modified** | `ui/workers.py` | `306799a` | `e0b6f2d` |
| **Added** | `dubstudio/hotpatch.py` | *N/A* | `7788471` |
| **Added** | `scripts/audit_release_diff.py` | *N/A* | `2f546cb` |
| **Added** | `tests/test_chinese_split_and_stream.py` | *N/A* | `c7ae9f8` |
| **Added** | `tests/test_hotpatch_and_relaunch.py` | *N/A* | `3906ce9` |
| **Added** | `tests/test_model_migration.py` | *N/A* | `414ff9b` |

---

## 3. Lịch sử Git Commits Kể từ `v1.1.2`

- [`4b45694`] Release: Patch v1.1.3 - Hot-patch, Safe Relaunch, Fit Optimization & Model Notification
- [`922184e`] Update GitHub push script to Full-Tree Deterministic Snapshot Sync
- [`d8b2c43`] Release v1.1.3: Studio audio mastering, 200% volume fix, render fix, and safe updater

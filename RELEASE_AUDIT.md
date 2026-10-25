# DubStudio Release Audit — Tag-to-Tag Comparison

- **Mục tiêu phát hành:** `v1.1.3`
- **Phiên bản gốc đối chiếu:** `v1.1.2`
- **Thời gian kiểm toán:** `2026-10-25 09:28:35`
- **Tổng số file thay đổi:** `56` (47 sửa đổi, 9 thêm mới, 0 đã xóa)

---

## 1. Tổng hợp toàn diện các tính năng & Lỗi đã sửa từ `v1.1.2`

1. **Chuẩn hóa Phóng đại Âm lượng +20.0 dB & Headroom Scaling chuẩn DAW:**
   - Giữ nguyên vẹn 100% âm lượng gốc TTS khi ở mức 100% (đạt chuẩn 0.0 dB diff).
   - Mức 200% phóng đại thực tế cực mạnh **+20.0 dB** (gấp 10 lần biên độ sóng ban đầu), kết hợp transparent lookahead soft-limiter tại 0.98 chống clipping và không gây rè/vang.
   - Cơ chế Headroom Scaling duy nhất (`voice_headroom_200.wav`): Không đổi source URL của file âm thanh khi kéo thanh trượt, điều chỉnh gain phần cứng tức thì, chấm dứt hoàn toàn hiện tượng khựng, giật cục hay mất tiếng.

2. **Studio Vocal Enhancement & Auto-Ducking thông minh:**
   - Chuỗi lọc giọng đọc: High-pass 80Hz cắt rung chấn micro sub-bass; EQ 3.2kHz tăng độ thoát tiếng cho phát âm tiếng Việt; EQ 350Hz làm sạch dải trung trầm bí bách.
   - Tính năng **Auto-Ducking (`sidechaincompress`)**: Tự động giảm nhạc nền BGM xuống ~10 dB khi có giọng đọc và trả về êm ái khi dứt câu.

3. **Tự động Ngắt nhịp Tách câu theo Số từ Ước lượng:**
   - Bắt sự kiện thay đổi `Từ/dòng` lưu tức thì vào `job_config.json`.
   - Tự động kích hoạt cơ chế tách câu ngắt nhịp ngay sau khi tạo phụ đề Bước 1 hoàn tất, loại bỏ thao tác bấm nút tách thủ công của người dùng.

4. **Hợp nhất Xuất video vào Tab Chỉnh sửa Video:**
   - Xóa bỏ nút Xuất video ở Tab Phụ đề, chuyển thành nút điều hướng trực quan sang Tab Chỉnh sửa video.
   - Tab Chỉnh sửa video hiển thị preview phụ đề 1:1, tự động đặt tên file xuất theo tên dự án `<tên_dự_án>.mp4`, lưu đồng thời vào thư mục xuất và thư mục dự án.
   - Bổ sung mục chọn 'Thư mục lưu video xuất' trong Cài đặt, chuẩn hóa mặc định về `~/Videos/DubStudio`.

5. **Đồng bộ Tuyệt đối Hệ Tọa độ Phụ đề WYSIWYG & Mở rộng Tỉ lệ Nền (9:16):**
   - Chuẩn hóa hệ quy chiếu `compute_subtitle_geometry` trên độ phân giải gốc của video (`native_w x native_h`).
   - Preview và video xuất đồng nhất 100%, hộp nền đen che kín chữ Trung Quốc gốc bên dưới.
   - Khi bật mở rộng tỉ lệ nền 9:16, phụ đề được đốt lên video gốc trước khi thêm viền đệm pad, giữ chữ nằm gọn trong khung hình gốc, không bao giờ rơi ra ngoài vùng đệm trắng.

6. **Kiến trúc Cập nhật An toàn & Tự động Khóa Mốc So sánh:**
   - Tách biệt thư mục cài đặt `%LocalAppData%\DubStudio` và dữ liệu `%LocalAppData%\DubStudioData`, bảo toàn 100% các model AI đã tải khi cập nhật bản mới.
   - Luôn khóa mốc so sánh (audit & delta package) từ bản release chính thức trước đó trên GitHub (`tag_version < CURRENT_VERSION`), đảm bảo Velopack cắt delta chuẩn xác và siêu nhẹ.

---

## 2. Bảng Danh mục Chi tiết Các File Thay đổi (`v1.1.2..HEAD`)

| Trạng thái | Đường dẫn File | SHA cũ (v1.1.2) | SHA mới (HEAD) |
|:---|:---|:---|:---|
| **Modified** | `.github/workflows/build_release.yml` | `a42b286` | `f259ebf` |
| **Modified** | `AGENTS.md` | `62cac09` | `3e0334b` |
| **Modified** | `DubStudio.spec` | `eb97325` | `af5ebbf` |
| **Modified** | `PROGRESS.md` | `8b98e6d` | `0315cee` |
| **Modified** | `README.md` | `11132e4` | `44bf192` |
| **Modified** | `RELEASE_NOTES.md` | `3437d7f` | `a5fbc0b` |
| **Modified** | `config/subtitle_preset.json` | `bfaaf0b` | `49d456c` |
| **Modified** | `dubstudio/api/app.py` | `678225e` | `1ce3f03` |
| **Modified** | `dubstudio/components.py` | `f0c242f` | `30eaf30` |
| **Modified** | `dubstudio/config.py` | `6e2fea5` | `f1ac860` |
| **Modified** | `dubstudio/llm/cdp_gemini.py` | `ca65a02` | `7d5b40c` |
| **Modified** | `dubstudio/llm/fit_rewrite.md` | `793fea8` | `8a42461` |
| **Modified** | `dubstudio/llm/fit_rewrite.py` | `ccda274` | `d0f4b16` |
| **Modified** | `dubstudio/llm/gemini.py` | `f55f899` | `cd489ff` |
| **Modified** | `dubstudio/llm/prompts/cluster_rewrite.md` | `5dadf31` | `aa000e5` |
| **Modified** | `dubstudio/llm/prompts/fit_rewrite.md` | `c7102ab` | `60ff51f` |
| **Modified** | `dubstudio/packaging.py` | `89647bc` | `058616e` |
| **Modified** | `dubstudio/paths.py` | `d0ef149` | `373a6aa` |
| **Modified** | `dubstudio/stages/asr.py` | `13e9389` | `f73e0ec` |
| **Modified** | `dubstudio/stages/fit.py` | `b90a1d4` | `91807eb` |
| **Modified** | `dubstudio/stages/mix.py` | `a99f618` | `90ca80a` |
| **Modified** | `dubstudio/stages/separate.py` | `fc2e15e` | `614d68a` |
| **Modified** | `dubstudio/subtitles/ass.py` | `74417e7` | `328645f` |
| **Modified** | `dubstudio/subtitles/sentence_align.py` | `49f8c58` | `21aa067` |
| **Modified** | `dubstudio/tools/trim_video.py` | `daf1a61` | `6cdc95f` |
| **Modified** | `dubstudio/updater.py` | `8f89485` | `dc26256` |
| **Modified** | `dubstudio/version.py` | `92ed50d` | `0ed62e0` |
| **Modified** | `dubstudio/win_job.py` | `c564d6e` | `57b5253` |
| **Modified** | `scripts/build_app.ps1` | `c211d51` | `00e720a` |
| **Modified** | `scripts/push_code_to_github.py` | `0b2ed38` | `808c9cc` |
| **Modified** | `scripts/sim_user_machine.ps1` | `9898e47` | `3c0c5f1` |
| **Modified** | `start_app.py` | `2378504` | `8aa6f48` |
| **Modified** | `tests/test_api.py` | `5ee1602` | `42b9528` |
| **Modified** | `tests/test_fit.py` | `40c55f7` | `abb1b28` |
| **Modified** | `tests/test_part_c.py` | `55789e8` | `7893da1` |
| **Modified** | `tests/test_paths_and_jobs.py` | `cfb76a6` | `b66979d` |
| **Modified** | `tests/test_phase4_studio_ui.py` | `c016f0b` | `869501b` |
| **Modified** | `tests/test_updater.py` | `e4f345a` | `a6e9b63` |
| **Modified** | `ui/app.py` | `ac0ae63` | `476dba6` |
| **Modified** | `ui/main_window.py` | `2760c6e` | `9b05fbc` |
| **Modified** | `ui/pages/merge_page.py` | `81c4b14` | `85a113c` |
| **Modified** | `ui/pages/projects_page.py` | `2825ed2` | `56491ee` |
| **Modified** | `ui/pages/settings_page.py` | `f3c2ba1` | `141576d` |
| **Modified** | `ui/pages/studio_page.py` | `cc65e5b` | `1b27222` |
| **Modified** | `ui/pages/subtitle_export_page.py` | `3e498d0` | `88994e6` |
| **Modified** | `ui/widgets/video_player.py` | `28c07a5` | `1c45938` |
| **Modified** | `ui/workers.py` | `306799a` | `e0b6f2d` |
| **Added** | `dubstudio/hotpatch.py` | *N/A* | `7788471` |
| **Added** | `scripts/audit_release_diff.py` | *N/A* | `589a763` |
| **Added** | `tests/test_audio_volume_smooth.py` | *N/A* | `399a9d7` |
| **Added** | `tests/test_chinese_split_and_stream.py` | *N/A* | `c7ae9f8` |
| **Added** | `tests/test_hotpatch_and_relaunch.py` | *N/A* | `3906ce9` |
| **Added** | `tests/test_model_migration.py` | *N/A* | `414ff9b` |
| **Added** | `tests/test_stem_mixing.py` | *N/A* | `841ae86` |
| **Added** | `tests/test_subtitle_wysiwyg.py` | *N/A* | `d6148e9` |
| **Added** | `tests/test_ui_export_and_split.py` | *N/A* | `38df209` |

---

## 3. Lịch sử Git Commits Kể từ `v1.1.2`

- **[Bản phát hành này / HEAD]** Release v1.1.3: +20dB Voice Boost, WYSIWYG 9:16 Subtitles, and Unified Export
- [`4b45694`] Release: Patch v1.1.3 - Hot-patch, Safe Relaunch, Fit Optimization & Model Notification
- [`922184e`] Update GitHub push script to Full-Tree Deterministic Snapshot Sync
- [`d8b2c43`] Release v1.1.3: Studio audio mastering, 200% volume fix, render fix, and safe updater
- [`a717b20`] Release v1.1.3: Tag-to-tag audit, locked delta updater, and smart model migration
- [`a7ccb10`] Update source tree snapshot
- [`44a9a40`] Update source tree snapshot
- [`1f3b775`] Update source tree snapshot
- [`1baae95`] Update source tree snapshot
- [`9de861d`] Update README.md
- [`a977440`] Update source tree snapshot

# DubStudio Release Audit — Tag-to-Tag Comparison

- **Mục tiêu phát hành:** `v2.0.0`
- **Phiên bản gốc đối chiếu:** `v1.1.3`
- **Thời gian kiểm toán:** `2026-10-27 18:11:55`
- **Tổng số file thay đổi:** `138` (45 sửa đổi, 63 thêm mới, 30 đã xóa)

---

## 1. Tổng hợp toàn diện các tính năng & Lỗi đã sửa từ `v1.1.3`

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

## 2. Bảng Danh mục Chi tiết Các File Thay đổi (`v1.1.3..HEAD`)

| Trạng thái | Đường dẫn File | SHA cũ (v1.1.3) | SHA mới (HEAD) |
|:---|:---|:---|:---|
| **Modified** | `.github/workflows/build_release.yml` | `f259ebf` | `3aefc95` |
| **Modified** | `AGENTS.md` | `3e0334b` | `9912113` |
| **Modified** | `DubStudio.spec` | `af5ebbf` | `a4dcce9` |
| **Modified** | `PROGRESS.md` | `0315cee` | `8060edb` |
| **Modified** | `README.md` | `44bf192` | `97f41a6` |
| **Modified** | `RELEASE_NOTES.md` | `a5fbc0b` | `7fa10d1` |
| **Modified** | `dubstudio.ico` | `a8c3da8` | `f4ea896` |
| **Modified** | `dubstudio/__init__.py` | `a52d273` | `8e891aa` |
| **Modified** | `dubstudio/api/app.py` | `1ce3f03` | `f8dfbcf` |
| **Modified** | `dubstudio/diagnostics.py` | `4f7f2dc` | `6e0fb70` |
| **Modified** | `dubstudio/events.py` | `56a4bd1` | `b5aa66a` |
| **Modified** | `dubstudio/jobstate.py` | `f2c9070` | `441547e` |
| **Modified** | `dubstudio/llm/fit_rewrite.py` | `d0f4b16` | `0feb146` |
| **Modified** | `dubstudio/llm/prompts/fit_rewrite.md` | `60ff51f` | `82ec899` |
| **Modified** | `dubstudio/paths.py` | `373a6aa` | `691ec2b` |
| **Modified** | `dubstudio/stages/fit.py` | `91807eb` | `9431310` |
| **Modified** | `dubstudio/stages/mix.py` | `90ca80a` | `174ac93` |
| **Modified** | `dubstudio/stages/render.py` | `3db9c5d` | `8020252` |
| **Modified** | `dubstudio/stages/translate.py` | `67bb73a` | `7372516` |
| **Modified** | `dubstudio/stages/tts.py` | `63d8eef` | `7816674` |
| **Modified** | `dubstudio/stages/voice_assign.py` | `313986c` | `c352cf7` |
| **Modified** | `dubstudio/subtitles/ass.py` | `328645f` | `537559c` |
| **Modified** | `dubstudio/subtitles/cue_split.py` | `a749e53` | `b8ac840` |
| **Modified** | `dubstudio/tts/base.py` | `b59d2d0` | `692e327` |
| **Modified** | `dubstudio/version.py` | `0ed62e0` | `d5ed31b` |
| **Modified** | `scripts/audit_release_diff.py` | `589a763` | `ce94d30` |
| **Modified** | `scripts/build_app.ps1` | `00e720a` | `6dd8419` |
| **Modified** | `scripts/push_code_to_github.py` | `808c9cc` | `e30ca74` |
| **Modified** | `start.bat` | `fece21a` | `ebfecfc` |
| **Modified** | `start_app.py` | `8aa6f48` | `67933f3` |
| **Modified** | `tests/test_api.py` | `42b9528` | `f8aff16` |
| **Modified** | `tests/test_ass.py` | `fc7e6e8` | `be080e1` |
| **Modified** | `tests/test_audio_volume_smooth.py` | `399a9d7` | `b5b18f1` |
| **Modified** | `tests/test_edit_video.py` | `bb99718` | `9c9b3e2` |
| **Modified** | `tests/test_find_replace_sync.py` | `d450cf6` | `a1d2e1f` |
| **Modified** | `tests/test_fit.py` | `abb1b28` | `60eedb6` |
| **Modified** | `tests/test_hotpatch_and_relaunch.py` | `3906ce9` | `a421530` |
| **Modified** | `tests/test_orig_audio_and_menu.py` | `015698c` | `99f20e1` |
| **Modified** | `tests/test_phase4_studio_ui.py` | `869501b` | `de9384e` |
| **Modified** | `tests/test_stem_mixing.py` | `841ae86` | `d6a6b95` |
| **Modified** | `tests/test_subtitle_wysiwyg.py` | `d6148e9` | `71d392e` |
| **Modified** | `tests/test_trim_video.py` | `b2a8775` | `f270b25` |
| **Modified** | `tests/test_tutorial_and_whisper_settings.py` | `4d4c14e` | `9961e34` |
| **Modified** | `tests/test_ui_export_and_split.py` | `38df209` | `adea810` |
| **Modified** | `tests/test_voice_selection.py` | `f9820b5` | `5c45b47` |
| **Added** | `app.ico` | *N/A* | `f4ea896` |
| **Added** | `config/app_settings.json` | *N/A* | `7a6d630` |
| **Added** | `dubstudio/resources/voice_previews/Adam bựa.wav` | *N/A* | `f9c5769` |
| **Added** | `dubstudio/resources/voice_previews/Adam.wav` | *N/A* | `14a1448` |
| **Added** | `dubstudio/resources/voice_previews/Hải Đăng.wav` | *N/A* | `f279996` |
| **Added** | `dubstudio/resources/voice_previews/Kim Thanh.wav` | *N/A* | `4cd4efb` |
| **Added** | `dubstudio/resources/voice_previews/Mai Anh.wav` | *N/A* | `708cfe5` |
| **Added** | `dubstudio/resources/voice_previews/Minh Triết.wav` | *N/A* | `0b6f15c` |
| **Added** | `dubstudio/resources/voice_previews/Minh Đức.wav` | *N/A* | `f87bcc5` |
| **Added** | `dubstudio/resources/voice_previews/Mỹ Duyên.wav` | *N/A* | `2e6faaf` |
| **Added** | `dubstudio/resources/voice_previews/Ngọc Huyền.wav` | *N/A* | `62ee231` |
| **Added** | `dubstudio/resources/voice_previews/Ngọc Linh.wav` | *N/A* | `58cb7d9` |
| **Added** | `dubstudio/resources/voice_previews/Ngọc Trân.wav` | *N/A* | `f85a47c` |
| **Added** | `dubstudio/resources/voice_previews/Phạm Tuyên.wav` | *N/A* | `653cc61` |
| **Added** | `dubstudio/resources/voice_previews/Quang Sơn.wav` | *N/A* | `a31aadc` |
| **Added** | `dubstudio/resources/voice_previews/Quốc Tuấn.wav` | *N/A* | `ab596b8` |
| **Added** | `dubstudio/resources/voice_previews/Quỳnh Anh.wav` | *N/A* | `0e56e35` |
| **Added** | `dubstudio/resources/voice_previews/Thanh Bình.wav` | *N/A* | `38f7931` |
| **Added** | `dubstudio/resources/voice_previews/Thiền Tâm Đức.wav` | *N/A* | `8112602` |
| **Added** | `dubstudio/resources/voice_previews/Thiện Minh.wav` | *N/A* | `3a456c2` |
| **Added** | `dubstudio/resources/voice_previews/Thái Sơn.wav` | *N/A* | `82bed55` |
| **Added** | `dubstudio/resources/voice_previews/Thùy Dung.wav` | *N/A* | `baa8801` |
| **Added** | `dubstudio/resources/voice_previews/Thục Đoan.wav` | *N/A* | `7251cf0` |
| **Added** | `dubstudio/resources/voice_previews/Trúc Ly.wav` | *N/A* | `b934115` |
| **Added** | `dubstudio/resources/voice_previews/Xuân Vĩnh.wav` | *N/A* | `0cecc13` |
| **Added** | `dubstudio/resources/voice_previews/Đoan Trang.wav` | *N/A* | `1381159` |
| **Added** | `dubstudio/resources/voice_previews/Đức Trí.wav` | *N/A* | `bfddd42` |
| **Added** | `dubstudiov2.ico` | *N/A* | `f4ea896` |
| **Added** | `frontend/index.html` | *N/A* | `710810c` |
| **Added** | `frontend/package-lock.json` | *N/A* | `8460bb2` |
| **Added** | `frontend/package.json` | *N/A* | `c876b7a` |
| **Added** | `frontend/src/App.tsx` | *N/A* | `722279c` |
| **Added** | `frontend/src/api/bridge.ts` | *N/A* | `a2cfc1f` |
| **Added** | `frontend/src/components/Sidebar.tsx` | *N/A* | `30f9658` |
| **Added** | `frontend/src/components/StudioWorkspace.tsx` | *N/A* | `b1021f9` |
| **Added** | `frontend/src/components/TitleBar.tsx` | *N/A* | `4f8c27b` |
| **Added** | `frontend/src/components/audio/AudioMixerDeck.tsx` | *N/A* | `a9bb8fe` |
| **Added** | `frontend/src/components/common/FloatingContextMenu.tsx` | *N/A* | `0af2af4` |
| **Added** | `frontend/src/components/dialogs/EditSentenceModal.tsx` | *N/A* | `93c9457` |
| **Added** | `frontend/src/components/export/MergeExportView.tsx` | *N/A* | `29df05b` |
| **Added** | `frontend/src/components/icons/StudioIcons.tsx` | *N/A* | `b1c226a` |
| **Added** | `frontend/src/components/modals/ManualTranslateModal.tsx` | *N/A* | `eb45c91` |
| **Added** | `frontend/src/components/projects/ProjectsView.tsx` | *N/A* | `0742cb7` |
| **Added** | `frontend/src/components/settings/SettingsModal.tsx` | *N/A* | `f7b38da` |
| **Added** | `frontend/src/components/subtitles/SubtitleEditor.tsx` | *N/A* | `a2a6bf9` |
| **Added** | `frontend/src/components/subtitles/SubtitleStylePanel.tsx` | *N/A* | `6c9afc5` |
| **Added** | `frontend/src/components/timeline/StudioTimeline.tsx` | *N/A* | `f6bbd7a` |
| **Added** | `frontend/src/components/tools/ToolsView.tsx` | *N/A* | `1e51dc6` |
| **Added** | `frontend/src/components/tutorial/TutorialModal.tsx` | *N/A* | `1c4b260` |
| **Added** | `frontend/src/components/updates/UpdatesModal.tsx` | *N/A* | `49d8ee5` |
| **Added** | `frontend/src/components/video/WYSIWYGPlayer.tsx` | *N/A* | `3a1d3ee` |
| **Added** | `frontend/src/index.css` | *N/A* | `2c7cd81` |
| **Added** | `frontend/src/main.tsx` | *N/A* | `305845d` |
| **Added** | `frontend/tsconfig.json` | *N/A* | `d012cf9` |
| **Added** | `frontend/tsconfig.node.json` | *N/A* | `2fdf7d2` |
| **Added** | `frontend/tsconfig.tsbuildinfo` | *N/A* | `2d1f506` |
| **Added** | `frontend/vite.config.ts` | *N/A* | `e06f895` |
| **Added** | `scripts/inspect_ui.py` | *N/A* | `6f7be99` |
| **Added** | `start_app_v2.py` | *N/A* | `67933f3` |
| **Added** | `tests/test_css_lock.py` | *N/A* | `fa13a19` |
| **Added** | `tests/test_parity_audit_b1_b6.py` | *N/A* | `09f5395` |
| **Added** | `tests/test_v2_frontend_bridge.py` | *N/A* | `487e319` |
| **Added** | `tests/test_v2_full_pipeline_and_wysiwyg.py` | *N/A* | `4de58dd` |
| **Deleted** | `RELEASE_AUDIT.md` | `57d3840` | *N/A* |
| **Deleted** | `dubstudio/llm/fit_rewrite.md` | `8a42461` | *N/A* |
| **Deleted** | `dubstudio/llm/translate.md` | `81593aa` | *N/A* |
| **Deleted** | `ui/__init__.py` | `8a461a8` | *N/A* |
| **Deleted** | `ui/app.py` | `476dba6` | *N/A* |
| **Deleted** | `ui/dialogs/component_update_dialog.py` | `f8ee34f` | *N/A* |
| **Deleted** | `ui/dialogs/gpu_prompt.py` | `2fcafd6` | *N/A* |
| **Deleted** | `ui/dialogs/manual_translate_dialog.py` | `fa172cc` | *N/A* |
| **Deleted** | `ui/dialogs/welcome_tutorial_dialog.py` | `4a72d75` | *N/A* |
| **Deleted** | `ui/icons.py` | `772f300` | *N/A* |
| **Deleted** | `ui/main_window.py` | `9b05fbc` | *N/A* |
| **Deleted** | `ui/pages/__init__.py` | `4f31133` | *N/A* |
| **Deleted** | `ui/pages/merge_page.py` | `85a113c` | *N/A* |
| **Deleted** | `ui/pages/projects_page.py` | `56491ee` | *N/A* |
| **Deleted** | `ui/pages/settings_page.py` | `141576d` | *N/A* |
| **Deleted** | `ui/pages/studio_page.py` | `1b27222` | *N/A* |
| **Deleted** | `ui/pages/subtitle_export_page.py` | `88994e6` | *N/A* |
| **Deleted** | `ui/resources/arrow_down.svg` | `a34f2a5` | *N/A* |
| **Deleted** | `ui/resources/arrow_up.svg` | `3975abb` | *N/A* |
| **Deleted** | `ui/theme.py` | `ca4df9e` | *N/A* |
| **Deleted** | `ui/widgets/__init__.py` | `5af2738` | *N/A* |
| **Deleted** | `ui/widgets/bento_card.py` | `9cbc464` | *N/A* |
| **Deleted** | `ui/widgets/range_slider.py` | `8d14a1c` | *N/A* |
| **Deleted** | `ui/widgets/subtitle_editor.py` | `354d9b5` | *N/A* |
| **Deleted** | `ui/widgets/subtitle_style_panel.py` | `c301303` | *N/A* |
| **Deleted** | `ui/widgets/switch.py` | `22f30f8` | *N/A* |
| **Deleted** | `ui/widgets/timeline_ruler.py` | `dea9d63` | *N/A* |
| **Deleted** | `ui/widgets/video_editor_overlay.py` | `09b6401` | *N/A* |
| **Deleted** | `ui/widgets/video_player.py` | `1c45938` | *N/A* |
| **Deleted** | `ui/workers.py` | `e0b6f2d` | *N/A* |

---

## 3. Lịch sử Git Commits Kể từ `v1.1.3`

- **[Bản phát hành này / HEAD]** Release v2.0.0: Next-Gen Studio UI (React/Tailwind + PyWebView), Dynamic Ports, Zero PyQt6, and Syllable-Aware LLM Fit
- [`a307ba2`] Update AGENTS.md: Refine release push protocol and comparison rules

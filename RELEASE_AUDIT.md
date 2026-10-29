# DubStudio Release Audit — Tag-to-Tag Comparison

- **Mục tiêu phát hành:** `v2.0.2`
- **Phiên bản gốc đối chiếu:** `v2.0.1`
- **Thời gian kiểm toán:** `2026-10-29 18:31:28`
- **Tổng số file thay đổi:** `29` (26 sửa đổi, 2 thêm mới, 1 đã xóa)

---

## 1. Bảng Danh mục Chi tiết Các File Thay đổi (`v2.0.1..HEAD`)

| Trạng thái | Đường dẫn File | SHA cũ (v2.0.1) | SHA mới (HEAD) |
|:---|:---|:---|:---|
| **Modified** | `AGENTS.md` | `9d08956` | `61fb524` |
| **Modified** | `PROGRESS.md` | `f9d8d06` | `9715d8b` |
| **Modified** | `RELEASE_NOTES.md` | `f7cf946` | `0c30782` |
| **Modified** | `dubstudio/cli.py` | `0a29d18` | `db48588` |
| **Modified** | `dubstudio/llm/cdp_gemini.py` | `7d5b40c` | `2edd601` |
| **Modified** | `dubstudio/llm/fit_rewrite.py` | `0feb146` | `3e945ac` |
| **Modified** | `dubstudio/llm/gemini.py` | `cd489ff` | `519e955` |
| **Modified** | `dubstudio/stages/asr.py` | `f73e0ec` | `7b62d2c` |
| **Modified** | `dubstudio/stages/fit.py` | `9431310` | `acdb667` |
| **Modified** | `dubstudio/stages/mix.py` | `22a6474` | `031f8f1` |
| **Modified** | `dubstudio/stages/translate.py` | `7372516` | `d01b78a` |
| **Modified** | `dubstudio/subtitles/cue_split.py` | `b8ac840` | `d1b37b5` |
| **Modified** | `dubstudio/subtitles/sentence_align.py` | `21aa067` | `23f7970` |
| **Modified** | `dubstudio/text/vi_normalize.py` | `366275f` | `3b6dae3` |
| **Modified** | `dubstudio/version.py` | `98853b3` | `bdd306c` |
| **Modified** | `frontend/package.json` | `2fde240` | `71461eb` |
| **Modified** | `frontend/src/App.tsx` | `4e06a17` | `a4c6303` |
| **Modified** | `frontend/src/api/bridge.ts` | `a2cfc1f` | `da9b1b6` |
| **Modified** | `frontend/src/components/Sidebar.tsx` | `30f9658` | `c0d2289` |
| **Modified** | `frontend/src/components/StudioWorkspace.tsx` | `b1021f9` | `48c83de` |
| **Modified** | `frontend/src/components/export/MergeExportView.tsx` | `29df05b` | `9e26c05` |
| **Modified** | `frontend/src/components/subtitles/SubtitleEditor.tsx` | `a2a6bf9` | `f6c3bc8` |
| **Modified** | `frontend/src/components/timeline/StudioTimeline.tsx` | `f6bbd7a` | `2376d30` |
| **Modified** | `frontend/src/components/video/WYSIWYGPlayer.tsx` | `ce890c8` | `73a214a` |
| **Modified** | `start_app.py` | `0063946` | `ca6b282` |
| **Modified** | `tests/test_vi_normalize.py` | `e039eb7` | `64565f6` |
| **Added** | `tests/test_v202_gemini_and_orig_voice.py` | *N/A* | `1ab4993` |
| **Added** | `tests/test_v202_subtitle_edit_and_asr_reconnect.py` | *N/A* | `23f19f0` |
| **Deleted** | `RELEASE_AUDIT.md` | `4d1ad5a` | *N/A* |

---

## 2. Lịch sử Git Commits Kể từ `v2.0.1`

- **[Bản phát hành này / HEAD]** Release v2.0.2: Timeline Ruler 5s, Ghost Range Leak Fix, Vietnamese DP Subtitle Grammar Protection, and Dynamic Version Badge
- [`dcc0d99`] Update README.md

# DubStudio Release Audit — Tag-to-Tag Comparison

- **Mục tiêu phát hành:** `v2.0.1`
- **Phiên bản gốc đối chiếu:** `v2.0.0`
- **Thời gian kiểm toán:** `2026-10-27 19:19:56`
- **Tổng số file thay đổi:** `11` (9 sửa đổi, 1 thêm mới, 1 đã xóa)

---

## 1. Tổng hợp toàn diện các tính năng & Lỗi đã sửa từ `v2.0.0`

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

## 2. Bảng Danh mục Chi tiết Các File Thay đổi (`v2.0.0..HEAD`)

| Trạng thái | Đường dẫn File | SHA cũ (v2.0.0) | SHA mới (HEAD) |
|:---|:---|:---|:---|
| **Modified** | `PROGRESS.md` | `8060edb` | `f9d8d06` |
| **Modified** | `RELEASE_NOTES.md` | `7fa10d1` | `c1ebfe7` |
| **Modified** | `dubstudio/stages/mix.py` | `174ac93` | `22a6474` |
| **Modified** | `dubstudio/subtitles/ass.py` | `537559c` | `c0ba6eb` |
| **Modified** | `dubstudio/version.py` | `d5ed31b` | `98853b3` |
| **Modified** | `frontend/package.json` | `c876b7a` | `2fde240` |
| **Modified** | `frontend/src/App.tsx` | `722279c` | `4e06a17` |
| **Modified** | `frontend/src/components/video/WYSIWYGPlayer.tsx` | `3a1d3ee` | `ce890c8` |
| **Modified** | `start_app.py` | `67933f3` | `0063946` |
| **Added** | `tests/test_v201_bugfixes.py` | *N/A* | `2602753` |
| **Deleted** | `RELEASE_AUDIT.md` | `a5c778b` | *N/A* |

---

## 3. Lịch sử Git Commits Kể từ `v2.0.0`

- **[Bản phát hành này / HEAD]** Release v2.0.1: Export Subtitle Burn Fix, BGM Real-time Slider Sync (100% Default), and Project Subtitle Status Fix

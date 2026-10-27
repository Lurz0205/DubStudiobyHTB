# DubStudio Release Audit — Tag-to-Tag Comparison

- **Mục tiêu phát hành:** `v2.0.1`
- **Phiên bản gốc đối chiếu:** `v2.0.0`
- **Thời gian kiểm toán:** `2026-10-27 19:32:13`
- **Tổng số file thay đổi:** `12` (10 sửa đổi, 1 thêm mới, 1 đã xóa)

---

## 1. Tổng hợp toàn diện các tính năng & Lỗi đã sửa từ `v2.0.0`

# DubStudio v2.0.1 — Bản Vá Lỗi Toàn Diện: Khắc Phục Lỗi Phụ Đề Xuất, Hòa Âm BGM & Trạng Thái Dự Án

Bản cập nhật bảo trì **DubStudio v2.0.1** tập trung giải quyết triệt để 3 lỗi phát sinh sau bản v2.0.0, bảo đảm quy trình làm việc từ khâu biên tập, tạo lại giọng đọc đến kết xuất video luôn đồng bộ và chính xác tuyệt đối:

---

### 🌟 Các Điểm Nâng Cấp & Sửa Lỗi Chính Trên v2.0.1:

#### 1. Khắc Phục Triệt Để Lỗi Phụ Đề Xuất Ra Vẫn Là Phụ Đề Cũ Của Lần Đầu Tạo
- **Nguyên nhân trước đây:** Thuật toán trích xuất phụ đề trong `ass.py` ưu tiên đọc các lát cắt phụ (`sub_slices`) nhưng không kiểm tra đối chiếu lại với câu thoại mới sau khi rút gọn (`fit_rewrite`) hoặc chỉnh sửa câu thủ công. Điều này khiến video xuất ra vẫn mang phụ đề ban đầu dù giọng đọc đã cập nhật câu mới.
- **Giải pháp trên v2.0.1:** Bổ sung cơ chế đối chiếu chuỗi chuẩn hóa `_norm_cmp`. Nếu nội dung lát cắt cũ không khớp với câu thoại hiện tại, hệ thống lập tức loại bỏ lát cắt rác và tự động phân tách lại dòng phụ đề mới khớp 100% từng từ với câu thoại đã rút gọn. Đồng thời đồng bộ tức thì cấu trúc phụ đề ngay khi người dùng bấm "Tạo lại giọng đọc" trong bảng sửa câu.

#### 2. Sửa Lỗi Điều Chỉnh Âm Lượng Nhạc Nền (BGM) & Đặt Mặc Định BGM 100%
- **Nguyên nhân trước đây:** Trình phát xem trước ưu tiên nạp tệp âm thanh đã hòa trộn sẵn (`voice_track.wav`) thay vì giọng đọc gốc thuần (`voice_raw.wav`), khiến nhạc nền bị "nướng chết" vào rãnh giọng. Đồng thời vòng lặp animation của trình xem trước bị dính lỗi *stale closure*, liên tục ghi đè lại mức âm lượng cũ khi kéo thanh trượt lúc đang phát.
- **Giải pháp trên v2.0.1:**
  - Tách bạch hoàn toàn rãnh giọng đọc thuần (`voice_raw.wav`) và rãnh nhạc nền (`audio/bgm.wav`) trên trình phát xem trước.
  - Sử dụng tham chiếu trực tiếp `syncAudioVolumesRef` giúp việc kéo thanh trượt âm lượng BGM hay Thuyết minh thay đổi âm lượng tức thì trong thời gian thực (real-time).
  - Nâng mức âm lượng mặc định của nhạc nền (BGM) lên **100%** (chuẩn cân bằng hoàn hảo với giọng đọc).
  - Bổ sung cơ chế lưu trữ và tự động chuyển đổi thang âm lượng 0–200% xuyên suốt từ giao diện sang tệp hòa âm `mix_settings.json` khi xuất video.

#### 3. Sửa Lỗi Dự Án Mới Tạo Bị Đánh Dấu Đã Hoàn Thành Phụ Đề
- **Nguyên nhân trước đây:** Khi tạo dự án mới, hệ thống tạo sẵn tệp `segments.json` chứa danh sách rỗng `[]`, khiến trang danh sách dự án nhận diện tệp tồn tại và tự động tick xanh hoàn thành bước "Phụ đề".
- **Giải pháp trên v2.0.1:** Cập nhật cơ chế kiểm tra tiến độ dự án: chỉ đánh dấu bước "Phụ đề" khi `segments.json` thực sự chứa ít nhất 1 câu thoại đã nhận dạng/dịch thuật (`len(segments) > 0`). Dự án mới tạo sẽ hiển thị chính xác trạng thái ban đầu là "Video gốc".

---

### 📋 Hướng Dẫn Cập Nhật & Nâng Cấp:
- **Tự động cập nhật:** Ứng dụng tích hợp công nghệ cập nhật thông minh (Velopack). Khi mở ứng dụng, hệ thống sẽ tự động thông báo và tải gói nâng cấp delta nhỏ gọn.
- **Người dùng mới hoặc cài lại:** Tải tệp `DubStudio-win-Setup.exe` ở phần Assets bên dưới và cài đặt tự động trong 1 click. Toàn bộ các dự án và mô hình AI đã tải trong máy đều được giữ nguyên 100% tại `%LocalAppData%\DubStudioData`.

---

---

## 2. Bảng Danh mục Chi tiết Các File Thay đổi (`v2.0.0..HEAD`)

| Trạng thái | Đường dẫn File | SHA cũ (v2.0.0) | SHA mới (HEAD) |
|:---|:---|:---|:---|
| **Modified** | `PROGRESS.md` | `8060edb` | `f9d8d06` |
| **Modified** | `RELEASE_NOTES.md` | `7fa10d1` | `f7cf946` |
| **Modified** | `dubstudio/stages/mix.py` | `174ac93` | `22a6474` |
| **Modified** | `dubstudio/subtitles/ass.py` | `537559c` | `c0ba6eb` |
| **Modified** | `dubstudio/version.py` | `d5ed31b` | `98853b3` |
| **Modified** | `frontend/package.json` | `c876b7a` | `2fde240` |
| **Modified** | `frontend/src/App.tsx` | `722279c` | `4e06a17` |
| **Modified** | `frontend/src/components/video/WYSIWYGPlayer.tsx` | `3a1d3ee` | `ce890c8` |
| **Modified** | `scripts/audit_release_diff.py` | `ce94d30` | `fadb7fd` |
| **Modified** | `start_app.py` | `67933f3` | `0063946` |
| **Added** | `tests/test_v201_bugfixes.py` | *N/A* | `2602753` |
| **Deleted** | `RELEASE_AUDIT.md` | `a5c778b` | *N/A* |

---

## 3. Lịch sử Git Commits Kể từ `v2.0.0`

- **[Bản phát hành này / HEAD]** Release v2.0.1: Export Subtitle Burn Fix, BGM Real-time Slider Sync (100% Default), and Project Subtitle Status Fix
- [`9070cca`] Release v2.0.1: Export Subtitle Burn Fix, BGM Real-time Slider Sync (100% Default), and Project Subtitle Status Fix
- [`1f5dad8`] Release v2.0.1: Export Subtitle Burn Fix, BGM Real-time Slider Sync (100% Default), and Project Subtitle Status Fix

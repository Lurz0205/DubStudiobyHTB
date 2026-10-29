# PROGRESS.md — DubStudio Progress

## Đã hoàn thành (Done)
- **1. Sửa thước đo Timeline (Ruler 5s):**
  - Hiển thị nhãn thời gian cố định 5 giây 1 số (`00:00`, `00:05`, `00:10`...) dạng `MM:SS`, không in số dày đặc gây rối mắt; giữ vạch phụ tinh tế 1s khi zoom.
- **2. Khắc phục triệt để rò rỉ vùng giữ âm gốc ("ghost ranges") giữa các project:**
  - Sửa `App.tsx`, `StudioWorkspace.tsx`, `MergeExportView.tsx` reset `keep_original_ranges = []` khi nạp hoặc tạo dự án mới, ngăn mang nhãn từ dự án trước sang.
  - Sửa `mix.py` lọc bỏ các đoạn giữ âm gốc nằm ngoài thời lượng video.
- **3. Cải tiến tách phụ đề DP (`cue_split.py`):**
  - Giữ trọn vẹn cụm cố định ("thẹn với lòng"), ngắt đúng dấu phẩy tự nhiên.
- **4. Kiểm thử & Đóng gói:**
  - `pytest tests/ -q`: **191 passed, 10 skipped (100% PASS)**.
  - Đóng gói hoàn tất `dist\DubStudio\DubStudio.exe`, selftest passed (Exit 0).

## Tiếp theo (Next)
- Theo dõi trải nghiệm người dùng thực tế.

## Vấn đề mở (Open issues)
- Không có lỗi tồn đọng.

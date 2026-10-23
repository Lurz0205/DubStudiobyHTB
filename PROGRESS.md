# PROGRESS.md — DubStudio Progress

## Đã hoàn thành (Done)
- Tách rời triệt để môi trường: `start.bat` (dev: `workspace/`) và `DubStudio.exe` (packaged: `%LocalAppData%\DubStudio\workspace`).
- Sửa lỗi âm thanh đọc lúc nhanh lúc chậm: xóa bỏ cơ chế ép chậm 0.90x nhân tạo, giới hạn tăng tốc tối đa 1.10x (`fit.py`), đồng bộ tốc độ hiển thị trên bảng.
- Sửa lỗi mất phụ đề / nhảy vị trí khi dịch: đồng bộ 100% `segments.json` với `units.json` khi câu bị tách/gộp (`translate.py`), reset cue cho câu tách mới (`sentence_align.py`).
- Pre-warm tiến trình VieNeu-TTS worker ngay khi mở app và mở dự án, tránh độ trễ khi tạo lại TTS từng câu.
- Dọn dẹp ổ đĩa giải phóng > 6.1 GB: xóa `dist/releases`, `build/`, chuyển `models/` thành Directory Junction tới `%LocalAppData%\DubStudio\models`.
- 130/130 unit tests passed (`pytest tests/ -q`).

## Tiếp theo (Next)
- Hoàn tất đóng gói `dist\DubStudio\DubStudio.exe`.
- Đẩy mã nguồn lên GitHub `main` qua `scripts/push_code_to_github.py`.
- Người dùng kiểm tra thực tế trên `DubStudio.exe`: tạo phụ đề, nghe thử TTS, tốc độ đọc tự nhiên và đồng đều.

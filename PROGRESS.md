# PROGRESS.md — Phase 1 Performance & Tab Switch Overhaul

## Đã hoàn thành (Done)
- Chuyển `QT_MEDIA_BACKEND` sang `ffmpeg` (thay thế WMF COM lock).
- Loại bỏ `setCellWidget`: dùng `VoiceComboDelegate` và Action Item, giảm thời gian nạp 250 dòng phụ đề từ 1.200ms xuống 8.5ms.
- Bất đồng bộ hóa `setup_job_audio` qua `AudioPrepWorker` (`QThread` có `generation_id` chống chồng lấn).
- Đẩy `probe_file` và nạp metadata video khỏi luồng Main Thread.
- Debounce 300ms + bất đồng bộ hóa ghi đĩa JSON và HTTP trong `_save_style_to_job`.
- Chặn bẫy nạp lại job trùng lặp khi chuyển tab trong `main_window.py`.
- Benchmark chuyển tab khi có sẵn 250 phụ đề + audio: đạt 10ms - 35ms (giảm từ 3.000ms - 4.000ms).
- 100% unit tests passed (`pytest tests/ -q`: 130/130 passed).
- Đóng gói hoàn tất `dist\DubStudio\DubStudio.exe` và push code lên GitHub `main` (commit: `9cf5072`).

## Tiếp theo (Next)
- Người dùng mở trực tiếp `dist\DubStudio\DubStudio.exe` để trải nghiệm độ mượt khi chuyển tab và thao tác phụ đề.
- Tiếp tục bước sang tách tiến trình Sidecar / Python Embeddable theo lộ trình thương mại hóa.

# DECISIONS.md — Kiến trúc & Lựa chọn công nghệ

Tài liệu này ghi lại các quyết định kỹ thuật quan trọng của dự án `dubstudio`.

## Phase 0: Khởi tạo kiến trúc
- **Môi trường**: Windows 11, Python 3.11 trong `.venv`.
- **Phân tách công đoạn**: Mỗi tiến trình nặng (ASR, Demucs, TTS) chạy trong một subprocess độc lập nhằm giải phóng bộ nhớ RAM/VRAM ngay sau khi hoàn thành.
- **Dữ liệu trung gian**: Lưu theo định dạng JSON chuẩn (`state.json`, `segments.json`) và âm thanh WAV 16kHz mono.

## Phase 2: Quyết định lựa chọn công nghệ qua Benchmark thực tế
1. **ASR (Nhận dạng tiếng Trung)**:
   - **Lựa chọn**: `faster-whisper` với model `large-v3-turbo` (`int8_float16`, VAD filter 500ms).
   - **Lý do**: Peak VRAM chỉ ~1.44 GB (rất an toàn cho card 4GB RTX 2050). Thời gian nhận dạng cực nhanh: clip 10 phút chỉ mất ~30 giây.
2. **Vocal/BGM Separation (Tách giọng nói / Nhạc nền)**:
   - **Lựa chọn**: `audio-separator[gpu]` với mô hình BS-RoFormer (`model_bs_roformer_ep_317_sdr_12.9755.ckpt`, SDR 12.9755) chạy trên GPU CUDA.
   - **Lý do**: Khắc phục triệt để nhược điểm của `htdemucs` (bị triệt tiêu pha, nuốt âm nền pumping/swallowing khiến BGM lúc to lúc nhỏ và giật). BS-RoFormer đạt chất lượng tách vocal và bảo toàn nhạc nền SOTA hiện nay, chạy trong subprocess độc lập để giải phóng 100% VRAM ngay sau khi xử lý. Đã gỡ bỏ `demucs` và dọn dẹp sạch cache `HTDemucs`.
3. **TTS (Tổng hợp giọng đọc tiếng Việt)**:
   - **Lựa chọn**: `VieNeu-TTS-v3-turbo` (qua SDK `vieneu`).
   - **Giọng mặc định theo người dùng lựa chọn**:
     - **Nam**: **Minh Quân** (alias của `Hải Đăng`, phong cách tự nhiên, tốc độ ~20.4 ký tự/giây).
     - **Nữ**: **Quỳnh Anh** (phong cách đọc truyện tự nhiên, tốc độ ~17.0 ký tự/giây).
   - **Kho 25 giọng đọc phong phú sẵn có (Đủ 3 miền Bắc - Trung - Nam, kể chuyện & tin tức)**:
     - **Miền Bắc**:
       - Nam: Minh Quân (Hải Đăng), Thiện Minh, Minh Đức, Phạm Tuyên, Xuân Vĩnh, Thanh Bình, Quốc Tuấn, Thiền Tâm Đức, Adam bựa.
       - Nữ: Quỳnh Anh, Trúc Ly, Mai Anh, Ngọc Huyền, Ngọc Linh, Đoan Trang.
     - **Miền Nam**:
       - Nam: Thái Sơn, Minh Triết, Đức Trí, Adam.
       - Nữ: Thùy Dung, Thục Đoan, Mỹ Duyên, Kim Thanh.
     - **Miền Trung**:
       - Nam: Quang Sơn.
       - Nữ: Ngọc Trân.

4. **Video Encoding & Audio Mastering**:
   - **Video**: Chuỗi ưu tiên `h264_nvenc` -> `h264_mf` (Windows Media Foundation Hardware GPU, đạt tốc độ ~10x) -> fallback `libx264` (CPU).
   - **Audio**: Xuất chuẩn 48.000 Hz Stereo AAC 192 kbps, hỗ trợ ducking BGM tùy biến từ 0% - 100% qua UI.

## Cập nhật Data Contract: Câu liền mạch & Cues phụ đề theo số từ
1. **Đơn vị lồng tiếng (units)**:
   - Ranh giới câu chỉ sau `。？！…`, hoặc khoảng nghỉ >= 0.8s (không dấu), hoặc đổi người nói. Dấu `，、；` không phải ranh giới câu.
   - Mảnh chưa hết câu luôn gộp tiếp với mảnh sau (cùng người nói, nghỉ <= 1.5s) cho đến hết câu.
   - Câu > 15s hoặc > 80 chữ Hán: ghi các vế vào `clauses: [{"start": float, "end": float, "zh": str}]`, dịch cả câu trong MỘT mục kèm `vi_clauses`.
2. **Cấu trúc Subtitle Cues (`cues`)**:
   - Mỗi unit lưu `cues: [{"start": float, "end": float, "text": str, "locked": bool}]`.
   - Tách chạy SAU khi bản dịch và timeline cuối đã xong, trên một câu hoàn chỉnh bằng thuật toán quy hoạch động (DP) cục bộ không qua LLM.
   - Dòng người dùng sửa tay (Enter thủ công) đặt `locked: true`, không bị ghi đè khi đổi N và chạy lại "Tách tự động".
   - `get_segment_slices()` ưu tiên `cues` lên hàng đầu để xuất phụ đề ASS, SRT và live preview đồng bộ 100%.

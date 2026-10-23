# DubStudio v1.1.1 (Bản vá lỗi - Patch Release)

Bản cập nhật v1.1.1 tập trung sửa các lỗi quan trọng trong quá trình nhận dạng giọng nói, quản lý bộ nhớ đệm và cải thiện trải nghiệm người dùng:

### 🚀 Các cải tiến & Lỗi đã khắc phục:
1. **Khắc phục triệt để lỗi ASR `[ASR_FAILED]` trên mô hình SenseVoice-Small:**
   - Sửa lỗi `RuntimeError: NOT_FOUND: "None": No such file or directory Error #2` do FunASR không tìm thấy tệp tokenizer SentencePiece. Tự động liên kết và trỏ trực tiếp đến tệp `chn_jpn_yue_eng_ko_spectok.bpe.model` (và `bpe.model`).
   - Tích hợp VAD offline cục bộ (`models/fsmn-vad`) giúp nhận dạng mượt mà không phụ thuộc tải mạng khi chạy.
   - Thêm cơ chế tự động chuyển đổi sang CPU (Auto Fallback) nếu card đồ họa gặp sự cố.

2. **Dọn sạch bộ nhớ đệm & Khắc phục lỗi trùng lặp phụ đề khi xóa dự án:**
   - Chuyển toàn bộ bộ nhớ đệm dịch thuật LLM và tối ưu thời lượng (`.cache/llm`) từ thư mục chung vào trực tiếp từng dự án (`job.workspace/.cache/llm`).
   - Khi xóa dự án, toàn bộ phụ đề và dữ liệu tạm sẽ được dọn sạch 100%. Khi thêm lại cùng một video, hệ thống sẽ thực hiện dịch mới từ đầu qua Gemini thay vì tự động nạp phụ đề cũ từ cache.

3. **Sửa lỗi mất tiếng xem thử video (Video Preview):**
   - Video mới thêm khi chưa có các track âm thanh tách rời sẽ tự động phát âm thanh gốc của video ở mức âm lượng 100%, khắc phục hiện tượng video xem thử bị mất tiếng.

4. **Bổ sung tiền kiểm (Pre-flight Gate) cho nút "2. Tạo lồng tiếng":**
   - Chặn người dùng bấm nút tạo lồng tiếng khi chưa hoàn tất bước tạo phụ đề tiếng Việt, hiển thị hướng dẫn thân thiện thay vì ném lỗi thiếu tệp và làm mất video preview.

5. **Sửa lỗi hiển thị dung lượng âm khi tải mô hình > 2 GB:**
   - Khắc phục lỗi tràn số nguyên 32-bit có dấu trong tín hiệu Qt khiến mô hình `faster-whisper large-v3` hiển thị thành số âm (`-1002.9 MB`).

6. **Khắc phục lỗi mạng nền `[WinError 10013]` trên Windows:**
   - Chuyển `asyncio` event loop policy sang `WindowsSelectorEventLoopPolicy` cho tiến trình API FastAPI chạy nền, loại bỏ cảnh báo socketpair trên Windows 11.

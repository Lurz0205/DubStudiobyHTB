# fit_rewrite.md — Biên kịch lồng tiếng thoát ý & cân bằng thời lượng hai chiều

## Vai trò
Bạn là đạo diễn kiêm chuyên gia biên kịch lồng tiếng tiếng Việt chuyên nghiệp.
Trong phim/video, khi đọc thử giọng thật (TTS), một số câu bị lệch thời lượng so với video:
- Có câu đọc QUÁ DÀI dẫn đến đè âm thanh lên câu tiếp theo (`direction = "shorter"`).
- Có câu đọc QUÁ NGẮN, đọc xong để khoảng trống im lặng quá lâu so với thời lượng người nói trên hình (`direction = "longer"`).

Nhiệm vụ của bạn là biên tập, dịch lại "THOÁT Ý" sao cho câu đọc vừa khít khung thời gian của video, câu thoại tự nhiên, gãy gọn, giữ trọn vẹn ý chính, xưng hô và cảm xúc.

## Bối cảnh video
{{analysis_json}}

## Danh sách các câu cần viết lại (Mỗi câu là một dòng đơn không ngắt dòng)
Mỗi phần tử gồm:
- id: Mã phân đoạn
- zh: Câu gốc tiếng Trung
- vi_text: Câu tiếng Việt hiện tại (dòng đơn)
- tts_text: Bản đọc hiện tại (dòng đơn, số/đơn vị đã thành chữ tiếng Việt)
- current_words: Số từ hiện tại của tts_text
- target_words: Số từ mục tiêu lý tưởng cần đạt
- min_words: Số từ tối thiểu BẮT BUỘC ĐẠT ĐƯỢC (không được viết dưới mức này)
- max_words: Số từ tối đa cho phép
- words_to_remove: Số từ cần cắt giảm (nếu direction="shorter")
- edit_instruction: Chỉ đạo biên kịch cụ thể cho câu này
- measured_dur: Thời lượng thực tế khi đọc (giây)
- max_audio_dur: Thời lượng âm thanh tối đa cho phép trên video (giây)
- direction: "shorter" (cần rút gọn) hoặc "longer" (cần mở rộng)
- context: Ngữ cảnh câu liền trước và liền sau
{{lines_json}}

## Nguyên tắc biên kịch lồng tiếng (TỐI QUAN TRỌNG)

### 1. direction = "shorter" (2 CẤP ĐỘ BIÊN TẬP THEO SỐ TỪ CẦN BỚT):
- **CẤP ĐỘ 1 — GỌT TỈA VI PHẪU (Ưu tiên tối đa khi words_to_remove <= 4 từ):**
  - Giữ nguyên 85% – 90% câu gốc `vi_text`. **TUYỆT ĐỐI KHÔNG TÓM TẮT HAY VIẾT LẠI TOÀN BỘ CÂU!**
  - Chỉ nhặt bỏ đúng số từ đệm, hư từ hoặc từ phụ rườm rà (ví dụ: *"thì"*, *"mà"*, *"rằng"*, *"những"*, *"các"*, *"một cách"*, *"vô cùng"*, *"được xem là"*, *"có thể nói là"*...).
  - Hoặc thay thế các cụm từ dài dòng bằng từ ghép ngắn hơn (ví dụ: *"ngay trong thời điểm này"* -> *"ngay lúc này"*, *"thực hiện việc kiểm tra"* -> *"kiểm tra"*).
  - Khung câu, ý chính và cấu trúc câu gốc phải được bảo toàn nguyên vẹn.

- **CẤP ĐỘ 2 — DIỄN ĐẠT THOÁT Ý SÚC TÍCH (Khi words_to_remove >= 5 từ):**
  - Dựa vào ý chính của câu gốc `zh` và `vi_text`, hãy diễn đạt lại bằng khẩu ngữ đời thường súc tích, gãy gọn nhất.
  - **TUYỆT ĐỐI KHÔNG CẮT CỤT LỦN:** Nghiêm cấm cắt xén cơ học, bỏ lửng câu, làm câu què quặt vô nghĩa. Câu viết lại bắt buộc phải là câu hoàn chỉnh ngữ pháp, tự nhiên, nghe êm tai.
  - **CHỐNG HỞ THỜI LƯỢNG:** Bắt buộc đếm từng từ (âm tiết cách nhau bởi khoảng trắng). **TUYỆT ĐỐI KHÔNG ĐƯỢC VIẾT DƯỚI `min_words`** để tránh giọng đọc dừng quá sớm gây hở miệng chết video. Số từ phải nằm khít trong khoảng `[min_words, max_words]`, sát nhất với `target_words`.

### 2. direction = "longer" (MỞ RỘNG THOÁT Ý TỰ NHIÊN):
- Diễn đạt đầy đủ và thoáng hơn: làm rõ chủ ngữ, bổ ngữ mà tiếng Trung hay ngầm hiểu; thêm từ nối và ngữ khí tự nhiên của người Việt (*"thì"*, *"mà"*, *"đấy"*, *"nhé"*, *"cơ mà"*...) hợp giọng nhân vật để câu cân bằng với thời lượng người nói trên video.
- Số từ nằm trong khoảng `[min_words, max_words]`, xấp xỉ `target_words`. Tuyệt đối KHÔNG bịa thêm sự kiện, chi tiết mới.

### 3. Quy định định dạng văn bản:
- Giữ nguyên đại từ xưng hô, ngôi kể, tính cách và cảm xúc của nhân vật theo `context`.
- Cập nhật cả `vi_text` (phụ đề) và `tts_text` (bản để đọc: số, đơn vị, ký hiệu viết bằng chữ tiếng Việt). Hai bản phải cùng nghĩa.
- **ĐỊNH DẠNG MỘT DÒNG DUY NHẤT (SINGLE-LINE):** Cả `vi_text` và `tts_text` phải viết trên 1 dòng đơn duy nhất, TUYỆT ĐỐI KHÔNG chứa ký tự xuống dòng (`\n`). Hệ thống sẽ tự động phân tách câu thành các dòng phụ đề sau.
- **ĐẾM TỪ TRƯỚC KHI XUẤT:** Bắt buộc đếm số từ của `tts_text` và trả về trường `tts_word_count`.

## Định dạng đầu ra
Chỉ trả về JSON hợp lệ, mỗi id đúng một kết quả:
```json
{
  "rewritten_segments": [
    {
      "id": 1,
      "vi_text": "câu phụ đề đã biên tập thoát ý tự nhiên trên 1 dòng đơn duy nhất",
      "tts_text": "câu đọc âm thanh đã biên tập thoát ý trên 1 dòng đơn duy nhất",
      "tts_word_count": 12
    }
  ]
}
```

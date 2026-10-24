# cluster_rewrite.md — Biên kịch lồng tiếng thoát ý theo ngữ cảnh chùm câu

## Vai trò
Bạn là đạo diễn kiêm chuyên gia biên kịch lồng tiếng tiếng Việt chuyên nghiệp.
Trong video, khi đọc thử giọng thật (TTS), một số câu bị quá dài dẫn đến ÂM THANH BỊ CHÈN / ĐÈ LÊN CÂU TIẾP THEO trên timeline.

## Bối cảnh video
{{analysis_json}}

## Chùm câu đối thoại / thuyết minh
Dưới đây là một chùm câu liên tục trong video:
{{cluster_json}}

## Nhiệm vụ biên tập (TỐI QUAN TRỌNG)
1. Đối với các câu có `"is_colliding": true`:
   - **RÚT GỌN BẰNG DỊCH THOÁT Ý:** Nhìn vào câu gốc tiếng Trung `zh` và ý chính của câu, hãy viết lại bằng khẩu ngữ tiếng Việt đời thường tự nhiên, cô đọng, giàu nhạc điệu.
   - **TUYỆT ĐỐI KHÔNG CẮT CƠ HỌC CỤT LỦN:** Không cắt bỏ thô bạo làm câu mất chủ ngữ, què quặt, lủng củng. Câu phải hoàn chỉnh và nghe êm tai.
   - **CHỐNG HỞ THỜI LƯỢNG:** KHÔNG ĐƯỢC VIẾT DƯỚI `min_chars`. Giữ độ dài trong khoảng `[min_chars, max_chars]`, xấp xỉ `target_chars` để giọng đọc vừa khít thời lượng, không để lại khoảng lặng chết dài ("hở miệng") trong khi người nói trên video vẫn đang nói.
   - **Lược bỏ từ đệm thừa:** Bỏ các từ sáo rỗng ("thì là mà rằng", "có thể nói là"...), gộp mệnh đề phụ.
2. Đảm bảo tính liền mạch của cả chùm câu:
   - Giữ nguyên đại từ xưng hô, ngôi kể, sắc thái biểu cảm và sự liên kết tự nhiên với các câu xung quanh.
   - Các câu `"is_colliding": false` giữ nguyên để bảo đảm tính ổn định của video.
3. Cập nhật cả `vi_text` (phụ đề) và `tts_text` (bản để đọc: số, đơn vị viết bằng chữ).

## Định dạng đầu ra
Chỉ trả về JSON hợp lệ theo đúng cấu trúc sau:
```json
{
  "rewritten_segments": [
    {
      "id": 1,
      "vi_text": "câu phụ đề đã biên tập thoát ý tự nhiên",
      "tts_text": "câu đọc âm thanh đã biên tập thoát ý"
    }
  ]
}
```

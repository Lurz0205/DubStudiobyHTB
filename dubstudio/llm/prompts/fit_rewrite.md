# fit_rewrite.md — Chỉnh độ dài hai chiều theo số đo thật (1 yêu cầu cho tất cả đơn vị lệch)

## Vai trò
Bạn là chuyên gia biên kịch và đạo diễn lồng tiếng tiếng Việt chuyên nghiệp.
Trong video, khi đọc thử giọng thật (TTS), một số câu bị lệch thời lượng so với video:
- Có câu đọc QUÁ DÀI dẫn đến đè âm thanh lên câu sau (direction = "shorter").
- Có câu dịch QUÁ NGẮN, đọc xong để khoảng trống im lặng quá lâu so với thời lượng người nói trên hình (direction = "longer").

Hãy viết lại để câu đọc vừa vặn với khung hình, tự nhiên, gãy gọn, giữ trọn ý chính và xưng hô.

## Bối cảnh video
{{analysis_json}}

## Danh sách các câu cần viết lại
{{lines_json}}

## Nhiệm vụ biên tập
1. direction = "shorter": BẮT BUỘC viết ngắn gọn hơn, số ký tự xấp xỉ hoặc dưới target_chars. Bỏ từ đệm thừa ("thì là mà rằng", "được biết rằng", "có thể nói là"...), cô đọng ý chính, dùng từ gãy gọn.
2. direction = "longer": Thoát ý và diễn đạt đầy đủ, thoáng hơn, làm rõ chủ ngữ/vị ngữ, dùng từ nối tự nhiên để câu cân bằng với thời lượng người nói trên video (target_chars), không dịch cộc lốc nhưng KHÔNG bịa thêm sự kiện mới.
3. Giữ nguyên đại từ xưng hô, ngôi kể, mạch cảm xúc và tính liền mạch với ngữ cảnh (trong context).
4. Cập nhật cả vi_text (phụ đề) và tts_text (bản để đọc: số, đơn vị, ký hiệu viết bằng chữ).
5. CHỈ TRẢ VỀ các câu có trong danh sách trên theo đúng định dạng JSON.

## Định dạng đầu ra
Chỉ trả về JSON hợp lệ:
```json
{
  "rewritten_segments": [
    {
      "id": 1,
      "vi_text": "câu phụ đề đã chỉnh",
      "tts_text": "câu đọc âm thanh đã chỉnh"
    }
  ]
}
```

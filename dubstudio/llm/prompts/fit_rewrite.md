# fit_rewrite.md — Chỉnh độ dài hai chiều theo số đo thật (1 yêu cầu cho tất cả đơn vị lệch)

Thay thế shorten.md. Dùng sau khi máy đã tạo giọng thật và ĐO được thời lượng đọc.

## Vai trò
Bạn là biên kịch lồng tiếng tiếng Việt. Các đơn vị dưới đây, khi đọc thật, đang lệch so với khung thời gian của hình: có đơn vị đọc quá dài (phải đọc dồn), có đơn vị đọc quá ngắn (để trống nhiều). Hãy viết lại để đọc vừa khung, vẫn giữ ý, sắc thái, mức lịch sự và xưng hô.

## Bối cảnh
{{analysis_json}}

## Các đơn vị cần chỉnh
Mỗi phần tử gồm:
- id
- zh: lời gốc tiếng Trung
- vi_text, tts_text: bản hiện tại
- measured_dur: thời gian giọng đọc bản hiện tại thực sự mất (giây, đã đo)
- dur: thời gian mà khung cho phép (giây)
- direction: "shorter" (cần ngắn lại) hoặc "longer" (cần dài ra)
- target_chars: số ký tự đích của tts_text (đã tính từ tốc độ đọc đo được của chính câu này)
- min_chars, max_chars: khoảng cho phép
- prev_lines: ít nhất 5 câu liền trước để nắm ngữ cảnh liên tục
- next_lines: các câu liền sau để giữ mạch câu chuyện
- prev_vi, next_vi: câu liền trước và liền sau
{{lines_json}}

## Nguyên tắc
1. tts_text mới phải nằm trong [min_chars, max_chars], lý tưởng sát target_chars (tính cả khoảng trắng và dấu câu).
2. direction = "shorter": bỏ từ đệm và từ thừa, bỏ ý phụ lặp lại, dùng từ ngắn hơn, gộp mệnh đề. Không bỏ tên riêng và thông tin quan trọng, không đổi xưng hô, không viết kiểu điện tín.
3. direction = "longer": diễn đạt đầy đủ và thoáng hơn: làm rõ chủ ngữ và đối tượng ngầm hiểu, dùng từ nối và ngữ khí tự nhiên hợp giọng nhân vật, tách ý thành câu trọn vẹn. Tuyệt đối không thêm sự kiện, chi tiết hay ý mới mà lời gốc hoặc ngữ cảnh không có, không lặp ý cho dài.
4. Giữ giọng văn nói tự nhiên, phù hợp với style_guide.
5. Cập nhật cả vi_text (phụ đề) và tts_text (bản để đọc: số, đơn vị, ký hiệu viết thành chữ). Hai bản cùng nghĩa.
6. Nếu không thể đạt khoảng ký tự mà không bịa thêm hoặc làm mất ý chính, trả bản gần nhất có thể và ghi length_note = "short" hoặc "long"; ngược lại ghi "ok".

## Đầu ra
Chỉ trả về JSON hợp lệ, mỗi id đúng một kết quả:
```
{"lines": [{"id": 0, "vi_text": "...", "tts_text": "...", "length_note": "ok"}]}
```

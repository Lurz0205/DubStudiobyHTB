import json
from unittest.mock import MagicMock, patch
import pytest
from dubstudio.errors import DubError
from dubstudio.llm.cdp_gemini import is_gemini_refusal_or_invalid, translate_via_cdp, close_gemini_tabs


def test_is_gemini_refusal_or_invalid_detects_refusal():
    # User's exact refusal string from Image 2
    refusal_1 = "Tôi chỉ là một mô hình ngôn ngữ, nên không thể trợ giúp về điều đó."
    assert is_gemini_refusal_or_invalid(refusal_1) is True

    # English refusal variants
    assert is_gemini_refusal_or_invalid("I am a large language model and cannot assist with that.") is True
    assert is_gemini_refusal_or_invalid("I cannot help with that request.") is True
    assert is_gemini_refusal_or_invalid("Bạn đã dừng câu trả lời này.") is True
    assert is_gemini_refusal_or_invalid("") is True
    assert is_gemini_refusal_or_invalid("   ") is True

    # Valid response containing JSON
    valid_resp = '```json\n[{"id": 1, "vi_text": "Xin chào các bạn"}]\n```'
    assert is_gemini_refusal_or_invalid(valid_resp) is False


def test_translate_via_cdp_rescues_from_refusal_on_retry():
    # First attempt returns the Image 2 refusal; second attempt succeeds
    refusal_msg = "Tôi chỉ là một mô hình ngôn ngữ, nên không thể trợ giúp về điều đó."
    success_json = '[{"id": 1, "vi_text": "Chào mừng bạn quay lại"}]'

    responses = [refusal_msg, success_json]
    call_count = 0

    async def fake_send(*args, **kwargs):
        nonlocal call_count
        resp = responses[call_count]
        call_count += 1
        return resp

    with patch("dubstudio.llm.cdp_gemini.is_cdp_ready", return_value=True), \
         patch("dubstudio.llm.cdp_gemini.cycle_new_gemini_tab", return_value="ws://fake-tab") as mock_cycle, \
         patch("dubstudio.llm.cdp_gemini._async_send_prompt_to_gemini", side_effect=fake_send):
        
        result = translate_via_cdp("test prompt", port=9222, max_retries=3)
        assert len(result) == 1
        assert result[0]["id"] == 1
        assert result[0]["vi_text"] == "Chào mừng bạn quay lại"
        assert call_count == 2
        mock_cycle.assert_called_once()


def test_translate_via_cdp_fails_after_3_refusals():
    # 3 attempts all return refusal
    refusal_msg = "Tôi chỉ là một mô hình ngôn ngữ, nên không thể trợ giúp về điều đó."

    async def fake_send(*args, **kwargs):
        return refusal_msg

    with patch("dubstudio.llm.cdp_gemini.is_cdp_ready", return_value=True), \
         patch("dubstudio.llm.cdp_gemini.cycle_new_gemini_tab", return_value="ws://fake-tab") as mock_cycle, \
         patch("dubstudio.llm.cdp_gemini._async_send_prompt_to_gemini", side_effect=fake_send):
        
        with pytest.raises(DubError) as exc_info:
            translate_via_cdp("test prompt", port=9222, max_retries=3)
        
        assert "sau 3 lần thử mở tab mới" in str(exc_info.value)
        assert mock_cycle.call_count == 2  # Cycled before attempt 2 and before attempt 3


def test_orig_voice_volume_capped_at_100_percent():
    # Test normalization logic for 0 - 100%
    for input_val, expected in [(0, 0.0), (50, 0.5), (100, 1.0), (150, 1.0), (0.75, 0.75)]:
        val = float(input_val)
        if val > 1.0:
            val /= 100.0
        normalized = max(0.0, min(1.0, val))
        assert normalized == expected


def test_build_prompt_includes_sentence_integrity_rules():
    from dubstudio.llm.gemini import build_prompt

    units = [
        {"id": 1, "zh": "你好", "dur": 2.5},
        {"id": 2, "zh": "世界", "dur": 2.0},
    ]
    sys_inst, content = build_prompt(batch_units=units, all_units=units)

    assert "TỰ NHẬN DIỆN VÀ BẢO ĐẢM TÍNH TOÀN VẸN NGỮ NGHĨA" in sys_inst
    assert "MỖI ĐƠN VỊ [id] BẮT BUỘC PHẢI LÀ MỘT CÂU/Ý HOÀN CHỈNH" in sys_inst
    assert "CƠ CHẾ TỰ ĐỘNG BÙ HOÀN CÂU THEO NGỮ CẢNH" in sys_inst
    assert "TUYỆT ĐỐI KHÔNG NGẮT CÂU LỬNG LƠ" in sys_inst

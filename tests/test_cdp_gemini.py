"""Unit tests for Gemini Web CDP translation integration."""
import pytest
from dubstudio.llm.cdp_gemini import extract_json_translations, is_cdp_ready


def test_extract_json_translations_codeblock():
    sample = """Dưới đây là bản dịch hoàn chỉnh:
```json
{
  "translations": [
    {"id": 1, "vi": "Chào bạn, hôm nay thế nào?"},
    {"id": 2, "vi": "Tôi cảm thấy rất tuyệt."}
  ]
}
```
Chúc bạn một ngày tốt lành!"""
    res = extract_json_translations(sample)
    assert len(res) == 2
    assert res[0]["id"] == 1
    assert res[0]["vi"] == "Chào bạn, hôm nay thế nào?"
    assert res[1]["id"] == 2
    assert res[1]["vi"] == "Tôi cảm thấy rất tuyệt."


def test_extract_json_translations_raw_object():
    sample = '{"translations": [{"id": 5, "vi": "Nhanh lên nào!"}]}'
    res = extract_json_translations(sample)
    assert len(res) == 1
    assert res[0]["id"] == 5
    assert res[0]["vi"] == "Nhanh lên nào!"


def test_extract_json_translations_array():
    sample = '[{"id": 10, "vi": "Đoạn cuối cùng."}]'
    res = extract_json_translations(sample)
    assert len(res) == 1
    assert res[0]["id"] == 10
    assert res[0]["vi"] == "Đoạn cuối cùng."


def test_is_cdp_ready_offline_port():
    # Unopened port 65432 should safely return False without raising
    assert is_cdp_ready(65432) is False

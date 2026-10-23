"""Unit tests for Manual AI translation provider: JSON parsing, numbered lines, and sequential fallback."""
import json
import pytest

from dubstudio.config import AppConfig
from dubstudio.llm.gemini import GeminiTranslator
from dubstudio.stages.translate import parse_manual_translation_text


def test_manual_provider_initialization(tmp_path):
    """Verify manual translation provider initializes properly without requiring API keys."""
    cfg = AppConfig.load()
    cfg.translation.provider = "manual"

    translator = GeminiTranslator(cfg=cfg, cache_dir=tmp_path / "cache")
    assert translator.provider == "manual"


def test_parse_manual_translation_json_block():
    """Verify parsing when user pastes markdown JSON block from ChatGPT/Claude."""
    items = [
        {"id": 1, "zh": "你好世界", "vi_text": "", "tts_text": ""},
        {"id": 2, "zh": "今天天气很好", "vi_text": "", "tts_text": ""},
    ]

    raw_response = """
    Dưới đây là bản dịch của bạn:
    ```json
    [
        {"id": 1, "vi": "Xin chào thế giới"},
        {"id": 2, "vi": "Hôm nay thời tiết rất đẹp"}
    ]
    ```
    Chúc bạn một ngày tốt lành!
    """

    res = parse_manual_translation_text(raw_response, items)
    assert res[0]["vi_text"] == "Xin chào thế giới"
    assert res[1]["vi_text"] == "Hôm nay thời tiết rất đẹp"
    assert res[0]["tts_text"] != ""
    assert res[1]["tts_text"] != ""


def test_parse_manual_translation_numbered_brackets():
    """Verify parsing when user pastes [1] Text, [2] Text format."""
    items = [
        {"id": 1, "zh": "第一句话", "vi_text": ""},
        {"id": 2, "zh": "第二句话", "vi_text": ""},
    ]

    raw_response = """
    [1] Đây là câu thoại đầu tiên.
    [2] Đây là câu thoại thứ hai.
    """

    res = parse_manual_translation_text(raw_response, items)
    assert res[0]["vi_text"] == "Đây là câu thoại đầu tiên."
    assert res[1]["vi_text"] == "Đây là câu thoại thứ hai."


def test_parse_manual_translation_numbered_dots():
    """Verify parsing when user pastes 1. Text, 2. Text format."""
    items = [
        {"id": 1, "zh": "测试一", "vi_text": ""},
        {"id": 2, "zh": "测试二", "vi_text": ""},
    ]

    raw_response = """
    1. Thử nghiệm một
    2. Thử nghiệm hai
    """

    res = parse_manual_translation_text(raw_response, items)
    assert res[0]["vi_text"] == "Thử nghiệm một"
    assert res[1]["vi_text"] == "Thử nghiệm hai"


def test_parse_manual_translation_sequential_lines():
    """Verify fallback to line-by-line sequential matching when AI drops numbering."""
    items = [
        {"id": 1, "zh": "第一行", "vi_text": ""},
        {"id": 2, "zh": "第二行", "vi_text": ""},
    ]

    raw_response = """
    Dòng dịch đầu tiên
    Dòng dịch thứ hai
    """

    res = parse_manual_translation_text(raw_response, items)
    assert res[0]["vi_text"] == "Dòng dịch đầu tiên"
    assert res[1]["vi_text"] == "Dòng dịch thứ hai"

"""Tests for Chinese subtitle splitting and SSE stream completion."""
import pytest
from dubstudio.subtitles.sentence_align import split_chinese_correspondingly, split_multi_sentence_segments


def test_split_chinese_correspondingly_terminal():
    zh = "500次折完了。 我们来看看结果吧。"
    durs = [1.5, 2.0]
    parts = split_chinese_correspondingly(zh, durs)
    assert len(parts) == 2
    assert parts[0] == "500次折完了。"
    assert parts[1] == "我们来看看结果吧。"


def test_split_chinese_correspondingly_clause():
    zh = "既然是折叠屏幕问题，逃不过折这个问题，这是他全新从未被折过的iphone do。那么的问题就是0次折叠。"
    durs = [2.261, 3.749]
    parts = split_chinese_correspondingly(zh, durs)
    assert len(parts) == 2
    # Should split near the 37% mark at the comma
    assert "既然是折叠屏幕问题" in parts[0]
    assert "这是他全新从未被折过的" in parts[1]
    # No part contains the entire string
    assert parts[0] != zh
    assert parts[1] != zh


def test_split_multi_sentence_segments_no_duplication():
    seg = {
        "id": 1,
        "start": 0.0,
        "end": 6.0,
        "zh": "500次折完了。 我们来看看结果吧。",
        "src_text": "500次折完了。 我们来看看结果吧。",
        "vi_text": "Gập đủ 500 lần rồi đây. Chúng ta cùng xem kết quả thế nào.",
        "tts_text": "Gập đủ 500 lần rồi đây. Chúng ta cùng xem kết quả thế nào.",
    }
    result = split_multi_sentence_segments([seg])
    assert len(result) == 2
    assert result[0]["vi_text"] == "Gập đủ 500 lần rồi đây."
    assert result[1]["vi_text"] == "Chúng ta cùng xem kết quả thế nào."
    assert result[0]["zh"] == "500次折完了。"
    assert result[1]["zh"] == "Chúng ta cùng xem kết quả thế nào." or result[1]["zh"] == "我们来看看结果吧。"
    assert result[0]["zh"] != result[1]["zh"]

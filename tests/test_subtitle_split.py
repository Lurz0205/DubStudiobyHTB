"""Unit tests for subtitle slicing, dangling conjunction cleanup, and multi-part segment splitting."""
import pytest
from dubstudio.subtitles.ass import split_subtitle_slices
from dubstudio.llm.gemini import clean_dangling_conjunctions


def test_split_subtitle_slices_short():
    text = "Đây là một câu ngắn dưới mười lăm từ."
    res = split_subtitle_slices(text, start=1.0, end=4.0)
    assert len(res) == 1
    assert res[0]["text"] == text
    assert res[0]["start"] == 1.0
    assert res[0]["end"] == 4.0


def test_split_subtitle_slices_long_user_example():
    text = (
        "Hay các bạn đã từng thấy một loại vật chất kỳ diệu nào có thể biến "
        "quả trứng gà trở nên cứng hơn cả đá tảng chưa?"
    )
    words = text.split()
    assert len(words) > 15

    res = split_subtitle_slices(text, start=2.0, end=8.0)
    assert len(res) >= 2

    # Check that each slice has <= 16 words (around 10-15 words)
    for sl in res:
        w_count = len(sl["text"].split())
        assert 6 <= w_count <= 16

    # Check timing continuity
    assert res[0]["start"] == 2.0
    assert res[-1]["end"] == 8.0
    for i in range(len(res) - 1):
        assert abs(res[i]["end"] - res[i + 1]["start"]) < 0.001

    # Check that reconstructed text contains all words
    reconstructed = " ".join(sl["text"] for sl in res)
    assert reconstructed.split() == words


def test_split_subtitle_slices_respects_punctuation():
    text = (
        "Từ giọt nước mắt Prince Rupert có thể biến viên đạn thành bột, "
        "nhưng lại cực kỳ dễ vỡ khi chạm vào phần đuôi mảnh mai."
    )
    res = split_subtitle_slices(text, start=0.0, end=6.0)
    assert len(res) == 2
    assert res[0]["text"].endswith("bột,")
    assert res[1]["text"].startswith("nhưng")


def test_clean_dangling_conjunctions_user_case():
    segs = [
        {
            "id": 1,
            "vi_text": "Hay các bạn đã từng thấy vật chất nào có thể biến quả trứng trở nên cứng hơn cả đá chưa? Từ...",
            "tts_text": "Hay các bạn đã từng thấy vật chất nào có thể biến quả trứng trở nên cứng hơn cả đá chưa? Từ...",
        },
        {
            "id": 2,
            "vi_text": "thủy tinh có thể biến viên đạn thành bột,",
            "tts_text": "thủy tinh có thể biến viên đạn thành bột,",
        },
    ]

    cleaned = clean_dangling_conjunctions(segs)
    assert cleaned[0]["vi_text"] == "Hay các bạn đã từng thấy vật chất nào có thể biến quả trứng trở nên cứng hơn cả đá chưa?"
    assert cleaned[1]["vi_text"] == "Từ thủy tinh có thể biến viên đạn thành bột,"
    assert cleaned[0]["tts_text"] == "Hay các bạn đã từng thấy vật chất nào có thể biến quả trứng trở nên cứng hơn cả đá chưa?"
    assert cleaned[1]["tts_text"] == "Từ thủy tinh có thể biến viên đạn thành bột,"


def test_clean_dangling_conjunctions_comma_and():
    segs = [
        {
            "id": 10,
            "vi_text": "Một thí nghiệm đặc biệt, và...",
            "tts_text": "Một thí nghiệm đặc biệt, và...",
        },
        {
            "id": 11,
            "vi_text": "kết quả thật bất ngờ.",
            "tts_text": "kết quả thật bất ngờ.",
        },
    ]

    cleaned = clean_dangling_conjunctions(segs)
    assert cleaned[0]["vi_text"] == "Một thí nghiệm đặc biệt."
    assert cleaned[1]["vi_text"] == "Và kết quả thật bất ngờ."


def test_auto_split_long_segments():
    from dubstudio.stages.translate import auto_split_long_segments
    segs = [
        {
            "id": 1,
            "start": 0.0,
            "end": 2.5,
            "vi_text": "Xin chào các bạn đã quay trở lại.",
            "tts_text": "Xin chào các bạn đã quay trở lại.",
            "src_text": "大家好欢迎回来。",
        },
        {
            "id": 2,
            "start": 3.0,
            "end": 9.0,
            "vi_text": "Từ giọt nước mắt Prince Rupert có thể biến viên đạn thành bột, nhưng lại cực kỳ dễ vỡ khi chạm vào phần đuôi mảnh mai.",
            "tts_text": "Từ giọt nước mắt Prince Rupert có thể biến viên đạn thành bột, nhưng lại cực kỳ dễ vỡ khi chạm vào phần đuôi mảnh mai.",
            "src_text": "鲁珀特之泪能把子弹打成粉末，但只要轻轻碰触尾巴就会瞬间碎裂。",
        }
    ]
    res = auto_split_long_segments(segs)
    assert res[0]["id"] == 1
    assert res[0]["vi_text"] == segs[0]["vi_text"]
    assert len(res) == 3
    assert res[1]["id"] == 2
    assert res[2]["id"] == 3
    assert res[1]["start"] == 3.0
    assert res[2]["end"] == 9.0
    assert res[1]["end"] == res[2]["start"]
    assert len(res[1]["vi_text"]) > 0
    assert len(res[2]["vi_text"]) > 0


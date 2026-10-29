import pytest
from dubstudio.stages.asr import reconnect_dangling_asr_segments
from dubstudio.stages.translate import auto_split_long_segments


def test_reconnect_image_1_case():
    """Image 1: '当然现在它。' (0.9s) + '也在经历这个时刻...' (1.5s) must be merged into one!"""
    segs = [
        {
            "id": 22,
            "start": 92.5,
            "end": 93.4,
            "src_text": "当然现在它。",
            "speech_time": 0.9,
            "words": [{"word": "当然现在它。", "start": 92.5, "end": 93.4}],
        },
        {
            "id": 23,
            "start": 93.4,
            "end": 94.9,
            "src_text": "也在经历这个时刻，真的我看起来呀，没有一个博主在夸...",
            "speech_time": 1.5,
            "words": [{"word": "也在经历这个时刻", "start": 93.4, "end": 94.9}],
        }
    ]
    merged = reconnect_dangling_asr_segments(segs)
    assert len(merged) == 1
    assert merged[0]["id"] == 1
    assert merged[0]["start"] == 92.5
    assert merged[0]["end"] == 94.9
    assert "当然现在它也在经历这个时刻" in merged[0]["src_text"]


def test_reconnect_image_2_case():
    """Image 2: '...我们直接' + '100万次，因为team...' must be merged into one!"""
    segs = [
        {
            "id": 4,
            "start": 12.0,
            "end": 18.0,
            "src_text": "来挑战一下范登山的100万次tem折他折了1万次，我们直接",
            "speech_time": 6.0,
            "words": [],
        },
        {
            "id": 5,
            "start": 18.0,
            "end": 19.0,
            "src_text": "100万次，因为team他可能没有那么多时间来做测试，但是...",
            "speech_time": 1.0,
            "words": [],
        }
    ]
    merged = reconnect_dangling_asr_segments(segs)
    assert len(merged) == 1
    assert merged[0]["start"] == 12.0
    assert merged[0]["end"] == 19.0
    assert "我们直接100万次" in merged[0]["src_text"]


def test_reconnect_image_3_case():
    """Image 3: '...反正大' + '会看到iphone do...' must be merged into one!"""
    segs = [
        {
            "id": 19,
            "start": 74.1,
            "end": 82.5,
            "src_text": "第一方的app，他们自己的app都还没有适配好，反正大",
            "speech_time": 8.4,
            "words": [],
        },
        {
            "id": 20,
            "start": 82.5,
            "end": 87.4,
            "src_text": "会看到iphone do。各种的bug，各种的适配问题。",
            "speech_time": 4.9,
            "words": [],
        }
    ]
    merged = reconnect_dangling_asr_segments(segs, max_combined_dur=9.5)
    assert len(merged) == 2


def test_auto_split_long_segments_no_mid_sentence_cuts():
    """Sentences without natural punctuation must never be chopped mid-phrase."""
    segs = [
        {
            "id": 1,
            "start": 10.0,
            "end": 16.5,
            "vi_text": "nói chung là viền đen xung quanh dày lắm mà dạo này các bạn sẽ thấy chiếc điện thoại này gặp đủ loại lỗi",
            "src_text": "zh text",
        }
    ]
    # No punctuation inside -> stays whole sentence!
    res = auto_split_long_segments(segs)
    assert len(res) == 1
    assert res[0]["vi_text"] == segs[0]["vi_text"]


def test_sentence_gap_preserved_not_connected():
    """Ensure sentence 1 (1s-3s) and sentence 2 (5s-7s) remain distinct with 2s silence preserved."""
    from dubstudio.subtitles.sentence_align import stitch_dangling_clauses

    segs = [
        {"id": 1, "start": 1.0, "end": 3.0, "src_text": "你好世界。", "vi_text": "Xin chào thế giới."},
        {"id": 2, "start": 5.0, "end": 7.0, "src_text": "今天天气很好。", "vi_text": "Hôm nay thời tiết rất đẹp."},
    ]
    # 1. ASR reconnect must keep them separate
    reconnected = reconnect_dangling_asr_segments(segs)
    assert len(reconnected) == 2
    assert reconnected[0]["start"] == 1.0
    assert reconnected[0]["end"] == 3.0
    assert reconnected[1]["start"] == 5.0
    assert reconnected[1]["end"] == 7.0

    # 2. Sentence align must NEVER pull sentence 2 start back to 3.0s
    aligned = stitch_dangling_clauses(segs)
    assert len(aligned) == 2
    assert aligned[0]["start"] == 1.0
    assert aligned[0]["end"] == 3.0
    assert aligned[1]["start"] == 5.0  # NOT 3.0!
    assert aligned[1]["end"] == 7.0


def test_user_sentence_split_at_comma_not_phrase():
    """Ensure 'Bất kể thế nào thì tôi cũng không thẹn với lòng, thế được chưa.' with target_n=10
    splits at the comma: Line 1 = '...với lòng,', Line 2 = 'thế được chưa.' (NOT cutting before 'với lòng')."""
    from dubstudio.subtitles.cue_split import split_sentence_cues

    text = "Bất kể thế nào thì tôi cũng không thẹn với lòng, thế được chưa."
    cues = split_sentence_cues(text, 0.0, 5.0, target_n=10)
    assert len(cues) == 2
    assert cues[0]["text"] == "Bất kể thế nào thì tôi cũng không thẹn với lòng,"
    assert cues[1]["text"] == "thế được chưa."
    assert cues[0]["start"] == 0.0
    assert cues[1]["end"] == 5.0


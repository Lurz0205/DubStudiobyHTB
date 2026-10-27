import pytest
from dubstudio.config import AppConfig
from dubstudio.stages.fit import calculate_fit_decision, build_clusters, resolve_isolated_pair_shifts


@pytest.fixture
def cfg():
    c = AppConfig.load()
    c.fit.max_speedup = 1.10
    return c


def test_golden_table_fit_decisions(cfg):
    # 15 golden cases testing all edge cases and boundaries with max_speedup = 1.10
    test_cases = [
        # (tts_dur, dur, silence_after, expected_method, expected_rate, expected_overflow)
        (1.00, 1.00, 0.0, "none", 1.0, False),         # exactly match
        (1.02, 1.00, 0.0, "none", 1.0, False),         # 1.02 within [0.95, 1.05]
        (0.96, 1.00, 0.0, "none", 1.0, False),         # 0.96 within [0.95, 1.05]
        (1.05, 1.00, 0.0, "none", 1.0, False),         # upper bound neutral
        (0.95, 1.00, 0.0, "none", 1.0, False),         # lower bound neutral

        (1.08, 1.00, 0.0, "speedup", 1.08, False),     # minor speedup <= 1.10
        (1.10, 1.00, 0.0, "speedup", 1.10, False),     # exact max speedup 1.10
        (1.15, 1.00, 0.0, "speedup", 1.10, True),      # over 1.10, zero silence -> overflow

        (0.92, 1.00, 0.0, "slowdown", 0.92, False),    # moderate slowdown
        (0.90, 1.00, 0.0, "slowdown", 0.90, False),    # exact min slowdown

        (1.30, 1.00, 0.5, "speedup", 1.10, False),     # over max speedup, fits in silence_after (0.5s)
        (1.30, 1.00, 0.05, "speedup", 1.10, True),     # over max speedup, silence_after too short -> overflow
        (2.00, 1.00, 0.0, "speedup", 1.10, True),      # huge overflow, zero silence -> overflow

        (0.70, 1.00, 0.0, "slowdown", 0.90, False),    # too short, clamped to min 0.9x
        (0.50, 1.00, 0.5, "slowdown", 0.90, False),    # very short line, clamped to 0.9x
    ]

    assert len(test_cases) == 15

    for tts_dur, dur, silence_after, exp_method, exp_rate, exp_overflow in test_cases:
        method, rate, flags = calculate_fit_decision(tts_dur, dur, cfg, silence_after=silence_after)
        assert method == exp_method, f"Failed method for tts_dur={tts_dur}, dur={dur}"
        assert abs(rate - exp_rate) < 0.01, f"Failed rate {rate} vs {exp_rate} for tts_dur={tts_dur}, dur={dur}"
        has_overflow = "overflow" in flags
        assert has_overflow == exp_overflow, f"Failed overflow flag for tts_dur={tts_dur}, dur={dur}, silence={silence_after}"


def test_build_clusters():
    # Test grouping colliding indices into clusters with window 2
    segments = [{"id": i} for i in range(10)]

    # Case 1: Single collision at line 3 -> cluster [1, 2, 3, 4, 5]
    c1 = build_clusters([3], segments, window=2)
    assert c1 == [[1, 2, 3, 4, 5]]

    # Case 2: Two nearby collisions at lines 3 and 5 -> merged into [1, 2, 3, 4, 5, 6, 7]
    c2 = build_clusters([3, 5], segments, window=2)
    assert c2 == [[1, 2, 3, 4, 5, 6, 7]]

    # Case 3: Two distant collisions at lines 1 and 8 -> separate clusters [0, 1, 2, 3] and [6, 7, 8, 9]
    c3 = build_clusters([1, 8], segments, window=2)
    assert c3 == [[0, 1, 2, 3], [6, 7, 8, 9]]


def test_fit_minor_overlap_balanced_within_1_1x():
    # Segment 0 starts at 0.0, next segment starts at 3.0 (available time = 3.0s, max audio = 2.95s)
    # TTS dur is 3.15s -> raw overlap = 0.20s
    # Required rate = 3.15 / 2.95 = 1.068x <= 1.10x
    # Should be balanced via minor speedup without needing rewrite!
    st = 0.0
    next_st = 3.0
    available_dur = next_st - st
    max_audio_dur = available_dur - 0.05
    tts_dur = 3.15

    raw_overlap = tts_dur - max_audio_dur
    assert raw_overlap > 0
    req_rate = tts_dur / max_audio_dur
    assert req_rate <= 1.10
    rate = min(1.10, max(1.0, round(req_rate, 2)))
    assert 1.0 < rate <= 1.10
    effective_dur = tts_dur / rate
    assert round(st + effective_dur, 2) <= next_st


def test_resolve_isolated_pair_shifts():
    # Segment 0: 0.0 -> 2.0 (ends at 2.0)
    # Segment 1: 3.0 -> 5.0 (tts_dur = 2.64s -> at 1.1x = 2.40s, reaches 5.40s)
    # Segment 2: 5.0 -> 7.0 (tts_dur = 2.0s -> at 1.1x = 1.82s, reaches 6.82s)
    # Segment 3: 8.5 -> 10.0 (starts at 8.5)
    #
    # Segments 1 and 2 collide (5.40s > 5.00s, overlap = 0.40s > 0.25s)
    # Boundary 0 (0 to 1): 2.0 to 3.0 (gap = 1.0s, no collision)
    # Boundary 2 (2 to 3): 6.82 to 8.5 (gap = 1.68s, no collision)
    # Exactly isolated pair (1 and 2)!
    segments = [
        {"id": 0, "start": 0.0, "end": 2.0, "tts_dur": 2.0},
        {"id": 1, "start": 3.0, "end": 5.0, "tts_dur": 2.64},
        {"id": 2, "start": 5.0, "end": 7.0, "tts_dur": 2.0},
        {"id": 3, "start": 8.5, "end": 10.0, "tts_dur": 1.5},
    ]

    shifted = resolve_isolated_pair_shifts(segments, video_dur=15.0, max_shift=0.25, allowable_overlap=0.25)
    assert shifted == 1
    # Segment 1 should shift back into gap_before
    assert segments[1]["start"] < 3.0
    # Overlap is relieved within allowable 0.25s
    st1 = segments[1]["start"]
    end1 = st1 + round(2.64 / 1.10, 3)
    st2 = segments[2]["start"]
    assert (end1 - st2) <= 0.25


def test_extract_json_translations_rewritten_segments():
    from dubstudio.llm.cdp_gemini import extract_json_translations

    raw = """Sau đây là các câu đã rút gọn:
```json
{
  "rewritten_segments": [
    {
      "id": 1,
      "vi_text": "Nói đến màn hình gập không thể bỏ qua nếp gập.",
      "tts_text": "Nói đến màn hình gập không thể bỏ qua nếp gập."
    }
  ]
}
```
Hi vọng bản rút gọn này vừa vặn thời lượng.
"""
    items = extract_json_translations(raw)
    assert len(items) == 1
    assert items[0]["id"] == 1
    assert "Nói đến màn hình gập" in items[0]["vi_text"]


def test_fit_rewriter_cluster_normalization(cfg):
    from dubstudio.llm.fit_rewrite import FitRewriter
    from unittest.mock import patch

    rewriter = FitRewriter(cfg)
    mock_items = [
        {"id": "2", "vi": "Câu dịch ngắn gọn", "tts": "Câu dịch ngắn gọn"},
    ]

    with patch.object(rewriter, "_can_use_cdp", return_value=True):
        with patch("dubstudio.llm.cdp_gemini.translate_via_cdp", return_value=mock_items):
            res = rewriter.rewrite_cluster(
                [{"id": 2, "is_colliding": True, "src_text": "test", "vi_text": "Dài", "tts_text": "Dài"}],
                analysis_data={},
                pass_idx=2,
            )
            assert len(res) == 1
            assert res[0]["id"] == 2
            assert res[0]["vi_text"] == "Câu dịch ngắn gọn"
            assert res[0]["tts_text"] == "Câu dịch ngắn gọn"


def test_fit_rewriter_rewrite_units_two_way(cfg):
    from dubstudio.llm.fit_rewrite import FitRewriter
    from unittest.mock import patch

    rewriter = FitRewriter(cfg)
    mock_items = {
        "rewritten_segments": [
            {"id": 1, "vi_text": "Câu rút ngắn gọn", "tts_text": "Câu rút ngắn gọn"},
            {"id": 2, "vi_text": "Câu được diễn đạt đầy đủ và thoáng ý hơn", "tts_text": "Câu được diễn đạt đầy đủ và thoáng ý hơn"},
        ]
    }

    mismatched = [
        {"id": 1, "direction": "shorter", "target_chars": 20, "zh": "短", "vi_text": "Câu này quá dài đè câu sau", "tts_dur": 3.0},
        {"id": 2, "direction": "longer", "target_chars": 50, "zh": "长", "vi_text": "Ngắn cộc lốc", "tts_dur": 1.0},
    ]

    with patch.object(rewriter, "_can_use_cdp", return_value=True):
        with patch("dubstudio.llm.cdp_gemini.translate_via_cdp", return_value=mock_items):
            res = rewriter.rewrite_units(mismatched, analysis_data={}, pass_idx=1)
            assert len(res) == 2
            assert res[0]["id"] == 1
            assert res[0]["vi_text"] == "Câu rút ngắn gọn"
            assert res[1]["id"] == 2
            assert "thoáng ý" in res[1]["vi_text"]


def test_trim_tts_silence(tmp_path):
    import numpy as np
    import soundfile as sf
    from dubstudio.stages.fit import trim_tts_silence

    sr = 24000
    # 200ms silence (0.0), 400ms tone (0.5 amplitude), 200ms silence (0.0)
    leading_silence = np.zeros(int(0.20 * sr), dtype=np.float32)
    tone = np.full(int(0.40 * sr), 0.5, dtype=np.float32)
    trailing_silence = np.zeros(int(0.20 * sr), dtype=np.float32)
    signal = np.concatenate([leading_silence, tone, trailing_silence])

    wav_p = tmp_path / "test_silence.wav"
    sf.write(str(wav_p), signal, sr)
    orig_dur = round(len(signal) / sr, 3)
    assert orig_dur == 0.80

    trimmed_dur = trim_tts_silence(wav_p, threshold_db=-45.0, pad_ms=25.0)
    # With 25ms pad on each side, trimmed should be ~ 400ms + 50ms = 450ms (0.45s)
    assert 0.43 <= trimmed_dur <= 0.48
    assert trimmed_dur < orig_dur

    # Read back to verify file was overwritten
    data, r_sr = sf.read(str(wav_p))
    assert len(data) < len(signal)


def test_resolve_isolated_pair_shifts_syncs_end_and_gap_before():
    from dubstudio.stages.fit import resolve_isolated_pair_shifts, MAX_SILENCE_SHIFT
    assert MAX_SILENCE_SHIFT == 0.25

    segments = [
        {"id": 0, "start": 0.0, "end": 2.0, "tts_dur": 2.0},
        {"id": 1, "start": 3.0, "end": 5.0, "tts_dur": 2.60}, # 2.60 / 1.1 = 2.36s -> overlap 0.36s > 0.25s
        {"id": 2, "start": 5.0, "end": 7.0, "tts_dur": 2.0},
        {"id": 3, "start": 9.0, "end": 10.0, "tts_dur": 1.0},
    ]

    shifted = resolve_isolated_pair_shifts(segments, video_dur=15.0)
    assert shifted == 1
    # Segment 1 start shifted back, end shifted back by same delta
    assert segments[1]["start"] < 3.0
    delta_start = 3.0 - segments[1]["start"]
    delta_end = 5.0 - segments[1]["end"]
    assert abs(delta_start - delta_end) < 0.005


def test_last_segment_boundary_fit():
    # Verify the last segment is bounded strictly to video_dur and does not overflow
    from dubstudio.stages.fit import ALLOWABLE_OVERLAP, MAX_SILENCE_SHIFT
    assert ALLOWABLE_OVERLAP == 0.25
    assert MAX_SILENCE_SHIFT == 0.25


def test_fit_rewrite_payload_strips_newlines(cfg, tmp_path):
    from dubstudio.llm.fit_rewrite import FitRewriter
    import json
    import re
    import dubstudio.llm.cdp_gemini as cdp_mod

    rewriter = FitRewriter(cfg, cache_dir=tmp_path)
    multiline_units = [
        {
            "id": 1,
            "zh": "这是他全新从未被折过的iphone do。\n那么的问题就是0次折叠。",
            "vi_text": "Đây là một chiếc\niPhone hoàn toàn mới,\nchưa từng qua một lần gập nào,\nnên số lần gập hiện tại là 0.",
            "tts_text": "Đây là một chiếc\niPhone hoàn toàn mới,\nchưa từng qua một lần gập nào.",
            "measured_dur": 4.72,
            "max_audio_dur": 3.84,
            "direction": "shorter",
            "target_chars": 75,
            "prev_vi": "Đã bàn về màn hình gập\nthì chắc chắn phải thử.",
            "next_vi": "Liệu nếp gấp\ngiữa hai chiếc có khác?",
        }
    ]

    captured_prompts = []
    orig_cdp = cdp_mod.translate_via_cdp

    def mock_translate(prompt, port=9222):
        captured_prompts.append(prompt)
        return [{
            "id": 1,
            "vi_text": "Đây là chiếc iPhone mới tinh\nchưa gập lần nào.",
            "tts_text": "Đây là chiếc iPhone mới tinh\nchưa gập lần nào.",
        }]

    try:
        cdp_mod.translate_via_cdp = mock_translate
        rewriter.provider = "gemini_web"
        rewriter._can_use_cdp = lambda: True

        res = rewriter.rewrite_units(multiline_units, {}, pass_idx=1)
        assert len(captured_prompts) == 1
        prompt = captured_prompts[0]

        # Verify that within the JSON payload objects, vi_text, tts_text, zh, and context do NOT have raw \n
        match = re.search(r'\[\s*\{\s*"id":\s*1.*?\n\s*\}\s*\]', prompt, re.DOTALL)
        assert match is not None
        payload_data = json.loads(match.group(0))
        item = payload_data[0]
        assert "\n" not in item["vi_text"]
        assert "\n" not in item["tts_text"]
        assert "\n" not in item["zh"]
        assert "\n" not in item["context"]
        assert "  " not in item["vi_text"]

        # Verify returned normalized result also strips any LLM \n
        assert len(res) == 1
        assert "\n" not in res[0]["vi_text"]
        assert "\n" not in res[0]["tts_text"]
        assert res[0]["vi_text"] == "Đây là chiếc iPhone mới tinh chưa gập lần nào."
        assert "tts_word_count" in res[0]
    finally:
        cdp_mod.translate_via_cdp = orig_cdp


def test_count_spoken_words_and_word_budgeting(cfg, tmp_path):
    from dubstudio.stages.fit import count_spoken_words
    from dubstudio.llm.fit_rewrite import FitRewriter
    import dubstudio.llm.cdp_gemini as cdp_mod

    s1 = "Đây là một chiếc điện thoại gập hoàn toàn mới"
    assert count_spoken_words(s1) == 10
    assert count_spoken_words("   chưa   qua sử dụng   ") == 4
    assert count_spoken_words("") == 0

    rewriter = FitRewriter(cfg, cache_dir=tmp_path)
    test_units = [
        {
            "id": 1,
            "zh": "这是全新的手机",
            "vi_text": "Đây là một chiếc điện thoại gập hoàn toàn mới",
            "tts_text": "Đây là một chiếc điện thoại gập hoàn toàn mới",
            "current_words": 10,
            "target_words": 8,
            "min_words": 7,
            "max_words": 9,
            "words_to_remove": 2,
            "edit_instruction": "CHỈ CẦN LƯỢC BỎ ĐÚNG 2 TỪ ĐỆM/TỪ THỪA. Giữ nguyên 85-90% câu gốc, TUYỆT ĐỐI KHÔNG tóm tắt hay viết lại toàn bộ câu!",
            "measured_dur": 3.0,
            "max_audio_dur": 2.4,
            "direction": "shorter",
            "target_chars": 40,
            "min_chars": 35,
            "max_chars": 45,
            "prev_vi": "",
            "next_vi": "",
        }
    ]

    captured = []
    def mock_cdp(prompt, port=9222):
        captured.append(prompt)
        return [{
            "id": 1,
            "vi_text": "Đây là chiếc điện thoại gập mới tinh",
            "tts_text": "Đây là chiếc điện thoại gập mới tinh",
            "tts_word_count": 8,
        }]

    orig_cdp = cdp_mod.translate_via_cdp
    try:
        cdp_mod.translate_via_cdp = mock_cdp
        rewriter.provider = "gemini_web"
        rewriter._can_use_cdp = lambda: True

        res = rewriter.rewrite_units(test_units, {}, pass_idx=1)
        assert len(captured) == 1
        prompt = captured[0]
        assert "current_words" in prompt
        assert "target_words" in prompt
        assert "edit_instruction" in prompt
        assert "CHỈ CẦN LƯỢC BỎ ĐÚNG 2 TỪ ĐỆM" in prompt

        assert len(res) == 1
        assert res[0]["tts_word_count"] == 8
    finally:
        cdp_mod.translate_via_cdp = orig_cdp




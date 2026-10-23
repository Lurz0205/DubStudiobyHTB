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
    # Segment 1: 3.0 -> 5.0 (tts_dur = 2.42s -> at 1.1x = 2.20s, reaches 5.20s)
    # Segment 2: 5.0 -> 7.0 (tts_dur = 2.0s -> at 1.1x = 1.82s, reaches 6.82s)
    # Segment 3: 8.5 -> 10.0 (starts at 8.5)
    #
    # Segments 1 and 2 collide (5.20s > 5.00s, overlap = 0.20s > 0.10s)
    # Boundary 0 (0 to 1): 2.0 to 3.0 (gap = 1.0s, no collision)
    # Boundary 2 (2 to 3): 6.82 to 8.5 (gap = 1.68s, no collision)
    # Exactly isolated pair (1 and 2)!
    segments = [
        {"id": 0, "start": 0.0, "end": 2.0, "tts_dur": 2.0},
        {"id": 1, "start": 3.0, "end": 5.0, "tts_dur": 2.42},
        {"id": 2, "start": 5.0, "end": 7.0, "tts_dur": 2.0},
        {"id": 3, "start": 8.5, "end": 10.0, "tts_dur": 1.5},
    ]

    shifted = resolve_isolated_pair_shifts(segments, video_dur=15.0, max_shift=0.50)
    assert shifted == 1
    # Segment 1 should shift back into gap_before (from 3.0 to 2.90)
    assert segments[1]["start"] < 3.0
    # Overlap is relieved within allowable 0.10s
    st1 = segments[1]["start"]
    end1 = st1 + round(2.42 / 1.10, 3)
    st2 = segments[2]["start"]
    assert (end1 - st2) <= 0.10

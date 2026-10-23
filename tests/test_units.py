import pytest
from dubstudio.stages.units import build_dubbing_units, extract_complete_sentences
from dubstudio.stages.translate import check_style_lint, run_style_lint_and_repair
from dubstudio.llm.gemini import build_prompt


def test_build_dubbing_units():
    # 3 adjacent segments with small gaps
    segments = [
        {"id": 1, "start": 0.0, "end": 1.0, "src_text": "你好", "speech_time": 0.9, "speaker": None},
        {"id": 2, "start": 1.2, "end": 2.0, "src_text": "今天", "speech_time": 0.7, "speaker": None},  # gap = 0.2s <= 0.6s
        {"id": 3, "start": 2.4, "end": 3.0, "src_text": "天气很好", "speech_time": 0.5, "speaker": None}, # gap = 0.4s <= 0.6s
        {"id": 4, "start": 5.0, "end": 6.0, "src_text": "再见", "speech_time": 0.8, "speaker": None},  # gap = 2.0s > 0.8s (must NOT combine)
    ]

    units = build_dubbing_units(segments, default_cps=17.0)

    # Unit 1 should combine segments 1, 2, 3 into a complete sentence
    assert len(units) == 2
    u1 = units[0]
    assert u1["id"] == 1
    assert u1["parts"] == [1, 2, 3]
    assert u1["zh"] == "你好今天天气很好"
    assert u1["start"] == 0.0
    assert u1["end"] == 3.0
    assert u1["dur"] > 0
    assert u1["min_chars"] < u1["target_chars"] < u1["max_chars"]

    # Unit 2 should be segment 4 alone
    u2 = units[1]
    assert u2["id"] == 2
    assert u2["parts"] == [4]
    assert u2["zh"] == "再见"
    assert u2["start"] == 5.0


def test_extract_complete_sentences_rules():
    # Comma does NOT break sentence, even if gap is 0.9s (gap <= 1.5s)
    segments = [
        {"id": 1, "start": 0.0, "end": 2.0, "src_text": "很多人以为美国会停手，", "speaker": "spk1"},
        {"id": 2, "start": 2.9, "end": 5.0, "src_text": "但当波斯湾的邮轮撤离后。", "speaker": "spk1"},
        {"id": 3, "start": 5.2, "end": 7.0, "src_text": "他们立刻空袭。", "speaker": "spk2"}, # speaker change
    ]
    sents = extract_complete_sentences(segments)
    assert len(sents) == 2
    # Segments 1 and 2 merged across comma
    assert sents[0]["parts"] == [1, 2]
    assert sents[0]["zh"] == "很多人以为美国会停手，但当波斯湾的邮轮撤离后。"
    # Segment 3 is separated due to speaker change
    assert sents[1]["parts"] == [3]
    assert sents[1]["zh"] == "他们立刻空袭。"


def test_long_sentence_produces_clauses():
    # Single sentence duration > 15s (not split by ASR)
    parts = [
        {"id": 1, "start": 0.0, "end": 16.0, "src_text": "这是一个持续时间超过十五秒的超长句子，中间有很多关于波斯湾的描述，最后是整个行动的总结。", "words": None},
    ]
    units = build_dubbing_units(parts, default_cps=17.0)
    assert len(units) == 1
    u = units[0]
    assert u["dur"] >= 15.0
    assert u["clauses"] is not None
    assert len(u["clauses"]) >= 2
    for c in u["clauses"]:
        assert "start" in c and "end" in c and "zh" in c


def test_natural_speech_does_not_collapse_into_one_block():
    # Sequence of 3-7s segments without terminal punctuation should NOT collapse into 1 block
    segments = [
        {"id": 1, "start": 0.0, "end": 5.0, "src_text": "曾经横扫中东的美军如今竟落到了枪里没子弹的尴尬地步", "speaker": None},
        {"id": 2, "start": 5.2, "end": 10.0, "src_text": "上周五伊朗对约旦境内美军基地发起袭击", "speaker": None},
        {"id": 3, "start": 10.3, "end": 15.5, "src_text": "反手就把美国的假停火撕了个稀碎", "speaker": None},
    ]
    units = build_dubbing_units(segments, default_cps=17.0)
    # Each segment is 5s, so they should remain distinct units
    assert len(units) == 3


def test_proportional_cue_scaling():
    # Verify that when segment timeline stretches, cues maintain identical proportional ratios
    orig_start = 0.0
    orig_dur = 10.0
    cues = [
        {"start": 0.0, "end": 4.0, "text": "Phần một"},
        {"start": 4.0, "end": 10.0, "text": "Phần hai"},
    ]
    # New TTS duration is 12.0s starting at 1.0s
    new_start = 1.0
    new_dur = 12.0
    ratio = new_dur / orig_dur

    scaled_cues = []
    for c in cues:
        rel_st = c["start"] - orig_start
        rel_en = c["end"] - orig_start
        scaled_cues.append({
            "start": round(new_start + rel_st * ratio, 3),
            "end": round(new_start + rel_en * ratio, 3),
            "text": c["text"],
        })

    assert scaled_cues[0]["start"] == 1.0
    assert scaled_cues[0]["end"] == round(1.0 + 4.0 * 1.2, 3) # 5.8s
    assert scaled_cues[1]["start"] == round(1.0 + 4.0 * 1.2, 3) # 5.8s
    assert scaled_cues[1]["end"] == 13.0 # 1.0 + 12.0
    # Ratio of first cue duration (4.8 / 12.0 = 0.4) equals original ratio (4.0 / 10.0 = 0.4)
    assert abs((scaled_cues[0]["end"] - scaled_cues[0]["start"]) / new_dur - 0.4) < 1e-5



def test_build_prompt_retry_carries_all_5_sections():
    # Verify build_prompt with task_type='retry' carries all 5 required parts
    context = {
        "genre": "Quân sự & Thời sự",
        "summary": "Phân tích chiến sự tại Trung Đông",
        "tone": "Trang trọng, dồn dập",
        "characters": [{"name": "Người dẫn", "role": "Dẫn chuyện"}],
        "glossary": [{"zh": "波斯湾", "vi": "vịnh Ba Tư"}, {"zh": "伊朗", "vi": "Iran"}],
    }

    all_units = [
        {"id": 1, "zh": "第一句话", "vi_text": "Câu số một."},
        {"id": 2, "zh": "第二句话", "vi_text": "Câu số hai."},
        {"id": 3, "zh": "第三句话", "vi_text": "Câu số ba."},
        {"id": 4, "zh": "第四句话", "vi_text": "Câu số bốn."},
        {"id": 5, "zh": "第五句话", "vi_text": "Câu số năm."},
        {"id": 6, "zh": "第六句话（cần dịch bù）", "vi_text": ""},
        {"id": 7, "zh": "第七句话（kế tiếp 1）", "vi_text": ""},
        {"id": 8, "zh": "第八句话（kế tiếp 2）", "vi_text": ""},
    ]

    target_retry = [all_units[5]] # unit 6

    system_instruction, content_str = build_prompt(
        batch_units=target_retry,
        all_units=all_units,
        context=context,
        style="Trang trọng",
        story_so_far="Mỹ đang điều động tàu sân bay tới khu vực.",
        task_type="retry",
    )

    # 1. analysis present
    assert "Quân sự & Thời sự" in system_instruction
    assert "Người dẫn" in system_instruction

    # 2. glossary removed as explicitly requested
    assert "波斯湾 -> vịnh Ba Tư" not in system_instruction
    assert "Bảng thuật ngữ" not in system_instruction

    # 3. story_so_far present
    assert "Mỹ đang điều động tàu sân bay" in system_instruction

    # 4. prev_lines present (up to 5)
    assert "#1: Câu số một." in system_instruction
    assert "#2: Câu số hai." in system_instruction
    assert "#3: Câu số ba." in system_instruction
    assert "#4: Câu số bốn." in system_instruction
    assert "#5: Câu số năm." in system_instruction

    # 5. next_lines present (2 units strictly for context)
    assert "next_lines" in system_instruction
    assert "#7 (ZH): 第七句话（kế tiếp 1）" in system_instruction
    assert "#8 (ZH): 第八句话（kế tiếp 2）" in system_instruction

    # Check content payload
    assert "第六句话（cần dịch bù）" in content_str


def test_style_lint_checks():
    # Starts with ellipsis
    assert check_style_lint("...nhưng khi mọi người rời đi") == "starts_with_ellipsis"
    assert check_style_lint("…nhưng khi mọi người rời đi") == "starts_with_ellipsis"

    # Ends with ellipsis
    assert check_style_lint("Họ tưởng Mỹ sẽ dừng tay...") == "ends_with_ellipsis"
    assert check_style_lint("Họ tưởng Mỹ sẽ dừng tay…") == "ends_with_ellipsis"

    # Ends with comma
    assert check_style_lint("Nhiều người tưởng Mỹ sẽ dừng tay,") == "ends_with_comma"

    # Ends with conjunction
    assert check_style_lint("Họ không kích liên tục và") == "ends_with_conjunction"
    assert check_style_lint("Họ không kích liên tục nhưng.") == "ends_with_conjunction"
    assert check_style_lint("Các tàu chiến di chuyển để") == "ends_with_conjunction"
    assert check_style_lint("Tình hình rất căng thẳng vì...") == "ends_with_ellipsis"

    # Valid complete sentence
    assert check_style_lint("Nhiều người tưởng Mỹ sẽ dừng tay, nhưng họ lập tức không kích.") is None


def test_style_lint_repair_merges_in_one_request():
    class DummyTranslator:
        def __init__(self):
            self.calls = []

        def _translate_batch(self, batch_items, system_instruction, stage_name, current_idx, total_items, style=None, content_str=None):
            self.calls.append({
                "items": batch_items,
                "inst": system_instruction,
                "content": content_str,
            })
            # Return polished translation for the merged item
            return [{"id": batch_items[0]["id"], "vi": "Nhiều người tưởng Mỹ dừng tay, nhưng họ lập tức không kích."}]

        def _merge_translations(self, segments, res):
            for r in res:
                for s in segments:
                    if s["id"] == r["id"]:
                        s["vi_text"] = r["vi"]
                        s["tts_text"] = r["vi"]

    units = [
        {"id": 1, "start": 0.0, "end": 2.0, "zh": "很多人以为美国会停手，", "vi_text": "Nhiều người tưởng Mỹ sẽ dừng tay,"},
        {"id": 2, "start": 2.2, "end": 5.0, "zh": "但他们立刻空袭。", "vi_text": "nhưng họ lập tức không kích."},
    ]

    dummy = DummyTranslator()
    repaired = run_style_lint_and_repair(units, translator=dummy)

    # Must be merged into 1 unit
    assert len(repaired) == 1
    # Must have made exactly ONE translation request
    assert len(dummy.calls) == 1
    call = dummy.calls[0]
    assert len(call["items"]) == 1
    assert "DỊCH LẠI để liền mạch câu thoại" in call["inst"]
    assert repaired[0]["vi_text"] == "Nhiều người tưởng Mỹ dừng tay, nhưng họ lập tức không kích."


def test_check_style_lint_dangling_comparatives():
    """Kiểm tra check_style_lint phát hiện các câu kết thúc lửng bằng từ so sánh/bắc cầu."""
    assert check_style_lint("quy đổi ra công suất đạt tới 163 kW, tương đương.") == "ends_with_dangling_phrase"
    assert check_style_lint("sức mạnh khủng khiếp, so với.") == "ends_with_dangling_phrase"
    assert check_style_lint("hệ thống phòng thủ bao gồm.") == "ends_with_dangling_phrase"
    assert check_style_lint("ảnh hưởng nghiêm trọng, dẫn đến.") == "ends_with_dangling_phrase"
    assert check_style_lint("Tốc độ bay tối đa của nó tới 1000 km trên giờ.") is None


def test_sentence_align_stitch_dangling_comparator():
    """Kiểm tra stitch_dangling_clauses tự động cứu cụm 'tương đương.' + 'Với công suất...'."""
    from dubstudio.subtitles.sentence_align import stitch_dangling_clauses

    segments = [
        {"id": 1, "start": 0.0, "end": 3.0, "vi_text": "quy đổi ra công suất đạt tới 163 kW, tương đương."},
        {"id": 2, "start": 3.1, "end": 6.5, "vi_text": "Với công suất của 26 chiếc máy giặt hoạt động cùng lúc,"},
    ]
    stitched = stitch_dangling_clauses(segments)
    assert stitched[0]["vi_text"] == "quy đổi ra công suất đạt tới 163 kW."
    assert stitched[1]["vi_text"] == "Tương đương với công suất của 26 chiếc máy giặt hoạt động cùng lúc,"


def test_extract_complete_sentences_zh_connective():
    """Kiểm tra ASR segment kết thúc bằng '相当于' không bị chặt đôi câu."""
    segments = [
        {"id": 1, "start": 0.0, "end": 2.5, "src_text": "折合功率达到163千瓦，相当于", "speaker": "spk1"},
        {"id": 2, "start": 3.0, "end": 6.0, "src_text": "26台洗衣机同时工作的功率。", "speaker": "spk1"},
    ]
    sents = extract_complete_sentences(segments)
    assert len(sents) == 1
    assert "相当于26台洗衣机" in sents[0]["zh"]

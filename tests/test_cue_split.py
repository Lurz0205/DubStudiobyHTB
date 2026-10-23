"""Tests for Dynamic Programming word-count subtitle cue splitting."""
import pytest
from dubstudio.subtitles.cue_split import (
    split_sentence_cues,
    auto_split_unit_cues,
    auto_split_all_units,
    find_forbidden_cuts,
    clean_word,
    FORBIDDEN_END_WORDS,
)


def test_persian_gulf_mandatory():
    """
    Test bắt buộc (câu thật):
    'Nhiều người tưởng Mỹ sẽ dừng tay, nhưng khi các tàu du lịch ở vịnh Ba Tư rút hết, họ lập tức không kích Iran liên tục 13 ngày.'
    với N=5 phải thỏa:
    - không dòng nào cắt 'vịnh Ba Tư', 'Iran', '13 ngày'
    - không dòng nào kết thúc bằng từ cấm
    - mọi dòng có 3–7 từ
    - điểm cắt rơi vào dấu phẩy hoặc trước 'nhưng'/'khi' khi có thể.
    """
    text = (
        "Nhiều người tưởng Mỹ sẽ dừng tay, nhưng khi các tàu du lịch ở vịnh Ba Tư "
        "rút hết, họ lập tức không kích Iran liên tục 13 ngày."
    )
    cues = split_sentence_cues(text, start=0.0, end=15.0, target_n=5)

    assert len(cues) >= 3

    # Check 1: Không dòng nào cắt 'vịnh Ba Tư', 'Iran', '13 ngày'
    for c in cues:
        t = c["text"]
        # 'vịnh Ba Tư'
        if "vịnh" in t:
            assert "vịnh Ba Tư" in t, f"'vịnh Ba Tư' bị cắt ngang trong dòng: '{t}'"
        if "Ba" in t and "Tư" in t:
            assert "Ba Tư" in t
        # '13 ngày'
        if "13" in t:
            assert "13 ngày" in t, f"'13 ngày' bị cắt ngang trong dòng: '{t}'"

    # Check 2: Không dòng nào kết thúc bằng từ cấm (ngoại trừ dòng cuối cùng kết thúc bằng dấu chấm)
    for idx, c in enumerate(cues[:-1]):
        words = c["text"].split()
        last_word = clean_word(words[-1]).lower()
        assert last_word not in FORBIDDEN_END_WORDS, (
            f"Dòng {idx+1} '{c['text']}' kết thúc bằng từ cấm '{last_word}'"
        )

    # Check 3: Mọi dòng có 3–7 từ (N=5, giới hạn cứng: tối đa N+2=7, tối thiểu 3 từ)
    for idx, c in enumerate(cues):
        wc = len(c["text"].split())
        assert 3 <= wc <= 7, f"Dòng {idx+1} '{c['text']}' có {wc} từ (không nằm trong [3, 7])"

    # Check 4: Điểm cắt rơi vào dấu phẩy hoặc trước 'nhưng'/'khi' khi có thể
    cut_found_comma = False
    cut_found_conjunction = False
    for idx, c in enumerate(cues[:-1]):
        nxt = cues[idx + 1]
        if c["text"].endswith(","):
            cut_found_comma = True
        first_w = clean_word(nxt["text"].split()[0]).lower()
        if first_w in ("nhưng", "khi"):
            cut_found_conjunction = True

    assert cut_found_comma, "Không có điểm cắt nào rơi vào dấu phẩy"
    assert cut_found_conjunction, "Không có điểm cắt nào rơi vào trước 'nhưng' hoặc 'khi'"


def test_1_proper_names_multi_words():
    # Tên riêng nhiều từ không bị cắt đôi
    text = (
        "Đại tướng Võ Nguyên Giáp đã trực tiếp chỉ huy quân đội ta "
        "giành thắng lợi vang dội trong chiến dịch Điện Biên Phủ lịch sử."
    )
    cues = split_sentence_cues(text, start=0.0, end=10.0, target_n=6)
    for c in cues:
        t = c["text"]
        if "Võ" in t:
            assert "Võ Nguyên Giáp" in t
        if "Điện" in t:
            assert "Điện Biên Phủ" in t


def test_2_common_noun_plus_proper_name():
    # Danh từ chung + tên riêng: thành phố Hồ Chí Minh, sông Hồng
    text = (
        "Đoàn đại biểu đã đến thăm thành phố Hồ Chí Minh và đi thuyền "
        "ngắm nhìn vẻ đẹp của dòng sông Hồng huyền thoại."
    )
    cues = split_sentence_cues(text, start=0.0, end=10.0, target_n=5)
    for c in cues:
        t = c["text"]
        if "thành phố" in t:
            assert "thành phố Hồ Chí Minh" in t
        if "sông" in t:
            assert "sông Hồng" in t


def test_3_numbers_and_complex_units():
    # Số + đơn vị tiền tệ, cự ly, thời gian
    text = (
        "Chính phủ vừa thông qua gói cứu trợ 5 tỷ đô la "
        "và dự kiến giải ngân trong vòng 24 giờ tới tại 150 km đường cao tốc."
    )
    cues = split_sentence_cues(text, start=0.0, end=12.0, target_n=5)
    for c in cues:
        t = c["text"]
        if "tỷ" in t:
            assert "5 tỷ đô la" in t
        if "24" in t:
            assert "24 giờ" in t
        if "150" in t:
            assert "150 km" in t


def test_4_short_sentence_kept_as_one_line():
    # Câu có <= N+2 từ giữ nguyên 1 dòng
    text = "Họ lập tức lên đường ngay."
    cues = split_sentence_cues(text, start=1.0, end=3.5, target_n=5)
    assert len(cues) == 1
    assert cues[0]["text"] == text
    assert cues[0]["start"] == 1.0
    assert cues[0]["end"] == 3.5


def test_5_very_long_sentence_balance():
    # Câu rất dài với nhiều vế: mọi dòng phải đảm bảo giới hạn cứng và không kết thúc bằng từ cấm
    text = (
        "Mặc dù điều kiện thời tiết vô cùng khắc nghiệt và đường sá sạt lở nghiêm trọng, "
        "nhưng lực lượng cứu hộ vẫn nỗ lực tiếp cận hiện trường để cứu giúp đồng bào, "
        "đồng thời nhanh chóng chuyển hàng nghìn tấn lương thực đến các vùng cô lập."
    )
    cues = split_sentence_cues(text, start=0.0, end=20.0, target_n=6)
    assert len(cues) >= 4
    for c in cues[:-1]:
        wc = len(c["text"].split())
        assert 3 <= wc <= 8 # N=6, max=8
        last_w = clean_word(c["text"].split()[-1]).lower()
        assert last_w not in FORBIDDEN_END_WORDS


def test_6_quotes_and_dialogue():
    # Câu có ngoặc kép
    text = (
        "Người phát ngôn bộ ngoại giao nhấn mạnh: 'Chúng tôi kiên quyết bảo vệ chủ quyền "
        "và toàn vẹn lãnh thổ thiêng liêng của Tổ quốc.'"
    )
    cues = split_sentence_cues(text, start=0.0, end=10.0, target_n=6)
    assert len(cues) >= 2
    for c in cues[:-1]:
        last_w = clean_word(c["text"].split()[-1]).lower()
        assert last_w not in FORBIDDEN_END_WORDS


def test_7_change_target_n_16_9():
    # Khung hình 16:9 với N=9
    text = (
        "Sau khi hoàn thành xuất sắc chuyến công tác dài ngày tại châu Âu, "
        "toàn bộ phái đoàn ngoại giao đã trở về thủ đô an toàn trong sự chào đón của nhân dân."
    )
    cues = split_sentence_cues(text, start=0.0, end=10.0, target_n=9)
    # Giới hạn cứng: tối đa 9+2=11 từ
    for c in cues:
        wc = len(c["text"].split())
        assert 3 <= wc <= 11


def test_8_change_target_n_1_1():
    # Khung hình 1:1 với N=6
    text = (
        "Các nhà khoa học đã phát hiện ra một loài sinh vật mới "
        "ở độ sâu hơn 3000 mét dưới đáy đại dương bao la."
    )
    cues = split_sentence_cues(text, start=0.0, end=10.0, target_n=6)
    for c in cues:
        wc = len(c["text"].split())
        assert 3 <= wc <= 8


def test_9_fixed_phrases_protection():
    # Cụm cố định: không những ... mà còn, bởi vì
    text = (
        "Họ không những hoàn thành vượt mức chỉ tiêu đề ra "
        "mà còn nhiệt tình hỗ trợ một số đồng nghiệp trong công ty."
    )
    cues = split_sentence_cues(text, start=0.0, end=8.0, target_n=5)
    for c in cues:
        t = c["text"]
        if "không" in t and "những" in t:
            assert "không những" in t
        if "mà" in t and "còn" in t:
            assert "mà còn" in t
        if "một" in t and "số" in t:
            assert "một số" in t


def test_10_minimum_duration_merging():
    # Thời lượng audio ngắn (dur=0.7s): các dòng con quá ngắn (<0.4s) sẽ được gộp nếu không vượt quá giới hạn từ
    text = "Thời gian trôi qua rất nhanh chóng."
    cues = split_sentence_cues(text, start=0.0, end=0.7, target_n=5)
    assert len(cues) == 1
    assert cues[0]["end"] - cues[0]["start"] >= 0.5


def test_11_locked_cues_preserved():
    # Đảm bảo các dòng đã sửa tay (locked=True) không bao giờ bị ghi đè khi chạy lại
    unit = {
        "id": 1,
        "start": 0.0,
        "end": 6.0,
        "vi_text": "Nhiều người tưởng Mỹ sẽ dừng tay, nhưng họ đã lầm.",
        "cues": [
            {"start": 0.0, "end": 3.0, "text": "Dòng người dùng tự sửa 1", "locked": True},
            {"start": 3.0, "end": 6.0, "text": "Dòng người dùng tự sửa 2", "locked": True},
        ]
    }
    res = auto_split_unit_cues(unit, target_n=5)
    assert len(res) == 2
    assert res[0]["text"] == "Dòng người dùng tự sửa 1"
    assert res[1]["text"] == "Dòng người dùng tự sửa 2"


def test_12_glossary_protection_from_analysis():
    # Bảo vệ thuật ngữ và nhân vật từ analysis.json
    analysis = {
        "glossary": [{"zh": "波斯湾", "vi": "vịnh Ba Tư"}],
        "characters": [{"name": "Donald Trump"}],
    }
    text = "Tổng thống Donald Trump đã ký sắc lệnh mới liên quan đến an ninh tại vịnh Ba Tư."
    cues = split_sentence_cues(text, start=0.0, end=10.0, target_n=5, analysis=analysis)
    for c in cues:
        t = c["text"]
        if "Donald" in t:
            assert "Donald Trump" in t
        if "vịnh" in t:
            assert "vịnh Ba Tư" in t


def test_13_user_sentence_boundaries_and_sacred_phrases():
    # Câu thực tế do user phản hồi: đảm bảo mọi dòng phụ đề đều nằm trong [3, target_n + 2] từ
    t1 = "Quân đội Mỹ từng lừng lững quét sạch Trung Đông, giờ đây lại rơi vào cảnh súng không có đạn, thật là khó."
    cues1 = split_sentence_cues(t1, start=0.0, end=3.8, target_n=5)
    for c in cues1:
        words = c["text"].split()
        assert 3 <= len(words) <= 7, f"Line word count violated: {len(words)} in '{c['text']}'"

    t2 = "Hôm thứ Sáu tuần trước, Iran đã tấn công căn cứ quân sự Mỹ tại Jordan, đồng thời xé toạc cái gọi là lệnh ngừng bắn giả tạo của Mỹ."
    cues2 = split_sentence_cues(t2, start=0.0, end=5.7, target_n=5)
    for c in cues2:
        words = c["text"].split()
        assert 3 <= len(words) <= 7, f"Line word count violated: {len(words)} in '{c['text']}'"
        # Đảm bảo không bị cắt ngang cụm từ
        assert "tấn công căn" not in c["text"]
        if "căn" in words:
            assert "cứ" in words
        if "lệnh" in words and "ngừng" in words:
            assert "bắn" in words

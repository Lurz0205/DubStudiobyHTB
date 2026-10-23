"""Unit tests for dubstudio.text.spoken_cleaner."""
from dubstudio.text.spoken_cleaner import (
    sanitize_spoken_vietnamese,
    is_translation_contaminated,
    clean_segments_spoken,
)


def test_sanitize_user_exact_complaint():
    # User complained about:
    # "Hôm nay, Star River sẽ Hãy cùng anh/chị tham quan 9 công nghệ siêu đỉnh này."
    # "Nếu video này thú vị, anh/chị nhớ long‑press, like, share nhé."
    raw1 = "Hôm nay, Star River sẽ Hãy cùng anh/chị tham quan 9 công nghệ siêu đỉnh này."
    cleaned1 = sanitize_spoken_vietnamese(raw1)
    assert "Star River" not in cleaned1
    assert "anh/chị" not in cleaned1
    assert "sẽ Hãy cùng" not in cleaned1
    assert "Hôm nay mình sẽ cùng các bạn tham quan 9 công nghệ siêu đỉnh này." == cleaned1

    raw2 = "Nếu video này thú vị, anh/chị nhớ long‑press, like, share nhé. Cảm ơn / ủng hộ."
    cleaned2 = sanitize_spoken_vietnamese(raw2)
    assert "anh/chị" not in cleaned2
    assert "long‑press" not in cleaned2
    assert " / " not in cleaned2
    assert "Nếu video này thú vị, các bạn nhớ nhấn giữ nút like, like và chia sẻ nhé. Cảm ơn và ủng hộ." == cleaned2


def test_sanitize_slashed_pronouns():
    assert "Các bạn hãy lắng nghe" == sanitize_spoken_vietnamese("Anh/chị hãy lắng nghe")
    assert "kính chào các bạn" == sanitize_spoken_vietnamese("kính chào anh/chị")
    assert "Mọi người thấy sao" == sanitize_spoken_vietnamese("Ông/bà thấy sao")
    assert "chào các bạn" == sanitize_spoken_vietnamese("chào bạn/quý vị")


def test_sanitize_tech_jargon():
    assert "nhấn giữ nút like" in sanitize_spoken_vietnamese("nhớ long-press nhé")
    assert "nhấn giữ nút like" in sanitize_spoken_vietnamese("nhớ long‑press nhé")
    assert "like và chia sẻ" in sanitize_spoken_vietnamese("hãy like, share video")


def test_is_translation_contaminated():
    assert is_translation_contaminated("Hãy cùng anh/chị theo dõi") is True
    assert is_translation_contaminated("Kênh Star River xin chào") is True
    assert is_translation_contaminated("Nhớ long-press nhé") is True
    assert is_translation_contaminated("Cảm ơn / ủng hộ") is True
    assert is_translation_contaminated("thật là khó堪.") is True
    assert is_translation_contaminated("Hôm nay mình sẽ cùng các bạn khám phá công nghệ mới.") is False


def test_sanitize_cjk_residue():
    raw = "Quân đội Mỹ đang rơi vào cảnh súng không có đạn, thật là khó堪."
    cleaned = sanitize_spoken_vietnamese(raw)
    assert "khó堪" not in cleaned
    assert "khó khăn" in cleaned
    assert "堪" not in cleaned

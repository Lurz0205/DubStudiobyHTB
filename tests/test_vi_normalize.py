import pytest
from dubstudio.text.vi_normalize import normalize_text, read_integer, read_decimal


def test_vi_normalize_integers():
    assert read_integer(0) == "không"
    assert read_integer(5) == "năm"
    assert read_integer(10) == "mười"
    assert read_integer(15) == "mười lăm"
    assert read_integer(21) == "hai mươi mốt"
    assert read_integer(24) == "hai mươi tư"
    assert read_integer(105) == "một trăm lẻ năm"
    assert read_integer(125) == "một trăm hai mươi lăm"
    assert read_integer(1000) == "một nghìn"
    assert read_integer(1000000) == "một triệu"


def test_vi_normalize_decimals():
    assert read_decimal("3.5") == "ba phẩy năm"
    assert read_decimal("0.75") == "không phẩy bảy năm"


def test_vi_normalize_units():
    assert "ba phẩy năm ki-lô-gam" in normalize_text("3.5kg")
    assert "mười ki-lô-mét" in normalize_text("10km")
    assert "hai mươi mét" in normalize_text("20m")
    assert "một trăm gam" in normalize_text("100g")
    assert "năm mươi mi-li-lít" in normalize_text("50ml")
    assert "sáu mươi ki-lô-mét trên giờ" in normalize_text("60km/h")


def test_vi_normalize_currencies():
    assert "đô la" in normalize_text("$100")
    assert "nhân dân tệ" in normalize_text("¥50")
    assert "đồng" in normalize_text("20000 VND")


def test_vi_normalize_percentages():
    assert "năm mươi phần trăm" in normalize_text("50%")
    assert "chín mươi chín phẩy chín phần trăm" in normalize_text("99.9%")


def test_vi_normalize_dates_and_times():
    text_date = normalize_text("15/10/2026")
    assert "ngày mười lăm tháng mười năm hai nghìn không trăm hai mươi sáu" in text_date
    text_time = normalize_text("10:30")
    assert "mười giờ ba mươi phút" in text_time


def test_vi_normalize_comprehensive_cases():
    cases = [
        ("Nặng 2kg", "ki-lô-gam"),
        ("Dài 15cm", "xen-ti-mét"),
        ("Tốc độ 80km/h", "ki-lô-mét trên giờ"),
        ("Giá 500đ", "đồng"),
        ("Còn 5 phút", "năm"),
        ("Khoảng 10s", "giây"),
        ("Đạt 100%", "một trăm phần trăm"),
        ("Tăng 2.5 lần", "hai phẩy năm"),
    ]
    for text, expected in cases:
        norm = normalize_text(text)
        assert expected in norm, f"Failed for '{text}': got '{norm}'"

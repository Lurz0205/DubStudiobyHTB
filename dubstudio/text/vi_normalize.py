"""Rule-based Vietnamese text normalizer for numbers, dates, units, currencies, and percentages."""
import re
from typing import Dict

# Unit dictionaries
UNITS_MAP: Dict[str, str] = {
    "kg": "ki-lô-gam",
    "g": "gam",
    "mg": "mi-li-gam",
    "km": "ki-lô-mét",
    "m": "mét",
    "cm": "xen-ti-mét",
    "mm": "mi-li-mét",
    "l": "lít",
    "ml": "mi-li-lít",
    "s": "giây",
    "h": "giờ",
    "min": "phút",
    "km/h": "ki-lô-mét trên giờ",
    "m/s": "mét trên giây",
}

CURRENCY_MAP: Dict[str, str] = {
    "$": "đô la",
    "USD": "đô la Mỹ",
    "VND": "đồng",
    "đ": "đồng",
    "¥": "nhân dân tệ",
    "NDT": "nhân dân tệ",
    "€": "ơ-rô",
}

ONES = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]


def _read_two_digits(n: int, is_sub: bool = False) -> str:
    """Read a number from 0 to 99."""
    if n < 10:
        return ("lẻ " if is_sub else "") + ONES[n]
    tens, ones = divmod(n, 10)
    tens_str = "mười" if tens == 1 else f"{ONES[tens]} mươi"
    if ones == 0:
        return tens_str
    if ones == 1:
        ones_str = "mốt" if tens > 1 else "một"
    elif ones == 4:
        ones_str = "tư" if tens > 1 else "bốn"
    elif ones == 5:
        ones_str = "lăm"
    else:
        ones_str = ONES[ones]
    return f"{tens_str} {ones_str}"


def _read_three_digits(n: int, read_zero_hundred: bool = False) -> str:
    """Read a number from 0 to 999."""
    hundreds, rem = divmod(n, 100)
    if hundreds == 0 and not read_zero_hundred:
        return _read_two_digits(rem, is_sub=False)

    h_str = f"{ONES[hundreds]} trăm"
    if rem == 0:
        return h_str
    if rem < 10:
        return f"{h_str} lẻ {ONES[rem]}"
    return f"{h_str} {_read_two_digits(rem, is_sub=False)}"


def read_integer(n: int) -> str:
    """Convert an integer into spoken Vietnamese words."""
    if n == 0:
        return "không"
    if n < 0:
        return f"âm {read_integer(-n)}"

    groups = []
    temp = n
    while temp > 0:
        groups.append(temp % 1000)
        temp //= 1000

    scales = ["", "nghìn", "triệu", "tỷ", "nghìn tỷ", "triệu tỷ"]
    words = []
    for i in reversed(range(len(groups))):
        val = groups[i]
        if val == 0:
            continue
        scale_name = scales[i]
        read_zero = (i < len(groups) - 1) and (groups[i] < 100)
        group_words = _read_three_digits(val, read_zero_hundred=(i < len(groups) - 1))
        if scale_name:
            words.append(f"{group_words} {scale_name}")
        else:
            words.append(group_words)

    return " ".join(words).strip()


def read_decimal(number_str: str) -> str:
    """Convert decimal number e.g. '3.5' or '3,5' into spoken words."""
    parts = re.split(r"[.,]", number_str)
    if len(parts) == 1:
        return read_integer(int(parts[0]))
    int_part = read_integer(int(parts[0]))
    dec_digits = " ".join(ONES[int(d)] for d in parts[1] if d.isdigit())
    return f"{int_part} phẩy {dec_digits}"


def normalize_text(text: str) -> str:
    """Normalize written text into spoken Vietnamese suitable for TTS."""
    if not text:
        return ""

    res = text

    # 0. Number ranges: 20-30 -> 20 đến 30
    res = re.sub(
        r"(\d+(?:[.,]\d+)?)\s*[-~–—]\s*(\d+(?:[.,]\d+)?)",
        r"\1 đến \2",
        res,
    )

    # 1. Percentages: 50% -> 50 phần trăm
    res = re.sub(
        r"(\d+(?:[.,]\d+)?)\s*%",
        lambda m: f"{read_decimal(m.group(1))} phần trăm",
        res,
    )

    # 2. Currencies with symbols before/after number
    # $100 -> 100 đô la
    res = re.sub(
        r"([$¥€])\s*(\d+(?:[.,]\d+)?)",
        lambda m: f"{read_decimal(m.group(2))} {CURRENCY_MAP.get(m.group(1), '')}",
        res,
    )
    # 100 USD / 100 VND / 100 đ (bound with non-word or end of string so 'đ' never matches 'độ')
    res = re.sub(
        r"(\d+(?:[.,]\d+)?)\s*(USD|VND|NDT|đ)(?=[^\w]|$)",
        lambda m: f"{read_decimal(m.group(1))} {CURRENCY_MAP.get(m.group(2), m.group(2))}",
        res,
    )

    # 2b. Degrees / Temperature: 20°C, 30° -> 20 độ C, 30 độ
    res = re.sub(
        r"(\d+(?:[.,]\d+)?)\s*(?:°C|℃)",
        lambda m: f"{read_decimal(m.group(1))} độ C",
        res,
        flags=re.IGNORECASE,
    )
    res = re.sub(
        r"(\d+(?:[.,]\d+)?)\s*°F",
        lambda m: f"{read_decimal(m.group(1))} độ F",
        res,
        flags=re.IGNORECASE,
    )
    res = re.sub(
        r"(\d+(?:[.,]\d+)?)\s*°(?=[^\w]|$)",
        lambda m: f"{read_decimal(m.group(1))} độ",
        res,
    )

    # 3. Units with numbers: 3.5kg -> ba phẩy năm ki-lô-gam
    for unit, unit_vi in sorted(UNITS_MAP.items(), key=lambda x: -len(x[0])):
        pattern = rf"(\d+(?:[.,]\d+)?)\s*{re.escape(unit)}(?=[^\w]|$)"
        res = re.sub(
            pattern,
            lambda m, u=unit_vi: f"{read_decimal(m.group(1))} {u}",
            res,
            flags=re.IGNORECASE,
        )

    # 4. Dates: 15/10/2026 -> ngày 15 tháng 10 năm 2026
    res = re.sub(
        r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})",
        lambda m: f"ngày {read_integer(int(m.group(1)))} tháng {read_integer(int(m.group(2)))} năm {read_integer(int(m.group(3)))}",
        res,
    )

    # 5. Times: 10:30 -> 10 giờ 30 phút
    res = re.sub(
        r"(\d{1,2}):(\d{2})",
        lambda m: f"{read_integer(int(m.group(1)))} giờ {read_integer(int(m.group(2)))} phút",
        res,
    )

    # 6. Standalone decimal numbers: 3.5 -> ba phẩy năm
    res = re.sub(
        r"\b(\d+)[.,](\d+)\b",
        lambda m: f"{read_integer(int(m.group(1)))} phẩy {' '.join(ONES[int(d)] for d in m.group(2))}",
        res,
    )

    # 7. Standalone integers: 123 -> một trăm hai mươi ba
    res = re.sub(
        r"\b(\d+)\b",
        lambda m: read_integer(int(m.group(1))),
        res,
    )

    # Clean multiple spaces
    res = re.sub(r"\s+", " ", res).strip()
    return res


# Alias for explicit naming
normalize_for_tts = normalize_text


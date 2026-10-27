"""
Dynamic Programming subtitle cue splitter by word count (Upgraded v2).

Key upgrades:
1. Unified Sentence-Level DP: Eliminates rigid comma fragmentation; DP naturally merges short clauses
   up to target_n while strongly preferring comma boundaries when splitting is needed.
2. Normalized Cost Function: Scales length penalty relative to target_n so DP never breaks sacred
   compound words just to balance line lengths at high target_n (e.g., target_n=12).
3. Expanded Vietnamese Compound Dictionary & Quantifier/Unit Locking.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple


COMMON_PROPER_PREFIXES = [
    "thành phố", "tỉnh", "quận", "huyện", "thị xã", "thị trấn", "phường", "xã",
    "vịnh", "sông", "núi", "biển", "đảo", "quần đảo", "bán đảo", "hồ", "đèo",
    "cầu", "nước", "đất nước", "quốc gia", "vương quốc", "đế quốc", "hải quân", "quân đội",
    "căn cứ", "sân bay", "thủ đô", "chiến dịch", "tổng thống", "thủ tướng", "đại sứ quán", "đại sứ"
]

# Từ điển từ ghép tiếng Việt (Thông dụng + Kỹ thuật + Đời sống + Quân sự/Tin tức)
FIXED_PHRASES = [
    # Quan hệ từ & Phụ từ ghép
    "bởi vì", "cho nên", "không những", "mà còn", "một số", "rất nhiều",
    "có thể", "không thể", "đã từng", "ngay cả", "mặc dù", "tuy nhiên", "như vậy",
    "do đó", "vì vậy", "thậm chí", "chẳng hạn", "ngoài ra", "hơn nữa",
    "trước hết", "cuối cùng", "đồng thời", "lập tức", "ngay lập tức", "vừa mới", "sắp sửa",
    "trong khi", "sau khi", "trước khi", "tất cả", "toàn bộ", "hầu hết", "mỗi bộ", "mỗi chiếc",
    # Kỹ thuật / Điện tử / Cơ khí / Khoa học
    "động cơ", "không chổi than", "chổi than", "lực đẩy", "cân nặng", "trọng lượng",
    "dòng điện", "điện áp", "hiệu điện thế", "công suất", "tốc độ", "gia tốc",
    "máy giặt", "máy lạnh", "điều hòa", "tủ lạnh", "máy bay", "máy tính", "điện thoại",
    "vi xử lý", "bộ nhớ", "màn hình", "pin dự phòng", "năng lượng", "mặt trời",
    "trí tuệ", "nhân tạo", "trí tuệ nhân tạo", "thuật toán", "hệ thống", "thiết bị",
    "cảm biến", "mạch điện", "bảng mạch", "linh kiện", "phần mềm", "phần cứng",
    "kích thước", "nhiệt độ", "áp suất", "tần số", "băng thông", "dung lượng",
    # Quân sự / Chính trị / Xã hội
    "ngừng bắn", "lệnh ngừng bắn", "quân sự", "căn cứ quân sự", "chiến tranh",
    "vũ khí", "vũ khí hạt nhân", "hạt nhân", "hòa bình", "hiệp định", "tên lửa",
    "phòng không", "chiến đấu cơ", "tàu sân bay", "tàu ngầm", "kinh tế", "chính phủ",
    # Danh từ/Động từ ghép thông dụng dễ bị cắt nhầm
    "thời gian", "không gian", "con người", "cuộc sống", "thế giới", "gia đình",
    "công việc", "học tập", "nghiên cứu", "phát triển", "sản xuất", "sử dụng",
    "hoạt động", "kiểm tra", "thử nghiệm", "kết quả", "nguyên nhân", "giải pháp",
    "khả năng", "tình trạng", "mức độ", "tối đa", "tối thiểu", "trung bình"
]

FORBIDDEN_END_WORDS = {
    "của", "ở", "với", "cho", "để", "là", "và", "hay", "hoặc", "những", "các",
    "một", "rất", "quá", "hơi", "đã", "sẽ", "đang", "vừa", "mới", "cũng", "vẫn",
    "còn", "bị", "được", "từ", "tại", "trong", "trên", "dưới", "bởi", "vì",
    "nếu", "khi", "như", "theo", "về", "đến", "tới", "ra", "vào", "lên", "xuống",
    "hơn", "kém", "gấp", "khoảng", "chừng", "mỗi", "mọi", "từng"
}

# Các từ nếu đứng ĐẦU dòng mới sẽ rất tự nhiên (được thưởng điểm cắt trước nó)
CLAUSE_STARTERS = {
    "nhưng", "mà", "nên", "vì", "bởi", "khi", "nếu", "rồi", "thì", "còn", "song",
    "tuy", "dù", "để", "cho", "với", "tại", "trong", "trên", "ngoài", "sau", "trước"
}

UNIT_WORDS = {
    "ngày", "tháng", "năm", "giờ", "tiếng", "phút", "giây", "tuần", "thế kỷ",
    "tỷ", "triệu", "nghìn", "ngàn", "trăm", "chục", "đồng", "đô", "đô la", "usd", "vnd",
    "km", "km/h", "m", "m/s", "cm", "mm", "nm", "kg", "g", "mg", "tấn", "tạ", "yến",
    "lít", "ml", "w", "kw", "mw", "v", "kv", "a", "ma", "mah", "ah", "hz", "khz", "mhz", "ghz",
    "độ", "phần trăm", "%",
    "người", "chiếc", "cái", "bộ", "cây", "con", "quả", "trái", "viên", "cục", "tấm", "thanh",
    "tàu", "máy", "máy bay", "chiến đấu cơ", "xe",
    "lần", "bước", "điểm", "mục", "phần", "tập", "loại", "kiểu", "dòng", "thế hệ"
}

NUMBER_WORDS = {
    "không", "một", "hai", "ba", "bốn", "tư", "năm", "lăm", "sáu", "bảy", "tám", "chín", "mười",
    "mươi", "mốt", "rưỡi", "trăm", "nghìn", "ngàn", "triệu", "tỷ", "vạn", "chục", "vài", "mấy"
}

QUANTIFIER_PREFIXES = {"hơn", "gần", "khoảng", "chừng", "tới", "đến", "gấp", "cỡ", "độ"}

PUNCT_STRIP = ",.!?:;—–…\"'”’()[]{}„“"
PUNCT_COMMA_SET = set(",;:—–")
PUNCT_TERMINAL_SET = set(".?!…")


def clean_word(w: str) -> str:
    """Strip bounding punctuation from a word token."""
    return w.strip(PUNCT_STRIP)


def is_number_token(w: str) -> bool:
    """Check if token is digits or a Vietnamese number word."""
    c = clean_word(w).lower()
    if not c:
        return False
    if re.match(r'^\d+([.,/]\d+)?[%a-zA-Z]*$', c):
        return True
    return c in NUMBER_WORDS


def is_capitalized(w: str) -> bool:
    """Check if a word token starts with a capital letter."""
    c = clean_word(w)
    return bool(c and c[0].isupper())


def get_default_n_for_aspect_ratio(aspect_ratio: str = "9:16") -> int:
    """
    Returns default word count N according to aspect ratio:
    9:16 -> 5, 1:1 -> 6, 16:9 -> 9.
    """
    ar = (aspect_ratio or "").lower()
    if "16:9" in ar:
        return 9
    elif "1:1" in ar:
        return 6
    return 5


def _normalize_spacing_and_dashes(text: str) -> str:
    """
    Gắn các dấu gạch ngang rời ( – , — ) vào từ đứng trước để không bị tính là 1 từ độc lập
    và giúp DP nhận diện được dấu ngắt vế ở cuối từ.
    """
    text = re.sub(r'\s+([—–])(\s+)', r'\1\2', text)
    return re.sub(r'\s+', ' ', text).strip()


def _split_into_clauses(text: str) -> List[str]:
    """Compatibility helper: splits text into clauses at punctuation marks."""
    if not text:
        return []
    raw = [c.strip() for c in re.split(r'[,;:—–]\s*', text) if c.strip()]
    return raw if raw else [text]


def find_forbidden_cuts(
    words: List[str],
    analysis: Optional[Dict[str, Any]] = None,
) -> Tuple[Set[int], List[Tuple[int, int]]]:
    """
    Identifies word boundary cut points that are FORBIDDEN because they split sacred phrases.
    Cut index k means cut between words[k-1] and words[k] (1 <= k < len(words)).
    """
    n = len(words)
    if n <= 1:
        return set(), []

    forbidden_cuts: Set[int] = set()
    atomic_intervals: List[Tuple[int, int]] = []

    def mark_range(st_idx: int, en_idx: int):
        """Mark all boundaries strictly inside [st_idx, en_idx] as forbidden, unless punctuation intervenes."""
        if en_idx > st_idx:
            atomic_intervals.append((st_idx, en_idx))
            for k in range(st_idx + 1, en_idx + 1):
                # Không khóa nếu từ phía trước kết thúc bằng dấu câu (ví dụ hết vế câu)
                prev_tok = words[k - 1]
                if prev_tok and prev_tok[-1] in (PUNCT_COMMA_SET | PUNCT_TERMINAL_SET):
                    continue
                forbidden_cuts.add(k)

    clean_words = [clean_word(w).lower() for w in words]

    # 1. Tên riêng: Chuỗi từ viết hoa liên tiếp
    i = 0
    while i < n:
        if is_capitalized(words[i]):
            j = i + 1
            while j < n and is_capitalized(words[j]):
                # Dừng nếu từ trước có dấu câu kết thúc
                if words[j - 1][-1] in (PUNCT_COMMA_SET | PUNCT_TERMINAL_SET):
                    break
                j += 1
            if j - i >= 2:
                mark_range(i, j - 1)
            i = j
        else:
            i += 1

    # 2. Danh từ chung + Tên riêng (vịnh Ba Tư, thành phố Hồ Chí Minh...)
    for prefix in COMMON_PROPER_PREFIXES:
        p_tokens = prefix.split()
        p_len = len(p_tokens)
        for idx in range(n - p_len + 1):
            if clean_words[idx:idx + p_len] == p_tokens:
                mark_range(idx, idx + p_len - 1)
                next_w_idx = idx + p_len
                if next_w_idx < n and is_capitalized(words[next_w_idx]):
                    end_prop = next_w_idx
                    while end_prop + 1 < n and is_capitalized(words[end_prop + 1]):
                        end_prop += 1
                    mark_range(idx, end_prop)

    # 3. Mục trong bảng thuật ngữ và tên nhân vật (analysis.json)
    if analysis:
        terms_to_protect = []
        for g in analysis.get("glossary", []):
            if isinstance(g, dict) and g.get("vi"):
                terms_to_protect.append(str(g["vi"]).strip())
        for c in analysis.get("characters", []):
            if isinstance(c, dict) and c.get("name"):
                terms_to_protect.append(str(c["name"]).strip())

        for term in terms_to_protect:
            t_tokens = [clean_word(tok).lower() for tok in term.split() if tok.strip()]
            t_len = len(t_tokens)
            if t_len >= 2:
                for idx in range(n - t_len + 1):
                    if clean_words[idx:idx + t_len] == t_tokens:
                        mark_range(idx, idx + t_len - 1)

    # 4. Cụm lượng từ + Số + Đơn vị (VD: "hơn 30 kg", "gấp 4 lần", "10 bộ")
    MULTI_WORD_UNITS = [
        "tỷ đô la", "tỷ đô", "triệu đô la", "triệu đô", "nghìn đô la", "nghìn đô",
        "đô la", "phần trăm", "km/h", "m/s", "héc ta", "thế kỷ"
    ]
    for munit in MULTI_WORD_UNITS:
        mu_tokens = munit.split()
        mu_len = len(mu_tokens)
        for idx in range(n - mu_len + 1):
            if clean_words[idx:idx + mu_len] == mu_tokens:
                st_p = idx - 1 if (idx > 0 and is_number_token(words[idx - 1])) else idx
                if st_p > 0 and clean_words[st_p - 1] in QUANTIFIER_PREFIXES:
                    st_p -= 1
                mark_range(st_p, idx + mu_len - 1)

    i = 0
    while i < n:
        if is_number_token(words[i]):
            st_p = i - 1 if (i > 0 and clean_words[i - 1] in QUANTIFIER_PREFIXES) else i
            j = i + 1
            while j < n:
                cw = clean_words[j]
                if cw in UNIT_WORDS or is_number_token(words[j]):
                    j += 1
                else:
                    break
            if j - st_p >= 2:
                mark_range(st_p, j - 1)
            i = max(i + 1, j)
        else:
            i += 1

    # 5. Từ điển từ ghép cố định (FIXED_PHRASES) - Sắp xếp cụm dài trước để ưu tiên khớp chuỗi dài
    sorted_phrases = sorted(FIXED_PHRASES, key=lambda x: len(x.split()), reverse=True)
    for phrase in sorted_phrases:
        p_tokens = phrase.split()
        p_len = len(p_tokens)
        for idx in range(n - p_len + 1):
            if clean_words[idx:idx + p_len] == p_tokens:
                mark_range(idx, idx + p_len - 1)

    return forbidden_cuts, atomic_intervals


def _split_single_sentence_dp(
    raw_text: str,
    start: float,
    end: float,
    target_n: int = 5,
    analysis: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Split a single complete sentence into balanced, grammatically natural subtitle cues using DP.
    Handles both short clause merging and long clause splitting unified in one pass.
    """
    norm_text = _normalize_spacing_and_dashes(raw_text)
    words = norm_text.split()
    total_words = len(words)
    total_dur = max(0.2, end - start)

    # Ngưỡng dung sai trên: cho phép linh hoạt +1 với target nhỏ, +2 với target lớn
    tolerance_up = 1 if target_n <= 6 else 2
    max_words_hard = target_n + tolerance_up

    # Nếu cả câu đã nằm gọn trong ngưỡng cho phép -> Giữ nguyên 1 dòng!
    if total_words <= max_words_hard:
        return [{
            "start": round(start, 3),
            "end": round(end, 3),
            "text": norm_text,
            "locked": False,
        }]

    forbidden_cuts, atomic_intervals = find_forbidden_cuts(words, analysis=analysis)

    INF = 1e9
    dp = [INF] * (total_words + 1)
    parent = [-1] * (total_words + 1)
    dp[0] = 0.0

    # Ngưỡng từ tối thiểu trên 1 dòng: không để tạo dòng < 4 từ khi target_n >= 8
    min_words_hard = 3 if target_n < 8 else 4

    # Độ dài tối ưu lý tưởng nếu phải chia đôi/chia ba câu
    ideal_len = min(target_n, max(min_words_hard, round(total_words / max(2, round(total_words / target_n)))))

    for j in range(1, total_words + 1):
        for i in range(0, j):
            if dp[i] >= INF:
                continue

            length = j - i
            is_last_line = (j == total_words)

            # Kiểm tra xem đoạn [i, j-1] có phải là 1 cụm bất khả xâm phạm dài hơn bình thường không
            is_atomic_override = any(a_st <= i and j - 1 <= a_en for a_st, a_en in atomic_intervals)

            if not is_atomic_override:
                # Cho phép vượt nhẹ max_words_hard tối đa 2 từ với chi phí cao trong trường hợp bất khả kháng
                if length > max_words_hard + 2:
                    continue
                if not is_last_line and length < min_words_hard:
                    continue

            cost = 0.0

            # 1. Phạt cực nặng nếu cắt ngang từ ghép / cụm số lượng (1000 điểm)
            if j < total_words and j in forbidden_cuts:
                cost += 1000.0

            # 2. Phạt nặng nếu kết thúc dòng bằng hư từ / giới từ ("của", "với", "hơn", "những"...)
            if j < total_words:
                last_w = clean_word(words[j - 1]).lower()
                if last_w in FORBIDDEN_END_WORDS:
                    # Nếu sau hư từ có dấu phẩy (hiếm) thì không phạt, ngược lại phạt 500
                    if not (words[j - 1] and words[j - 1][-1] in PUNCT_COMMA_SET):
                        cost += 500.0

            # 3. Hàm phạt độ dài chuẩn hóa (Normalized Length Penalty)
            # Thay vì phạt nặng khi nhỏ hơn target_n, ta cho phép vùng linh hoạt [ideal_len - 2, target_n + 1]
            if length > max_words_hard:
                cost += 300.0 + (length - max_words_hard) * 150.0
            else:
                # Khoảng cách tương đối so với độ dài cân bằng
                ref_target = ideal_len if total_words < target_n * 2 else target_n
                diff = abs(length - ref_target) / max(1.0, float(ref_target))
                cost += (diff ** 2) * 80.0

                # Phạt nhẹ nếu dòng hơi ngắn (dưới 50% target_n) để chống tách vụn 4-5 từ khi chọn 12 từ
                if length < max(4, int(target_n * 0.55)):
                    cost += (int(target_n * 0.55) - length) * 45.0

            # 4. Phạt dòng mồ côi ở cuối câu (Orphan words)
            if is_last_line and length < min_words_hard:
                if length == 1:
                    cost += 1200.0
                elif length == 2:
                    cost += 600.0
                else:
                    cost += 250.0

            # 5. Điểm thưởng (Bonus) tại các ranh giới ngữ pháp tự nhiên
            if j < total_words:
                prev_token = words[j - 1]
                next_token_clean = clean_word(words[j]).lower()

                has_comma_punct = bool(prev_token and prev_token[-1] in PUNCT_COMMA_SET)
                has_term_punct = bool(prev_token and prev_token[-1] in PUNCT_TERMINAL_SET)
                is_clause_starter = (next_token_clean in CLAUSE_STARTERS)

                if has_term_punct:
                    cost -= 120.0
                elif has_comma_punct:
                    # Thưởng lớn khi ngắt đúng dấu phẩy, NHƯNG chỉ thưởng tối đa khi dòng đã đủ dài (>= 50% target_n)
                    # Điều này ngăn việc ngắt ở dấu phẩy quá sớm tạo ra câu 3-4 từ!
                    if length >= max(3, int(target_n * 0.5)):
                        cost -= 95.0
                    else:
                        cost -= 15.0

                if is_clause_starter:
                    cost -= 35.0
                    if has_comma_punct:
                        cost -= 25.0

            total_cost = dp[i] + cost
            if total_cost < dp[j]:
                dp[j] = total_cost
                parent[j] = i

    # Truy vết điểm cắt tối ưu
    if dp[total_words] >= INF:
        num_chunks = max(2, round(total_words / target_n))
        step = total_words / num_chunks
        cuts = [int(round(k * step)) for k in range(1, num_chunks)]
    else:
        cuts = []
        curr = total_words
        while curr > 0:
            p = parent[curr]
            if p > 0:
                cuts.append(p)
            curr = p
        cuts.reverse()

    lines: List[str] = []
    c_idx = 0
    for cut in cuts:
        lines.append(" ".join(words[c_idx:cut]))
        c_idx = cut
    lines.append(" ".join(words[c_idx:]))

    # 6. Phân bổ thời gian theo tỷ lệ ký tự (kèm cộng thêm nhịp nghỉ cho dấu phẩy/chấm)
    def _effective_weight(line_str: str) -> float:
        base = float(len(line_str.replace(" ", "")))
        if line_str and line_str[-1] in PUNCT_COMMA_SET:
            base += 2.5  # Cộng thêm thời lượng tương đương ~2.5 ký tự cho nhịp nghỉ dấu phẩy
        elif line_str and line_str[-1] in PUNCT_TERMINAL_SET:
            base += 4.0
        return max(1.0, base)

    weights = [_effective_weight(l) for l in lines]
    total_weight = sum(weights)

    cue_durations = [
        round(total_dur * (w / total_weight), 3)
        for w in weights
    ]

    # Đảm bảo thời lượng hiển thị tối thiểu (0.5s) nếu có thể gộp mà không vượt quá max_words_hard + 1
    min_allowable_dur = 0.5
    while len(lines) > 1 and any(d < min_allowable_dur for d in cue_durations):
        min_idx = min(range(len(cue_durations)), key=lambda idx: cue_durations[idx])
        if cue_durations[min_idx] >= min_allowable_dur:
            break

        if min_idx == len(lines) - 1:
            target_merge = min_idx - 1
        elif min_idx == 0:
            target_merge = 1
        else:
            left_w = len(lines[min_idx - 1].split())
            right_w = len(lines[min_idx + 1].split())
            target_merge = (min_idx - 1) if left_w <= right_w else (min_idx + 1)

        merged_len = len((lines[target_merge] + " " + lines[min_idx]).split())
        if merged_len > max_words_hard + 1:
            break

        if target_merge < min_idx:
            lines[target_merge] = lines[target_merge] + " " + lines[min_idx]
            lines.pop(min_idx)
        else:
            lines[min_idx] = lines[min_idx] + " " + lines[target_merge]
            lines.pop(target_merge)

        weights = [_effective_weight(l) for l in lines]
        total_weight = sum(weights)
        cue_durations = [
            round(total_dur * (w / total_weight), 3)
            for w in weights
        ]

    # Gán timestamp cuối cùng
    cues: List[Dict[str, Any]] = []
    curr_time = start
    for idx, (line_text, dur) in enumerate(zip(lines, cue_durations), start=1):
        if idx == len(lines):
            c_end = end
        else:
            c_end = round(curr_time + dur, 3)
            c_end = min(c_end, end - 0.1 * (len(lines) - idx))
            c_end = max(c_end, curr_time + 0.1)

        cues.append({
            "start": round(curr_time, 3),
            "end": round(c_end, 3),
            "text": line_text.strip(),
            "locked": False,
        })
        curr_time = c_end

    return cues


def split_sentence_cues(
    text: str,
    start: float,
    end: float,
    target_n: int = 5,
    analysis: Optional[Dict[str, Any]] = None,
    clauses: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Split text into subtitle cues:
    1. Split complete sentences (. ? ! …) into distinct segments first.
       (Short sentences may still be merged if combined <= target_n).
    2. Feed each sentence directly into the upgraded DP engine, which handles comma clauses,
       compound words, and target word limits globally without fragmenting into 4-5 word orphans.
    """
    raw_text = (text or "").strip()
    # Flatten any embedded newlines so sentences can merge or split strictly based on target_n
    raw_text = re.sub(r'\s*\n+\s*', ' ', raw_text).strip()
    if not raw_text:
        return []

    total_dur = max(0.2, end - start)

    # 1. Tách các câu hoàn chỉnh (. ? ! …) nhưng cẩn thận không tách nhầm số thập phân (VD: 3.5)
    raw_sentences: List[str] = []
    cur_start = 0
    for m in re.finditer(r'([.?!…]+)(\s+|$)', raw_text):
        end_pos = m.end()
        cand = raw_text[cur_start:end_pos].strip()
        if cand:
            raw_sentences.append(cand)
            cur_start = end_pos
    rem = raw_text[cur_start:].strip()
    if rem:
        raw_sentences.append(rem)

    if not raw_sentences:
        raw_sentences = [raw_text]

    # Gom các câu quá ngắn (VD: "Đúng vậy." + câu sau) nếu tổng số từ <= target_n
    merged_sentences: List[str] = []
    for s in raw_sentences:
        if merged_sentences:
            prev_words = len(merged_sentences[-1].split())
            curr_words = len(s.split())
            if prev_words <= 3 and (prev_words + curr_words) <= target_n + 1:
                merged_sentences[-1] = merged_sentences[-1] + " " + s
                continue
        merged_sentences.append(s)

    if len(merged_sentences) == 1:
        return _split_single_sentence_dp(
            raw_text=merged_sentences[0],
            start=start,
            end=end,
            target_n=target_n,
            analysis=analysis,
        )

    # Phân bổ thời gian cho từng câu hoàn chỉnh trước khi chạy DP trên từng câu
    total_chars = sum(len(s.replace(" ", "")) for s in merged_sentences)
    if total_chars <= 0:
        total_chars = max(1, len(raw_text))

    all_cues: List[Dict[str, Any]] = []
    curr_time = start
    for s_idx, s_text in enumerate(merged_sentences):
        s_chars = len(s_text.replace(" ", ""))
        s_dur = total_dur * (s_chars / total_chars)
        s_end = round(curr_time + s_dur, 3) if s_idx < len(merged_sentences) - 1 else end
        s_end = max(s_end, curr_time + 0.1)

        sub_cues = _split_single_sentence_dp(
            raw_text=s_text,
            start=curr_time,
            end=s_end,
            target_n=target_n,
            analysis=analysis,
        )
        all_cues.extend(sub_cues)
        curr_time = s_end

    return all_cues


def auto_split_unit_cues(
    unit: Dict[str, Any],
    target_n: int = 5,
    analysis: Optional[Dict[str, Any]] = None,
    force: bool = False,
) -> List[Dict[str, Any]]:
    """
    Split a unit into cues, preserving any cues already locked by manual edits unless force=True.
    Synchronizes both unit["cues"] and unit["sub_slices"].
    """
    existing_cues = unit.get("cues")
    if not force and existing_cues and isinstance(existing_cues, list):
        if any(c.get("locked") for c in existing_cues):
            unit["sub_slices"] = [
                {"text": c.get("text", "").strip(), "start": float(c.get("start", 0)), "end": float(c.get("end", 0))}
                for c in existing_cues if c.get("text", "").strip()
            ] if len(existing_cues) > 1 else None
            return existing_cues

    vi_text = str(unit.get("vi_text") or unit.get("text") or unit.get("src_text") or "").strip()
    vi_text = re.sub(r'\s*\n+\s*', ' ', vi_text).strip()
    if not vi_text:
        return []

    st = float(unit.get("start", 0.0))
    en = float(unit.get("end", st + 1.0))
    clauses = unit.get("clauses")

    cues = split_sentence_cues(
        text=vi_text,
        start=st,
        end=en,
        target_n=target_n,
        analysis=analysis,
        clauses=clauses,
    )
    unit["cues"] = cues
    unit["sub_slices"] = [
        {"text": c.get("text", "").strip(), "start": float(c.get("start", st)), "end": float(c.get("end", en))}
        for c in cues if c.get("text", "").strip()
    ] if len(cues) > 1 else None
    return cues


def auto_split_all_units(
    units: List[Dict[str, Any]],
    target_n: int = 5,
    analysis: Optional[Dict[str, Any]] = None,
    force: bool = False,
) -> List[Dict[str, Any]]:
    """
    Processes all units with auto_split_unit_cues.
    """
    for u in units:
        auto_split_unit_cues(u, target_n=target_n, analysis=analysis, force=force)
    return units

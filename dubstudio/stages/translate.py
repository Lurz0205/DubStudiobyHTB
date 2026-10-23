"""Stage: translate. Translates segments using Gemini API client with live batch persistence and resume."""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import re
from dubstudio.config import AppConfig
from dubstudio.events import emit_event
from dubstudio.jobstate import JobContext, compute_file_hash
from dubstudio.llm.gemini import GeminiTranslator

def _split_one_segment(seg: dict) -> list[dict]:
    vi_text = str(seg.get("vi_text") or "").strip()
    st = float(seg.get("start", 0.0))
    en = float(seg.get("end", 0.0))
    dur = round(en - st, 3)

    words = vi_text.split()
    # Segment is too long if:
    # 1. dur > 7.0 seconds
    # 2. OR dur >= 4.5 seconds AND (len(vi_text) > 48 or len(words) >= 11)
    # Never split segments with dur <= 3.2s or words <= 7
    if dur <= 3.2 or len(words) <= 7:
        return [seg]
    if not (dur > 7.0 or (dur >= 4.5 and (len(vi_text) > 48 or len(words) >= 11))):
        return [seg]

    mid = len(vi_text) // 2
    best_idx = -1
    best_score = float("inf")

    # 1. Search for sentence terminators (. ? ! …)
    for m in re.finditer(r'([.?!…])\s+', vi_text):
        idx = m.end()
        score = abs(idx - mid)
        if score < best_score:
            best_score = score
            best_idx = idx

    # 2. Search for clause punctuation (, ; : — – -)
    if best_idx == -1 or (best_score > len(vi_text) * 0.35):
        for m in re.finditer(r'([,;:—–\-])\s+', vi_text):
            idx = m.end()
            if idx > len(vi_text) * 0.2 and idx < len(vi_text) * 0.8:
                score = abs(idx - mid)
                if score < best_score:
                    best_score = score
                    best_idx = idx

    # 3. Search for conjunctions
    if best_idx == -1 or (best_score > len(vi_text) * 0.35):
        for conj in [" nhưng ", " mà ", " nên ", " vì ", " và ", " rồi ", " thì ", " hoặc ", " nếu ", " để "]:
            pos = 0
            while True:
                found = vi_text.find(conj, pos)
                if found == -1:
                    break
                idx = found + 1
                if idx > len(vi_text) * 0.2 and idx < len(vi_text) * 0.8:
                    score = abs(idx - mid) * 1.2
                    if score < best_score:
                        best_score = score
                        best_idx = idx
                pos = found + len(conj)

    # 4. Fallback: split at nearest word boundary
    if best_idx == -1:
        for m in re.finditer(r'\s+', vi_text):
            idx = m.end()
            if idx > len(vi_text) * 0.25 and idx < len(vi_text) * 0.75:
                score = abs(idx - mid) * 1.5
                if score < best_score:
                    best_score = score
                    best_idx = idx

    if best_idx <= 0 or best_idx >= len(vi_text):
        return [seg]

    part1_vi = vi_text[:best_idx].strip()
    part2_vi = vi_text[best_idx:].strip()
    if not part1_vi or not part2_vi:
        return [seg]

    # Calculate proportional duration by word count
    w1 = max(1, len(part1_vi.split()))
    w2 = max(1, len(part2_vi.split()))
    ratio = w1 / (w1 + w2)
    dur1 = round(dur * ratio, 2)
    split_t = round(st + dur1, 2)

    # Enforce minimum segment duration 1.4s and at least 4 words per part
    if split_t - st < 1.4 or en - split_t < 1.4 or w1 < 4 or w2 < 4:
        return [seg]

    # Split Chinese text proportionally
    zh_text = str(seg.get("src_text") or seg.get("zh") or "").strip()
    zh1, zh2 = "", ""
    if zh_text:
        zh_punct_match = [m.end() for m in re.finditer(r'([，。！？；])', zh_text)]
        if zh_punct_match:
            mid_zh = int(len(zh_text) * ratio)
            best_zh_idx = min(zh_punct_match, key=lambda x: abs(x - mid_zh))
            zh1 = zh_text[:best_zh_idx].strip()
            zh2 = zh_text[best_zh_idx:].strip()
        else:
            mid_zh = max(1, int(len(zh_text) * ratio))
            zh1 = zh_text[:mid_zh].strip()
            zh2 = zh_text[mid_zh:].strip()

    seg1 = dict(seg)
    seg1["start"] = st
    seg1["end"] = split_t
    seg1["dur"] = round(split_t - st, 3)
    seg1["vi_text"] = part1_vi
    seg1["tts_text"] = part1_vi
    seg1["src_text"] = zh1 or zh_text
    seg1["zh"] = zh1 or zh_text
    seg1["tts_file"] = None
    seg1["tts_dur"] = None
    seg1["fit"] = None
    seg1["flags"] = list(seg.get("flags") or [])

    seg2 = dict(seg)
    seg2["start"] = split_t
    seg2["end"] = en
    seg2["dur"] = round(en - split_t, 3)
    seg2["vi_text"] = part2_vi
    seg2["tts_text"] = part2_vi
    seg2["src_text"] = zh2 or zh_text
    seg2["zh"] = zh2 or zh_text
    seg2["tts_file"] = None
    seg2["tts_dur"] = None
    seg2["fit"] = None
    seg2["flags"] = list(seg.get("flags") or [])

    return _split_one_segment(seg1) + _split_one_segment(seg2)


def auto_split_long_segments(segments: list[dict]) -> list[dict]:
    """Automatically splits long sentences into concise subtitle segments with proportional time allocation."""
    result = []
    for s in segments:
        result.extend(_split_one_segment(s))

    for idx, item in enumerate(result, start=1):
        item["id"] = idx
    return result


STYLE_LINT_DANGLING_1WORD = {
    "và", "nhưng", "mà", "rồi", "nên", "vì", "khi", "để", "do", "bởi", "tuy", "hoặc", "hay",
    "với", "như", "gồm", "là", "rằng", "đến"
}
STYLE_LINT_DANGLING_2WORDS = {
    "tương đương", "tương tự", "so với", "như là", "bao gồm", "gồm có", "dẫn đến", "khiến cho",
    "làm cho", "đối với", "cùng với", "thuộc về", "dựa trên", "dựa vào", "bởi vì", "cho thấy",
    "cho rằng", "nghĩ rằng", "nói rằng"
}
STYLE_LINT_CONJUNCTIONS = STYLE_LINT_DANGLING_1WORD | STYLE_LINT_DANGLING_2WORDS


def check_style_lint(vi_text: str) -> Optional[str]:
    """
    Check if vi_text starts with '...'/'…', or ends with '...'/'…', comma, conjunction,
    or dangling comparative phrases (tương đương, so với, bao gồm, dẫn đến, etc.).
    Returns flag reason or None if clean.
    """
    t = (vi_text or "").strip()
    if not t:
        return None

    if t.startswith("...") or t.startswith("…"):
        return "starts_with_ellipsis"

    if t.endswith("...") or t.endswith("…"):
        return "ends_with_ellipsis"

    if t.endswith(",") or t.endswith("，"):
        return "ends_with_comma"

    # Strip trailing punctuation (. ! ? : ; , …) and check tokens
    t_clean = re.sub(r'[\s.!?:;,，。！？；…]+$', '', t)
    tokens = t_clean.split()
    if not tokens:
        return None

    if len(tokens) >= 2:
        last2 = f"{tokens[-2]} {tokens[-1]}".lower()
        if last2 in STYLE_LINT_DANGLING_2WORDS:
            return "ends_with_dangling_phrase"

    if tokens[-1].lower() in STYLE_LINT_DANGLING_1WORD:
        return "ends_with_conjunction"

    return None


def _merge_two_unit_dicts(u1: dict, u2: dict) -> dict:
    st = min(u1["start"], u2["start"])
    en = max(u1["end"], u2["end"])
    dur = round(en - st, 3)
    speech_time = round(u1.get("speech_time", 0.0) + u2.get("speech_time", 0.0), 3)

    parts = list(u1.get("parts", []))
    for p in u2.get("parts", []):
        if p not in parts:
            parts.append(p)

    raw_parts = list(u1.get("raw_parts") or []) + list(u2.get("raw_parts") or [])

    zh1 = u1.get("zh") or u1.get("src_text") or ""
    zh2 = u2.get("zh") or u2.get("src_text") or ""
    zh = (zh1 + " " + zh2).strip()

    clauses = []
    if u1.get("clauses"):
        clauses.extend(u1["clauses"])
    if u2.get("clauses"):
        clauses.extend(u2["clauses"])

    from dubstudio.stages.units import _split_into_clauses
    zh_chars = len([c for c in zh if not c.isspace()])
    if not clauses and (dur > 15.0 or zh_chars > 80):
        clauses = _split_into_clauses(raw_parts, zh, st, en)

    merged = dict(u1)
    merged["start"] = st
    merged["end"] = en
    merged["dur"] = dur
    merged["speech_time"] = speech_time
    merged["parts"] = parts
    merged["raw_parts"] = raw_parts
    merged["zh"] = zh
    merged["src_text"] = zh
    merged["min_chars"] = u1.get("min_chars", 0) + u2.get("min_chars", 0)
    merged["target_chars"] = u1.get("target_chars", 0) + u2.get("target_chars", 0)
    merged["max_chars"] = u1.get("max_chars", 0) + u2.get("max_chars", 0)
    merged["clauses"] = clauses if clauses else None
    merged["vi_text"] = ""
    merged["tts_text"] = ""
    return merged


def run_style_lint_and_repair(
    units: list[dict],
    translator: GeminiTranslator,
    context: Optional[dict] = None,
    style: Optional[str] = None,
    stage_name: str = "translate",
) -> list[dict]:
    """
    Scans units for style lint flags. If any unit is flagged:
    - Merges it with adjacent unit.
    - Re-translates all newly merged units in ONE single request using build_prompt(task_type="polish").
    """
    if not units or len(units) < 2:
        return units

    flagged_indices = set()
    for idx, u in enumerate(units):
        flag = check_style_lint(u.get("vi_text", ""))
        if flag:
            flagged_indices.add(idx)

        # Check severed comparator/preposition between unit idx and unit idx+1
        if idx + 1 < len(units):
            next_t = (units[idx + 1].get("vi_text") or "").strip().lower()
            prev_clean = re.sub(r'[\s.!?:;,，。！？；…]+$', '', u.get("vi_text", "")).strip().lower()
            if next_t.startswith("với ") and any(prev_clean.endswith(w) for w in ["tương đương", "so", "cùng", "đối"]):
                flagged_indices.add(idx)

    if not flagged_indices:
        return units

    emit_event(
        stage_name,
        90.0,
        f"Phát hiện {len(flagged_indices)} câu bị ngắt lửng/dấu nối (style_lint). Đang gộp với câu kế và dịch lại liền mạch...",
        level="info",
    )

    from dubstudio.llm.gemini import build_prompt

    new_units = []
    skip_next = False
    merged_units = []

    for idx in range(len(units)):
        if skip_next:
            skip_next = False
            continue

        curr = units[idx]
        if idx in flagged_indices:
            flag = check_style_lint(curr.get("vi_text", ""))
            if flag == "starts_with_ellipsis" and new_units:
                prev = new_units.pop()
                m = _merge_two_unit_dicts(prev, curr)
                new_units.append(m)
                merged_units.append(m)
                continue

            if idx + 1 < len(units):
                nxt = units[idx + 1]
                m = _merge_two_unit_dicts(curr, nxt)
                new_units.append(m)
                merged_units.append(m)
                skip_next = True
            elif new_units:
                prev = new_units.pop()
                m = _merge_two_unit_dicts(prev, curr)
                new_units.append(m)
                merged_units.append(m)
            else:
                new_units.append(curr)
        else:
            new_units.append(curr)

    # Re-index units
    for i, u in enumerate(new_units, start=1):
        u["id"] = i

    # Re-translate the newly merged units in ONE single request
    if merged_units:
        summary = (context.get("summary") or context.get("topic") or "") if context else ""
        system_instruction, content_str = build_prompt(
            batch_units=merged_units,
            all_units=new_units,
            context=context,
            style=style,
            story_so_far=summary,
            task_type="polish",
        )
        try:
            res = translator._translate_batch(
                merged_units,
                system_instruction,
                stage_name,
                current_idx=len(merged_units),
                total_items=len(merged_units),
                style=style,
                content_str=content_str,
            )
            translator._merge_translations(new_units, res)
        except Exception as e:
            emit_event(stage_name, 90.0, f"Dịch lại câu gộp gặp lỗi: {e}", level="warning")

    return new_units


def parse_manual_translation_text(raw_text: str, items: list[dict]) -> list[dict]:
    """Parse manual translated text from user into items list with robust format recognition."""
    import re
    from dubstudio.text.vi_normalize import normalize_for_tts
    from dubstudio.text.spoken_cleaner import sanitize_spoken_vietnamese

    # 1. Try JSON block or direct JSON
    json_candidate = raw_text.strip()
    if "```json" in json_candidate:
        m = re.search(r"```json\s*(.*?)\s*```", json_candidate, re.DOTALL)
        if m:
            json_candidate = m.group(1).strip()
    elif "```" in json_candidate:
        m = re.search(r"```\s*(.*?)\s*```", json_candidate, re.DOTALL)
        if m:
            json_candidate = m.group(1).strip()

    parsed_json = None
    try:
        loaded = json.loads(json_candidate)
        if isinstance(loaded, list):
            parsed_json = loaded
        elif isinstance(loaded, dict):
            for k in ("translations", "segments", "data", "items", "results", "lines"):
                if k in loaded and isinstance(loaded[k], list):
                    parsed_json = loaded[k]
                    break
    except Exception:
        pass

    if parsed_json:
        id_to_vi = {}
        for entry in parsed_json:
            if isinstance(entry, dict):
                eid = entry.get("id") or entry.get("index")
                txt = entry.get("vi") or entry.get("vi_text") or entry.get("text") or ""
                if eid is not None and txt:
                    try:
                        id_to_vi[int(eid)] = str(txt).strip()
                    except (ValueError, TypeError):
                        pass
        if id_to_vi:
            for s in items:
                sid = s.get("id")
                if sid in id_to_vi:
                    clean_vi = sanitize_spoken_vietnamese(id_to_vi[sid])
                    s["vi_text"] = clean_vi
                    s["tts_text"] = normalize_for_tts(clean_vi)
            return items

    # 2. Numbered line parsing (e.g. [1] Text, 1. Text, 1: Text, 1) Text)
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    id_to_text = {}
    pattern = re.compile(r'^(?:\[(\d+)\]|(\d+)[\.\:\)]|\((\d+)\))\s*(.*)$')
    for line in lines:
        match = pattern.match(line)
        if match:
            num_str = match.group(1) or match.group(2) or match.group(3)
            txt = match.group(4).strip()
            if num_str and txt:
                try:
                    id_to_text[int(num_str)] = txt
                except (ValueError, TypeError):
                    pass

    if id_to_text:
        matched_any = False
        for s in items:
            sid = s.get("id")
            if sid in id_to_text:
                clean_vi = sanitize_spoken_vietnamese(id_to_text[sid])
                s["vi_text"] = clean_vi
                s["tts_text"] = normalize_for_tts(clean_vi)
                matched_any = True
        if matched_any:
            return items

    # 3. Fallback: sequential line mapping
    clean_lines = [
        l for l in lines
        if not l.startswith("#") and not l.startswith("```") and len(l) > 1
    ]
    for idx, s in enumerate(items):
        if idx < len(clean_lines):
            line_val = clean_lines[idx]
            m_lead = re.match(r'^(?:\[?\d+\]?[\.\:\)]?\s*)(.*)$', line_val)
            if m_lead and m_lead.group(1):
                line_val = m_lead.group(1).strip()
            clean_vi = sanitize_spoken_vietnamese(line_val)
            s["vi_text"] = clean_vi
            s["tts_text"] = normalize_for_tts(clean_vi)

    return items


def run_manual_translation(
    job: JobContext,
    items: list[dict],
    style: str,
    using_units: bool,
    stage_name: str,
    on_batch_done: callable,
) -> list[dict]:
    """Execute manual translation: save prompt, emit event, wait for response file, and parse."""
    chinese_lines = []
    for s in items:
        sid = s.get("id", len(chinese_lines) + 1)
        zh = (s.get("zh") or s.get("src_text") or "").strip()
        chinese_lines.append(f"[{sid}] {zh}")

    chinese_block = "\n".join(chinese_lines)
    prompt_text = (
        "Bạn là chuyên gia dịch thuật và biên tập phụ đề video tiếng Trung sang tiếng Việt chuyên nghiệp.\n"
        "Hãy dịch toàn bộ danh sách các câu tiếng Trung dưới đây sang tiếng Việt tự nhiên, chuẩn văn phong đời thường, giữ trọn cảm xúc và ngữ cảnh video.\n\n"
        f"Phong cách dịch mong muốn: {style}\n\n"
        "Quy tắc quan trọng:\n"
        "1. Dịch chuẩn xác, thuần Việt, tự nhiên, câu cú mượt mà như người bản xứ nói chuyện.\n"
        "2. Không bao giờ ngắt câu lửng lơ ở các từ so sánh, bắc cầu (như 'tương đương', 'so với', 'dẫn đến', 'hoạt động cùng lúc').\n"
        "3. Bắt buộc giữ nguyên số thứ tự [id] của từng câu ở đầu dòng để hệ thống tự động ghép phụ đề.\n\n"
        "Định dạng trả lời mẫu:\n"
        "[1] Nội dung câu dịch 1\n"
        "[2] Nội dung câu dịch 2\n"
        "...\n\n"
        "Danh sách các câu tiếng Trung cần dịch:\n"
        f"{chinese_block}"
    )

    prompt_file = job.workspace / "manual_translate_prompt.txt"
    prompt_file.write_text(prompt_text, encoding="utf-8")

    resp_file = job.workspace / "manual_translate_response.json"
    if resp_file.exists():
        try:
            resp_file.unlink()
        except Exception:
            pass

    emit_event(
        stage_name,
        15.0,
        f"Đang chờ bạn sao chép prompt và dán kết quả dịch ({len(items)} câu)...",
        level="manual_input_required",
        data={
            "job_id": job.job_id,
            "total_items": len(items),
            "prompt_file": str(prompt_file.resolve()),
            "prompt": prompt_text,
        },
    )

    import time
    t0 = time.time()
    while not resp_file.exists():
        time.sleep(0.5)
        if time.time() - t0 > 3600:
            raise DubError(
                code="MANUAL_TIMEOUT",
                user_message_vi="Đã hết thời gian chờ dán kết quả dịch thủ công (1 giờ).",
                hint_vi="Hãy bấm '1. Tạo phụ đề' khi bạn đã có sẵn câu trả lời dịch của AI.",
            )

    resp_data = {}
    try:
        resp_data = json.loads(resp_file.read_text(encoding="utf-8"))
    except Exception:
        pass

    if resp_data.get("cancelled"):
        raise DubError(
            code="USER_CANCELLED",
            user_message_vi="Bạn đã hủy thao tác dịch thủ công.",
            hint_vi="Bạn có thể chuyển sang chế độ Gemini Web tự động trong mục Cài đặt.",
        )

    raw_text = resp_data.get("text", "")
    items = parse_manual_translation_text(raw_text, items)
    from dubstudio.llm.gemini import clean_dangling_conjunctions
    items = clean_dangling_conjunctions(items)
    on_batch_done(items)
    return items


def run(job: JobContext, cfg: AppConfig) -> None:
    stage_name = "translate"
    emit_event(stage_name, 0.0, "Bắt đầu dịch phụ đề tiếng Trung sang tiếng Việt")

    # If units.json exists, translate units; otherwise fallback to segments.json
    units_file = job.workspace / "units.json"
    using_units = units_file.exists()
    target_file = units_file if using_units else (job.workspace / "segments.json")
    segments_file = job.workspace / "segments.json"

    if not target_file.exists():
        emit_event(stage_name, 0.0, f"Không tìm thấy tệp dữ liệu phân đoạn: {target_file.name}", level="error")
        return

    with open(target_file, "r", encoding="utf-8") as f:
        file_content = json.load(f)

    items = file_content if using_units else file_content.get("segments", [])

    # Load translation style if configured
    style = getattr(cfg.translation, "style", "Tự nhiên, đời thường")
    job_conf = job.workspace / "job_config.json"
    if job_conf.exists():
        try:
            jdata = json.loads(job_conf.read_text(encoding="utf-8"))
            if jdata.get("style"):
                style = jdata["style"]
        except Exception:
            pass

    from dubstudio.llm.gemini import GeminiTranslator, clean_dangling_conjunctions

    # Check if translation style has changed compared to saved segments
    saved_style = file_content.get("translation_style") if isinstance(file_content, dict) else None
    style_changed = bool(saved_style and saved_style != style)

    if style_changed:
        emit_event(stage_name, 5.0, f"Phát hiện thay đổi văn phong từ '{saved_style}' sang '{style}'. Đang dịch lại...")
        for s in items:
            s["vi_text"] = ""
            s["tts_text"] = ""
            s["tts_file"] = None
            s["tts_dur"] = None
            s["tts_hash"] = None
        already_done = False
    else:
        already_done = len(items) > 0 and all(bool(s.get("vi_text") and str(s.get("vi_text")).strip()) for s in items)

    import hashlib
    base_hash = compute_file_hash(target_file)
    input_hash = f"{base_hash}_{hashlib.md5(style.encode('utf-8')).hexdigest()[:8]}"

    if already_done and not style_changed and job.is_stage_done(stage_name, input_hash):
        items = clean_dangling_conjunctions(items)
        if using_units:
            with open(units_file, "w", encoding="utf-8") as uf:
                json.dump(items, uf, ensure_ascii=False, indent=2)
            if segments_file.exists():
                with open(segments_file, "r", encoding="utf-8") as sf:
                    seg_data = json.load(sf)
                seg_data["segments"] = items
                seg_data["translation_style"] = style
                with open(segments_file, "w", encoding="utf-8") as sf:
                    json.dump(seg_data, sf, ensure_ascii=False, indent=2)
        else:
            file_content["segments"] = items
            file_content["translation_style"] = style
            with open(target_file, "w", encoding="utf-8") as tf:
                json.dump(file_content, tf, ensure_ascii=False, indent=2)

        emit_event(stage_name, 100.0, f"Toàn bộ {len(items)} câu đã được dịch hoàn tất với văn phong '{style}' (bỏ qua)")
        outputs = ["units.json", "segments.json"] if using_units else ["segments.json"]
        job.finish_stage(stage_name, outputs)
        return

    job.start_stage(stage_name, input_hash)

    # Check translation provider preference (job_config or global config)
    trans_provider = getattr(cfg.translation, "provider", "gemini_web")
    if job_conf.exists():
        try:
            jdata = json.loads(job_conf.read_text(encoding="utf-8"))
            if jdata.get("translation_provider"):
                trans_provider = jdata["translation_provider"]
        except Exception:
            pass

    # Load analysis.json if present
    analysis_file = job.workspace / "analysis.json"
    analysis_data = {}
    if analysis_file.exists():
        try:
            analysis_data = json.loads(analysis_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    def _persist_disk(current_items):
        """Immediately save translated items to disk so partial progress is never lost."""
        if using_units:
            with open(units_file, "w", encoding="utf-8") as uf:
                json.dump(current_items, uf, ensure_ascii=False, indent=2)

            if segments_file.exists():
                with open(segments_file, "r", encoding="utf-8") as sf:
                    seg_data = json.load(sf)
                seg_data["segments"] = current_items
                seg_data["translation_style"] = style
                with open(segments_file, "w", encoding="utf-8") as sf:
                    json.dump(seg_data, sf, ensure_ascii=False, indent=2)
        else:
            file_content["segments"] = current_items
            with open(target_file, "w", encoding="utf-8") as tf:
                json.dump(file_content, tf, ensure_ascii=False, indent=2)

    if trans_provider == "manual":
        translated_items = run_manual_translation(
            job=job,
            items=items,
            style=style,
            using_units=using_units,
            stage_name=stage_name,
            on_batch_done=_persist_disk,
        )
    else:
        translator = GeminiTranslator(cfg=cfg, cache_dir=cfg.general.workspace_dir / ".cache" / "llm")
        translated_items = translator.translate_segments(
            items,
            stage_name=stage_name,
            style=style,
            context=analysis_data,
            on_batch_done=_persist_disk,
        )

        # Style lint check & single-request repair
        translated_items = run_style_lint_and_repair(
            translated_items,
            translator=translator,
            context=analysis_data,
            style=style,
            stage_name=stage_name,
        )

    from dubstudio.text.spoken_cleaner import clean_segments_spoken
    translated_items = clean_segments_spoken(translated_items)
    translated_items = clean_dangling_conjunctions(translated_items)
    from dubstudio.subtitles.sentence_align import realign_sentences_for_voice
    translated_items = realign_sentences_for_voice(translated_items)
    translated_items = clean_segments_spoken(translated_items)

    # Auto-split translated sentences into cues according to target_n (job_config or video aspect ratio)
    target_n = 6
    conf_file = job.workspace / "job_config.json"
    conf_data = {}
    if conf_file.exists():
        try:
            conf_data = json.loads(conf_file.read_text(encoding="utf-8"))
            if conf_data.get("words_per_line"):
                target_n = int(conf_data["words_per_line"])
        except Exception:
            pass

    probe_file = job.workspace / "probe.json"
    if probe_file.exists() and "words_per_line" not in conf_data:
        try:
            p_data = json.loads(probe_file.read_text(encoding="utf-8"))
            w = p_data.get("video", {}).get("width", 1920)
            h = p_data.get("video", {}).get("height", 1080)
            if h > w:  # 9:16 vertical
                target_n = 5
            elif abs(w - h) < 50:  # 1:1 square
                target_n = 6
            else:  # 16:9 widescreen
                target_n = 9
        except Exception:
            pass

    from dubstudio.subtitles.cue_split import auto_split_all_units
    translated_items = auto_split_all_units(translated_items, target_n=target_n, analysis=analysis_data)
    _persist_disk(translated_items)

    if using_units and segments_file.exists():
        with open(segments_file, "r", encoding="utf-8") as sf:
            seg_data = json.load(sf)
        seg_data["segments"] = translated_items
        seg_data["translation_style"] = style
        with open(segments_file, "w", encoding="utf-8") as sf:
            json.dump(seg_data, sf, ensure_ascii=False, indent=2)

    outputs = ["units.json", "segments.json"] if using_units else ["segments.json"]
    job.finish_stage(stage_name, outputs)
    emit_event(stage_name, 100.0, f"Đã dịch thành công và tối ưu độ dài cho toàn bộ {len(translated_items)} câu thoại")


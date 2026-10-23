"""Stage: units. Groups adjacent ASR segments into dubbing units and computes character budgets."""
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from dubstudio.config import AppConfig
from dubstudio.events import emit_event
from dubstudio.jobstate import JobContext, compute_file_hash

# Default voice chars-per-second benchmarks from Phase 2 / DECISIONS.md
VOICE_CPS_MAP = {
    "Quỳnh Anh": 17.0,
    "Mai Anh": 17.4,
    "Minh Đức": 15.7,
    "Hải Đăng": 20.4,
    "Minh Quân": 20.4,
}

TERMINAL_PUNCT = set("。？！…?!.")
CLAUSE_PUNCT = set("，、；,;")

ZH_DANGLING_CONNECTIVES = (
    "相当于", "类似于", "等于", "如同", "正如", "比如", "例如", "包括", "属于", "位于",
    "由于", "为了", "根据", "按照", "关于", "对于", "把", "被", "将", "让", "叫", "使",
    "从", "向", "往", "朝", "和", "跟", "同", "与", "及", "以及", "虽然", "但是", "如果", "因为", "所以"
)


def _ends_with_zh_connective(text: str) -> bool:
    t = (text or "").rstrip(" ,，。.!！?？;；:：…-— ")
    return any(t.endswith(w) for w in ZH_DANGLING_CONNECTIVES)


def _is_terminal(text: str) -> bool:
    t = (text or "").rstrip()
    return bool(t and t[-1] in TERMINAL_PUNCT)


def _is_clause(text: str) -> bool:
    t = (text or "").rstrip()
    return bool(t and t[-1] in CLAUSE_PUNCT)


def _join_zh_parts(parts: List[Dict[str, Any]]) -> str:
    texts = [p.get("src_text") or p.get("zh") or p.get("text") or "" for p in parts]
    cleaned = [t.strip() for t in texts if t.strip()]
    return "".join(cleaned)


def _split_into_clauses(parts: List[Dict[str, Any]], full_zh: str, start: float, end: float) -> List[Dict[str, Any]]:
    """
    Split a long sentence (>15s or >80 Chinese chars) into clauses at the largest pause
    or clause punctuation, returning list of clauses with start, end, and zh.
    """
    if len(parts) > 1:
        scored_boundaries = []
        for idx in range(len(parts) - 1):
            p_curr = parts[idx]
            p_next = parts[idx + 1]
            gap = max(0.0, p_next["start"] - p_curr["end"])
            txt = (p_curr.get("src_text") or "").rstrip()
            punct_bonus = 2.0 if txt and txt[-1] in CLAUSE_PUNCT else 0.0
            score = gap + punct_bonus
            scored_boundaries.append((score, idx))

        scored_boundaries.sort(key=lambda x: x[0], reverse=True)
        num_clauses = max(2, int(round((end - start) / 8.0)))
        cuts = sorted([idx for _, idx in scored_boundaries[:num_clauses - 1]])

        clauses = []
        c_st_idx = 0
        for cut_idx in cuts:
            sub_parts = parts[c_st_idx:cut_idx + 1]
            if sub_parts:
                clauses.append({
                    "start": sub_parts[0]["start"],
                    "end": sub_parts[-1]["end"],
                    "zh": _join_zh_parts(sub_parts),
                })
            c_st_idx = cut_idx + 1

        sub_parts = parts[c_st_idx:]
        if sub_parts:
            clauses.append({
                "start": sub_parts[0]["start"],
                "end": sub_parts[-1]["end"],
                "zh": _join_zh_parts(sub_parts),
            })

        if len(clauses) > 1:
            return clauses

    # Look for words timestamps
    words = []
    for p in parts:
        if p.get("words"):
            words.extend(p["words"])

    if words and len(words) > 4:
        word_gaps = []
        for w_idx in range(len(words) - 1):
            w_curr = words[w_idx]
            w_next = words[w_idx + 1]
            gap = max(0.0, w_next.get("start", 0) - w_curr.get("end", 0))
            w_txt = (w_curr.get("word") or "").strip()
            punct_bonus = 1.0 if w_txt and w_txt[-1] in CLAUSE_PUNCT else 0.0
            word_gaps.append((gap + punct_bonus, w_idx))

        word_gaps.sort(key=lambda x: x[0], reverse=True)
        num_cuts = max(1, int(round((end - start) / 8.0)) - 1)
        top_cuts = sorted([idx for _, idx in word_gaps[:num_cuts]])

        clauses = []
        cur_w = 0
        for cut in top_cuts:
            w_sub = words[cur_w:cut + 1]
            if w_sub:
                c_zh = "".join(w.get("word", "") for w in w_sub)
                clauses.append({
                    "start": w_sub[0].get("start", start),
                    "end": w_sub[-1].get("end", end),
                    "zh": c_zh,
                })
            cur_w = cut + 1
        w_sub = words[cur_w:]
        if w_sub:
            clauses.append({
                "start": w_sub[0].get("start", start),
                "end": w_sub[-1].get("end", end),
                "zh": "".join(w.get("word", "") for w in w_sub),
            })
        if len(clauses) > 1:
            return clauses

    punct_matches = list(re.finditer(r'([，、；,;])', full_zh))
    if punct_matches:
        mid_char = len(full_zh) // 2
        best_p = min(punct_matches, key=lambda m: abs(m.end() - mid_char))
        split_idx = best_p.end()
        zh1 = full_zh[:split_idx].strip()
        zh2 = full_zh[split_idx:].strip()
        ratio = len(zh1) / max(1, len(full_zh))
        mid_t = round(start + (end - start) * ratio, 3)
        return [
            {"start": start, "end": mid_t, "zh": zh1},
            {"start": mid_t, "end": end, "zh": zh2},
        ]

    mid_t = round((start + end) / 2.0, 3)
    half_c = len(full_zh) // 2
    return [
        {"start": start, "end": mid_t, "zh": full_zh[:half_c]},
        {"start": mid_t, "end": end, "zh": full_zh[half_c:]},
    ]


def _make_sentence(parts: List[Dict[str, Any]]) -> Dict[str, Any]:
    st = parts[0]["start"]
    en = parts[-1]["end"]
    dur = round(en - st, 3)
    speech_time = round(sum(p.get("speech_time") or (p["end"] - p["start"]) for p in parts), 3)

    zh_text = _join_zh_parts(parts)
    part_ids = [p["id"] for p in parts]
    speaker = parts[0].get("speaker")
    gender = parts[0].get("gender", "unknown")
    voice = parts[0].get("voice")

    sent = {
        "start": st,
        "end": en,
        "dur": dur,
        "speech_time": speech_time,
        "parts": part_ids,
        "raw_parts": parts,
        "speaker": speaker,
        "gender": gender,
        "voice": voice,
        "zh": zh_text,
        "src_text": zh_text,
        "clauses": None,
    }

    zh_chars = len([c for c in zh_text if not c.isspace()])
    if dur > 15.0 or zh_chars > 80:
        clauses = _split_into_clauses(parts, zh_text, st, en)
        if clauses and len(clauses) > 1:
            sent["clauses"] = clauses

    return sent


def extract_complete_sentences(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Groups raw ASR segments into natural, grammatically complete sentences:
    - Boundary: after 。？！… or gap >= 0.8s or speaker change.
    - Hard duration cap: a sentence never exceeds 7.0-8.0s, preventing entire-video merging.
    - If accumulated duration reaches >= 4.0s and there is a clause punctuation (，、；) or gap >= 0.4s, end sentence.
    """
    if not segments:
        return []

    sentences: List[Dict[str, Any]] = []
    current_parts: List[Dict[str, Any]] = []

    for i, seg in enumerate(segments):
        current_parts.append(seg)
        next_seg = segments[i + 1] if i + 1 < len(segments) else None

        if not next_seg:
            sentences.append(_make_sentence(current_parts))
            current_parts = []
            break

        gap = max(0.0, next_seg["start"] - seg["end"])
        same_speaker = (seg.get("speaker") == next_seg.get("speaker"))
        curr_text = seg.get("src_text") or seg.get("zh") or seg.get("text") or ""
        accum_dur = seg["end"] - current_parts[0]["start"]
        next_total_dur = next_seg["end"] - current_parts[0]["start"]

        has_terminal = _is_terminal(curr_text)
        has_clause = _is_clause(curr_text)
        is_dangling_zh = _ends_with_zh_connective(curr_text)

        end_sentence = False
        if has_terminal and not is_dangling_zh:
            end_sentence = True
        elif not same_speaker:
            end_sentence = True
        elif accum_dur >= 7.0 or next_total_dur > 8.0:
            # Enforce hard duration cap so sentences align with natural video pacing
            if not is_dangling_zh or next_total_dur > 11.0:
                end_sentence = True
        elif is_dangling_zh and same_speaker and next_total_dur <= 10.0:
            # Dangling preposition/connective (e.g. 相当于, 类似于): MUST not split before object!
            end_sentence = False
        elif has_clause:
            end_sentence = (gap > 1.2 or accum_dur >= 4.5)
        elif gap >= 0.8:
            end_sentence = True
        elif accum_dur >= 3.5 and gap >= 0.35:
            end_sentence = True
        elif gap > 1.2:
            end_sentence = True

        if end_sentence:
            sentences.append(_make_sentence(current_parts))
            current_parts = []

    if current_parts:
        sentences.append(_make_sentence(current_parts))

    return sentences


def build_dubbing_units(segments: List[Dict[str, Any]], default_cps: float = 17.0) -> List[Dict[str, Any]]:
    """
    Build dubbing units from ASR segments:
    - Unit = 1 complete sentence, OR multiple consecutive complete sentences
      (combined total duration <= 10.0s; if a sentence is >10.0s, unit contains only that sentence).
    - Translation block boundaries are strictly between units.
    - TTS reads whole unit at once.
    """
    if not segments:
        return []

    sentences = extract_complete_sentences(segments)
    units: List[Dict[str, Any]] = []
    current_sents: List[Dict[str, Any]] = []

    def flush_unit(sents: List[Dict[str, Any]], next_sent: Optional[Dict[str, Any]] = None):
        if not sents:
            return

        u_id = len(units) + 1
        st = sents[0]["start"]
        en = sents[-1]["end"]
        part_ids = []
        for s in sents:
            part_ids.extend(s["parts"])

        speaker = sents[0].get("speaker")
        gender = sents[0].get("gender", "unknown")
        voice = sents[0].get("voice")
        speech_time = round(sum(s["speech_time"] for s in sents), 3)

        internal_gaps = 0.0
        for i in range(len(sents) - 1):
            gap = max(0.0, sents[i + 1]["start"] - sents[i]["end"])
            internal_gaps += gap

        if next_sent:
            silence_after = max(0.0, next_sent["start"] - en)
        else:
            silence_after = 0.5

        borrow_after = min(max(0.0, silence_after - 0.15), 0.4)
        base_dur = min(en - st, speech_time + 0.5 * internal_gaps)
        dur = round(base_dur + borrow_after, 3)

        min_chars = int(round(0.9 * dur * default_cps))
        target_chars = int(round(dur * default_cps))
        max_chars = int(round(1.15 * dur * default_cps))

        zh_text = " ".join(s["zh"] for s in sents)

        all_clauses = []
        for s in sents:
            if s.get("clauses"):
                all_clauses.extend(s["clauses"])

        unit = {
            "id": u_id,
            "start": st,
            "end": en,
            "parts": part_ids,
            "speaker": speaker,
            "gender": gender,
            "voice": voice,
            "speech_time": speech_time,
            "dur": dur,
            "min_chars": min_chars,
            "target_chars": target_chars,
            "max_chars": max_chars,
            "zh": zh_text,
            "src_text": zh_text,
            "vi_text": "",
            "tts_text": "",
            "clauses": all_clauses if all_clauses else None,
            "uncertain": False,
            "length_note": "ok",
            "flags": [],
        }
        units.append(unit)

    for i, sent in enumerate(sentences):
        if not current_sents:
            current_sents.append(sent)
            continue

        prev_sent = current_sents[-1]
        gap = max(0.0, sent["start"] - prev_sent["end"])
        same_speaker = (sent.get("speaker") == prev_sent.get("speaker"))
        combined_dur = sent["end"] - current_sents[0]["start"]
        prev_dur = prev_sent["end"] - prev_sent["start"]
        curr_dur = sent["end"] - sent["start"]
        # Only merge if one of the fragments is very short and gap is small, total <= 7.0s
        can_merge = (gap <= 0.4 and same_speaker and combined_dur <= 7.0 and (prev_dur < 3.0 or curr_dur < 3.0))

        if can_merge:
            current_sents.append(sent)
        else:
            flush_unit(current_sents, next_sent=sent)
            current_sents = [sent]

    if current_sents:
        flush_unit(current_sents, next_sent=None)

    return units


def run(job: JobContext, cfg: AppConfig) -> None:
    stage_name = "units"
    emit_event(stage_name, 0.0, "Bắt đầu tạo đơn vị lồng tiếng (dubbing units)")

    segments_file = job.workspace / "segments.json"
    input_hash = compute_file_hash(segments_file)

    units_file = job.workspace / "units.json"
    if job.is_stage_done(stage_name, input_hash) or (units_file.exists() and units_file.stat().st_size > 50):
        emit_event(stage_name, 100.0, "Giai đoạn units đã hoàn thành (bỏ qua)")
        job.finish_stage(stage_name, ["units.json", "segments.json"])
        return

    job.start_stage(stage_name, input_hash)

    with open(segments_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    segments = data.get("segments", [])
    default_voice = cfg.tts.default_female_voice
    cps = VOICE_CPS_MAP.get(default_voice, 17.0)

    raw_file = job.workspace / "raw_segments.json"
    if not raw_file.exists():
        with open(raw_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    units = build_dubbing_units(segments, default_cps=cps)

    units_file = job.workspace / "units.json"
    with open(units_file, "w", encoding="utf-8") as f:
        json.dump(units, f, ensure_ascii=False, indent=2)

    consolidated_segments = []
    for u in units:
        consolidated_segments.append({
            "id": u["id"],
            "start": u["start"],
            "end": u["end"],
            "src_text": u["src_text"],
            "zh": u["zh"],
            "speech_time": u["speech_time"],
            "dur": u["dur"],
            "min_chars": u["min_chars"],
            "target_chars": u["target_chars"],
            "max_chars": u["max_chars"],
            "parts": u["parts"],
            "clauses": u.get("clauses"),
            "vi_text": "",
            "tts_text": "",
            "speaker": u.get("speaker"),
            "gender": u.get("gender", "unknown"),
            "voice": u.get("voice"),
            "tts_file": None,
            "tts_dur": None,
            "fit": None,
            "flags": [],
        })

    data["segments"] = consolidated_segments
    with open(segments_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    emit_event(stage_name, 100.0, f"Đã xây dựng {len(units)} đơn vị lồng tiếng từ {len(segments)} segment")
    job.finish_stage(stage_name, ["units.json", "segments.json"])

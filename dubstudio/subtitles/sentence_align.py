"""Sentence alignment and restructuring module for dubstudio.

Ensures voice track units consist of complete, natural grammatical sentences
without chopping phrases mid-sentence (e.g. '...Hôm nay mình sẽ' | 'dẫn các bạn...').
"""
import re
from typing import Any, Dict, List
from dubstudio.text.spoken_cleaner import sanitize_spoken_vietnamese, clean_segments_spoken

# Terminal punctuation matching Vietnamese & Chinese sentence endings
TERMINAL_PUNCT_RE = re.compile(r'([.?!…])(\s+|$)')


def stitch_dangling_clauses(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Detect trailing incomplete phrases at the end of segment i that belong to the
    beginning of segment i+1 (e.g., segment i ends with '...đảo lộn nhận thức. Hôm nay mình sẽ',
    and segment i+1 starts with 'dẫn các bạn khám phá...').
    
    Moves the trailing phrase to segment i+1 and shifts the timestamp boundary proportionally.
    """
    if len(segments) < 2:
        return segments

    for i in range(len(segments) - 1):
        s_curr = segments[i]
        s_next = segments[i + 1]

        vi_curr = (s_curr.get("vi_text") or s_curr.get("tts_text") or "").strip()
        vi_next = (s_next.get("vi_text") or s_next.get("tts_text") or "").strip()
        if not vi_curr or not vi_next:
            continue

        # Find all terminal punctuation positions in vi_curr
        matches = list(TERMINAL_PUNCT_RE.finditer(vi_curr))
        if not matches:
            continue

        last_match = matches[-1]
        last_punct_end = last_match.end()

        # Check if there is trailing text after the last sentence terminator
        trailing_fragment = vi_curr[last_punct_end:].strip()
        if not trailing_fragment:
            # Check if vi_curr ended with a dangling comparative word right before the period (e.g. "...tương đương.")
            # and vi_next starts with "Với..." or "Như..." -> stitch comparator to next sentence
            dang_match = re.search(r'([,;\s]+)?(tương đương|tương tự|so sánh|so)\s*[.!?:;…]*$', vi_curr, re.IGNORECASE)
            if dang_match and re.match(r'^(với|như|là)\b', vi_next, re.IGNORECASE):
                dang_word = dang_match.group(2)
                s_curr["vi_text"] = vi_curr[:dang_match.start()].rstrip(' ,;') + '.'
                s_curr["tts_text"] = s_curr["vi_text"]
                s_next["vi_text"] = f"{dang_word.capitalize()} {vi_next[0].lower() + vi_next[1:]}"
                s_next["tts_text"] = s_next["vi_text"]
            continue

        # If the trailing fragment does not have its own sentence terminator, it's a dangling clause
        frag_matches = list(TERMINAL_PUNCT_RE.finditer(trailing_fragment))
        if not frag_matches:
            # Trailing fragment is an incomplete clause (e.g. 'Hôm nay mình sẽ', 'Chúng ta hãy')
            main_sentence = vi_curr[:last_punct_end].strip()

            words_main = len(main_sentence.split())
            words_frag = len(trailing_fragment.split())

            if words_main > 0 and words_frag > 0:
                # Proportional timestamp boundary adjustment
                st = float(s_curr.get("start", 0.0))
                en = float(s_curr.get("end", st + 1.0))
                dur = max(0.5, en - st)
                shift_ratio = words_frag / (words_main + words_frag)
                shift_time = round(dur * shift_ratio, 3)
                # Keep safety margin of at least 1.0s for current segment
                shift_time = min(shift_time, max(0.0, dur - 1.0))

                s_curr["end"] = round(en - shift_time, 3)
                s_curr["dur"] = round(s_curr["end"] - st, 3)

                # Prepend trailing fragment to next segment
                # If next segment started with lowercase or continuation, stitch smoothly
                clean_frag = trailing_fragment
                if clean_frag and clean_frag[0].islower():
                    clean_frag = clean_frag[0].upper() + clean_frag[1:]

                new_next_vi = sanitize_spoken_vietnamese(f"{clean_frag} {vi_next}")
                s_next["vi_text"] = new_next_vi
                s_next["tts_text"] = new_next_vi

                # Adjust next segment start time
                next_st = float(s_next.get("start", en))
                s_next["start"] = round(max(s_curr["end"], next_st - shift_time), 3)
                s_next["dur"] = round(float(s_next.get("end", s_next["start"] + 1.0)) - s_next["start"], 3)

                sanitized_main = sanitize_spoken_vietnamese(main_sentence)
                s_curr["vi_text"] = sanitized_main
                s_curr["tts_text"] = sanitized_main

    return segments


def split_chinese_correspondingly(
    zh_text: str,
    durations: List[float],
) -> List[str]:
    """
    Split Chinese text into len(durations) parts corresponding to split Vietnamese sentences.
    Preserves Chinese sentence/clause boundaries and avoids repeating identical Chinese text.
    """
    if not zh_text or len(durations) <= 1:
        return [zh_text] if zh_text else [""] * len(durations)

    num_parts = len(durations)
    total_dur = sum(durations) or 1.0

    # First check if zh_text naturally splits into exactly num_parts by terminal punctuation
    term_matches = list(re.finditer(r'([。？！…?!]+)(\s+|$)', zh_text))
    if len(term_matches) in (num_parts - 1, num_parts):
        parts = []
        cur = 0
        for m in term_matches[:num_parts - 1]:
            parts.append(zh_text[cur:m.end()].strip())
            cur = m.end()
        parts.append(zh_text[cur:].strip())
        if len(parts) == num_parts and all(parts):
            return parts

    # Otherwise, split proportionally based on durations, snapping cuts to nearest punctuation
    all_punct = []
    for m in re.finditer(r'([。？！…?!.,;，、；\s])', zh_text):
        all_punct.append((m.end(), 2.0 if m.group() in "。？！…?!." else 1.0))

    cuts = []
    accum_dur = 0.0
    zh_len = len(zh_text)
    cur_idx = 0
    for d in durations[:-1]:
        accum_dur += d
        target_char = int(round(zh_len * (accum_dur / total_dur)))
        best_cut = None
        best_score = float("inf")
        margin = max(3, int(zh_len * 0.35))
        for p_idx, weight in all_punct:
            if cur_idx < p_idx < zh_len:
                dist = abs(p_idx - target_char)
                if dist <= margin:
                    score = dist / weight
                    if score < best_score:
                        best_score = score
                        best_cut = p_idx
        if best_cut is None or best_cut <= cur_idx or best_cut >= zh_len:
            best_cut = max(cur_idx + 1, min(zh_len - 1, target_char))
        cuts.append(best_cut)
        cur_idx = best_cut

    result = []
    prev_c = 0
    for c in cuts:
        result.append(zh_text[prev_c:c].strip())
        prev_c = c
    result.append(zh_text[prev_c:].strip())

    if len(result) == num_parts:
        return result
    return [zh_text] + [""] * (num_parts - 1)


def split_multi_sentence_segments(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Split segments that contain multiple complete sentences into separate individual
    segments for the voice track, so each sentence is read naturally as its own dubbing unit.
    Also splits Chinese source text correspondingly so Chinese subtitles never duplicate.
    """
    result: List[Dict[str, Any]] = []

    for seg in segments:
        vi_text = (seg.get("vi_text") or seg.get("tts_text") or "").strip()
        st = float(seg.get("start", 0.0))
        en = float(seg.get("end", st + 1.0))
        dur = max(0.2, en - st)

        # Split into distinct sentences by terminal punctuation (. ? ! …)
        raw_sentences = []
        cur_start = 0
        for m in re.finditer(r'([.?!…])(\s+|$)', vi_text):
            end_pos = m.end()
            cand = vi_text[cur_start:end_pos].strip()
            if cand:
                raw_sentences.append(cand)
                cur_start = end_pos

        rem = vi_text[cur_start:].strip()
        if rem:
            raw_sentences.append(rem)

        # Split whenever we have 2 or more complete sentences/utterances
        if len(raw_sentences) >= 2:
            total_chars = sum(len(s.replace(" ", "")) for s in raw_sentences)
            if total_chars <= 0:
                total_chars = max(1, len(vi_text))

            # Compute proportional durations
            part_durs = []
            for sent_text in raw_sentences:
                sent_chars = len(sent_text.replace(" ", ""))
                part_durs.append(dur * (sent_chars / total_chars))

            orig_zh = str(seg.get("src_text") or seg.get("zh") or "").strip()
            zh_parts = split_chinese_correspondingly(orig_zh, part_durs)

            running_st = st
            for s_idx, sent_text in enumerate(raw_sentences):
                sent_chars = len(sent_text.replace(" ", ""))
                if s_idx == len(raw_sentences) - 1:
                    sent_en = en
                else:
                    sent_dur = round(dur * (sent_chars / total_chars), 3)
                    sent_en = round(min(en - 0.2, running_st + max(0.4, sent_dur)), 3)

                new_seg = dict(seg)
                new_seg["start"] = round(running_st, 3)
                new_seg["end"] = round(sent_en, 3)
                new_seg["dur"] = round(sent_en - running_st, 3)
                new_seg["vi_text"] = sent_text
                new_seg["tts_text"] = sent_text
                zh_val = zh_parts[s_idx] if s_idx < len(zh_parts) and zh_parts[s_idx] else orig_zh
                new_seg["src_text"] = zh_val
                new_seg["zh"] = zh_val
                new_seg["tts_file"] = None
                new_seg["tts_dur"] = None
                new_seg["tts_hash"] = None
                new_seg["fit"] = None
                new_seg["cues"] = None
                new_seg["sub_slices"] = None
                result.append(new_seg)
                running_st = sent_en
        else:
            result.append(seg)

    # Re-index IDs sequentially
    for idx, item in enumerate(result, start=1):
        item["id"] = idx

    return result


def realign_sentences_for_voice(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Comprehensive sentence restructuring pipeline for dubbing:
    1. Stitch dangling clauses from previous segments.
    2. Split multi-sentence lumps into clean, complete sentences.
    3. Sanitize and humanize spoken text.
    """
    if not segments:
        return []
    stitched = stitch_dangling_clauses(segments)
    refined = split_multi_sentence_segments(stitched)
    return clean_segments_spoken(refined)

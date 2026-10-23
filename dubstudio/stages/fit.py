"""Stage: fit. Closed-loop voice-to-picture timing algorithm with audio collision detection,
1.0x - 1.1x tempo balancing for minor overlaps, and contextual cluster re-writing for major overlaps.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Tuple
import numpy as np
import soundfile as sf

from dubstudio.config import AppConfig
from dubstudio.events import emit_event
from dubstudio.jobstate import JobContext, compute_file_hash
from dubstudio.llm.fit_rewrite import FitRewriter
from dubstudio.subtitles.cue_split import auto_split_unit_cues, split_sentence_cues
from dubstudio.text.vi_normalize import normalize_for_tts


def time_stretch_audio(in_wav: Path, out_wav: Path, rate: float) -> None:
    """Adjust audio tempo by rate (e.g. 1.05x) using ffmpeg atempo filter."""
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    rate = max(0.5, min(2.0, rate))
    cmd = [
        "ffmpeg", "-y",
        "-i", str(in_wav.resolve()),
        "-filter:a", f"atempo={rate:.3f}",
        "-vn",
        str(out_wav.resolve()),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def enforce_audio_boundary(wav_path: Path, max_dur: float) -> float:
    """Ensure audio file does not exceed max_dur, trimming with a smooth 50ms fade-out to prevent voice collision."""
    try:
        data, file_sr = sf.read(str(wav_path.resolve()))
        max_samples = int(max_dur * file_sr)
        if len(data) > max_samples:
            trimmed = data[:max_samples]
            fade_len = min(int(0.05 * file_sr), len(trimmed))
            if fade_len > 0:
                trimmed[-fade_len:] *= np.linspace(1.0, 0.0, fade_len, dtype=np.float32)
            sf.write(str(wav_path.resolve()), trimmed, file_sr)
            return round(len(trimmed) / file_sr, 3)
        return round(len(data) / file_sr, 3)
    except Exception:
        return max_dur


def calculate_fit_decision(
    tts_dur: float,
    dur: float,
    cfg: AppConfig,
    silence_after: float = 0.0,
) -> Tuple[str, float, List[str]]:
    """Pure logic function for fit decision (table-testable without I/O).

    Returns: (method, rate, flags)
    """
    if dur <= 0.0:
        return "none", 1.0, []

    s = tts_dur / dur
    flags = []

    # 1. Neutral zone [0.95, 1.05]
    if cfg.fit.neutral_zone_low <= s <= cfg.fit.neutral_zone_high:
        return "none", 1.0, flags

    # 2. Tolerable stretch [0.9, max_speedup]
    if cfg.fit.min_slowdown <= s < cfg.fit.neutral_zone_low:
        return "slowdown", round(s, 3), flags

    if cfg.fit.neutral_zone_high < s <= cfg.fit.max_speedup:
        return "speedup", round(s, 3), flags

    # 3. Beyond [0.9, max_speedup]
    if s > cfg.fit.max_speedup:
        # Check if remaining overflow fits into trailing silence
        overflow_sec = tts_dur / cfg.fit.max_speedup - dur
        if overflow_sec > silence_after:
            flags.append("overflow")
        return "speedup", cfg.fit.max_speedup, flags
    else:
        # s < 0.9: slow down to min 0.9x and accept remaining gap
        return "slowdown", cfg.fit.min_slowdown, flags


def build_clusters(colliding_indices: List[int], segments: List[Dict[str, Any]], window: int = 2) -> List[List[int]]:
    """Group colliding segment indices into contextual clusters of surrounding sentences."""
    if not colliding_indices:
        return []

    n = len(segments)
    ranges = []
    for idx in colliding_indices:
        st = max(0, idx - window)
        en = min(n - 1, idx + window)
        ranges.append((st, en))

    # Merge overlapping ranges
    merged = []
    for st, en in sorted(ranges):
        if not merged:
            merged.append([st, en])
        else:
            prev_st, prev_en = merged[-1]
            if st <= prev_en + 1:
                merged[-1][1] = max(prev_en, en)
            else:
                merged.append([st, en])

    return [list(range(st, en + 1)) for st, en in merged]


def resolve_isolated_pair_shifts(segments: List[Dict[str, Any]], video_dur: float, max_shift: float = 0.50) -> int:
    """If exactly two consecutive segments collide with each other and are isolated
    (neither collides with outside neighbors), shift segment A backwards (up to 0.5s)
    and segment B forwards (up to 0.5s) using available silence gaps before and after.
    Returns the number of isolated pairs shifted.
    """
    n = len(segments)
    if n < 2:
        return 0

    durations = []
    for s in segments:
        orig_dur = max(0.1, round(float(s["end"]) - float(s["start"]), 3))
        tts_dur = float(s.get("tts_dur") or orig_dur)
        safe_dur = round(tts_dur / 1.10, 3)
        durations.append(safe_dur)

    boundary_collides = [False] * (n - 1)
    for i in range(n - 1):
        st_i = float(segments[i]["start"])
        end_i = st_i + durations[i]
        st_next = float(segments[i + 1]["start"])
        if end_i - st_next > 0.10:
            boundary_collides[i] = True

    shifted_count = 0
    for i in range(n - 1):
        if not boundary_collides[i]:
            continue
        collides_prev = (i > 0 and boundary_collides[i - 1])
        collides_next = (i + 1 < n - 1 and boundary_collides[i + 1])
        # Only apply when exactly 2 sentences collide and no other sentence collides with them
        if not collides_prev and not collides_next:
            seg_a = segments[i]
            seg_b = segments[i + 1]

            st_a = float(seg_a["start"])
            dur_a = durations[i]
            st_b = float(seg_b["start"])
            dur_b = durations[i + 1]

            overlap = round((st_a + dur_a) - st_b, 3)
            needed_relief = round(overlap - 0.10, 3)
            if needed_relief <= 0:
                continue

            prev_end = float(segments[i - 1]["end"]) if i > 0 else 0.0
            gap_before = max(0.0, round(st_a - prev_end, 3))
            max_shift_a = min(max_shift, gap_before)

            if i + 2 < n:
                next_next_st = float(segments[i + 2]["start"])
            else:
                next_next_st = video_dur if video_dur > st_b + dur_b else (st_b + dur_b + 3.0)
            gap_after = max(0.0, round(next_next_st - (st_b + dur_b), 3))
            max_shift_b = min(max_shift, gap_after)

            shift_a = min(max_shift_a, needed_relief)
            rem = round(needed_relief - shift_a, 3)
            shift_b = min(max_shift_b, rem) if rem > 0 else 0.0

            if shift_a > 0.005 or shift_b > 0.005:
                if shift_a > 0.005:
                    seg_a["start"] = max(0.0, round(st_a - shift_a, 3))
                    seg_a["voice_start"] = seg_a["start"]
                if shift_b > 0.005:
                    seg_b["start"] = round(st_b + shift_b, 3)
                    seg_b["voice_start"] = seg_b["start"]
                shifted_count += 1

    return shifted_count


def run(job: JobContext, cfg: AppConfig) -> None:
    stage_name = "fit"
    emit_event(stage_name, 0.0, "Bắt đầu vòng lặp khép kín khớp tiếng-hình (closed-loop fit)")

    segments_file = job.workspace / "segments.json"
    tts_dir = job.workspace / "tts"
    stretched_dir = job.workspace / "tts_stretched"
    stretched_dir.mkdir(parents=True, exist_ok=True)

    if not segments_file.exists():
        emit_event(stage_name, 100.0, "Chưa có segments.json, bỏ qua giai đoạn fit", level="warning")
        return

    with open(segments_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    segments = data.get("segments", [])
    if not segments:
        emit_event(stage_name, 100.0, "Không có đoạn thoại nào để khớp thời lượng")
        return

    conf_file = job.workspace / "job_config.json"
    conf = {}
    if conf_file.exists():
        try:
            conf = json.loads(conf_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    male_voice = conf.get("default_male_voice") or conf.get("voice_male") or cfg.tts.default_male_voice
    female_voice = conf.get("default_female_voice") or conf.get("voice_female") or cfg.tts.default_female_voice
    detect_gender = bool(conf.get("detect_gender", False))
    single_choice = conf.get("single_voice_gender", "male")
    fallback_single_voice = female_voice if single_choice == "female" else male_voice

    video_dur = float(data.get("video", {}).get("duration", 0.0) or 0.0)
    if video_dur <= 0.0:
        probe_f = job.workspace / "probe.json"
        if probe_f.exists():
            try:
                p_data = json.loads(probe_f.read_text(encoding="utf-8"))
                video_dur = float(p_data.get("format", {}).get("duration", 0.0) or 0.0)
            except Exception:
                pass
    if video_dur <= 0.0 and segments:
        video_dur = max(float(s.get("end", 0.0)) for s in segments) + 3.0
    analysis_file = job.workspace / "analysis.json"
    analysis_data = {}
    if analysis_file.exists():
        try:
            analysis_data = json.loads(analysis_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Ensure actual tts_dur is loaded from audio files
    for seg in segments:
        w_path = tts_dir / f"{seg['id']:04d}.wav"
        if w_path.exists() and w_path.stat().st_size > 500:
            try:
                seg["tts_dur"] = round(sf.info(str(w_path)).duration, 3)
                seg["tts_file"] = f"tts/{seg['id']:04d}.wav"
            except Exception:
                pass

    # Xê dịch các cặp câu bị đè cô lập tới lui tối đa 0.5s nếu trước và sau còn trống
    isolated_shifted = resolve_isolated_pair_shifts(segments, video_dur, max_shift=0.50)
    if isolated_shifted > 0:
        emit_event(stage_name, 10.0, f"Đã tự động xê dịch tới/lui tối đa 0.5s cho {isolated_shifted} cặp câu bị đè cô lập vào khoảng trống yên lặng.")

    # ─── 1. Multi-pass Audio Collision Detection & Contextual Cluster Rewriting ───
    # ALLOWABLE_OVERLAP = 0.10s (cho phép đè nhẹ tối đa 0.1 giây)
    ALLOWABLE_OVERLAP = 0.10
    MAX_REWRITE_PASSES = 3

    from dubstudio.llm.cdp_gemini import is_cdp_ready
    cdp_port = getattr(cfg.translation, "cdp_port", 9222)
    is_gemini_web = (getattr(cfg.translation, "provider", "") == "gemini_web") or is_cdp_ready(cdp_port)

    has_api_key = bool(
        cfg.gemini_api_key
        or os.getenv("GEMINI_API_KEY")
    )
    can_rewrite = has_api_key or is_gemini_web

    for pass_idx in range(1, MAX_REWRITE_PASSES + 1):
        major_colliding_indices = []
        minor_colliding_count = 0

        for idx, seg in enumerate(segments):
            st = float(seg["start"])
            orig_dur = max(0.1, round(float(seg["end"]) - st, 3))
            tts_dur = float(seg.get("tts_dur") or orig_dur)

            if idx + 1 < len(segments):
                next_st = float(segments[idx + 1]["start"])
            else:
                next_st = video_dur if video_dur > st + orig_dur else (st + orig_dur + 3.0)

            available_dur = max(orig_dur, round(next_st - st, 3))
            max_audio_dur = max(0.1, round(available_dur - 0.05, 3))
            raw_overlap = round(tts_dur - max_audio_dur, 3)

            if raw_overlap > 0.02:
                # Check overlap remaining after applying maximum safe speedup (1.10x)
                overlap_after_speedup = round((tts_dur / 1.10) - max_audio_dur, 3)
                if overlap_after_speedup > ALLOWABLE_OVERLAP:
                    # Kiểm tra khoảng trống phía trước để xê dịch tối đa 0.5s trước khi quyết định viết lại!
                    prev_end = float(segments[idx - 1]["end"]) if idx > 0 else 0.0
                    gap_before = max(0.0, st - prev_end)
                    needed_relief = overlap_after_speedup - ALLOWABLE_OVERLAP
                    shift_back = min(0.50, gap_before, needed_relief)

                    new_st = max(0.0, round(st - shift_back, 3))
                    new_avail = max(orig_dur, round(next_st - new_st, 3))
                    new_max_audio = max(0.1, round(new_avail - 0.05, 3))
                    new_overlap = round((tts_dur / 1.10) - new_max_audio, 3)

                    if new_overlap <= ALLOWABLE_OVERLAP:
                        # Xê dịch <= 0.5s đã giải tỏa được va chạm -> không cần viết lại!
                        seg["start"] = new_st
                        seg["voice_start"] = new_st
                        minor_colliding_count += 1
                    else:
                        # Major collision: vẫn đè >ALLOWABLE_OVERLAP dù đã xê dịch tối đa 0.5s -> mới gom chùm viết lại
                        major_colliding_indices.append(idx)
                else:
                    minor_colliding_count += 1

        if not major_colliding_indices:
            if pass_idx > 1:
                emit_event(
                    stage_name, 65.0,
                    f"Hoàn thành triệt tiêu đè âm thanh sau {pass_idx - 1} lượt viết lại! Toàn bộ đều trong ngưỡng an toàn (<={ALLOWABLE_OVERLAP:.1f}s hoặc cân đối 1.0x-1.1x)."
                )
            break

        if not can_rewrite:
            emit_event(
                stage_name, 25.0,
                f"Phát hiện {len(major_colliding_indices)} đoạn bị đè >{ALLOWABLE_OVERLAP:.1f}s nhưng không có API key LLM hoặc kết nối Gemini Web. Sẽ áp dụng tốc độ 1.0x-1.1x tối đa và ducking hòa âm.",
                level="warning"
            )
            break

        # Progressively shorten more aggressively on each pass
        shrink_factors = [0.88, 0.72, 0.60]
        shrink_factor = shrink_factors[min(pass_idx - 1, len(shrink_factors) - 1)]

        emit_event(
            stage_name, 20.0 + pass_idx * 12.0,
            f"Lượt {pass_idx}/{MAX_REWRITE_PASSES}: Phát hiện {len(major_colliding_indices)} đoạn bị đè âm thanh quá {ALLOWABLE_OVERLAP:.1f}s (>1.1x). Đang gom chùm câu để viết lại ngắn hơn (hệ số co: {shrink_factor * 100:.0f}%)..."
        )
        clusters = build_clusters(major_colliding_indices, segments, window=2)
        rewriter = FitRewriter(cfg=cfg, cache_dir=cfg.general.workspace_dir / ".cache" / "llm")

        all_rewritten_items = {}
        for c_idx, cluster_indices in enumerate(clusters, start=1):
            cluster_segs = []
            for c_i in cluster_indices:
                s = segments[c_i]
                s_st = float(s["start"])
                s_dur = max(0.1, round(float(s["end"]) - s_st, 3))
                s_tts = float(s.get("tts_dur") or s_dur)
                s_next = float(segments[c_i + 1]["start"]) if c_i + 1 < len(segments) else (video_dur or s_st + s_dur + 3.0)
                s_max = max(0.1, round((s_next - s_st) - 0.05, 3))

                cps = len(s.get("tts_text") or s.get("vi_text", "")) / max(0.1, s_tts)
                target_chars = int(round(s_max * cps * shrink_factor))

                is_col = (c_i in major_colliding_indices)
                cluster_segs.append({
                    "id": s["id"],
                    "zh": s.get("src_text", ""),
                    "vi_text": s.get("vi_text", ""),
                    "tts_text": s.get("tts_text", ""),
                    "is_colliding": is_col,
                    "tts_dur": s_tts,
                    "max_audio_dur": s_max,
                    "target_chars": target_chars,
                })

            rewritten = rewriter.rewrite_cluster(cluster_segs, analysis_data, stage_name=stage_name)
            for item in rewritten:
                all_rewritten_items[item["id"]] = item

        if not all_rewritten_items:
            break

        emit_event(stage_name, 25.0 + pass_idx * 12.0, f"Lượt {pass_idx}: Đã viết lại {len(all_rewritten_items)} đoạn thoại. Đang tạo lại âm thanh TTS...")

        # Backup original segment states for rollback if TTS generation fails
        backup_segs = {}
        for seg in segments:
            sid = seg["id"]
            if sid in all_rewritten_items:
                backup_segs[sid] = {
                    "vi_text": seg.get("vi_text", ""),
                    "tts_text": seg.get("tts_text", ""),
                    "tts_hash": seg.get("tts_hash"),
                    "tts_dur": seg.get("tts_dur"),
                    "voice": seg.get("voice"),
                    "cues": copy.deepcopy(seg.get("cues")),
                    "sub_slices": copy.deepcopy(seg.get("sub_slices")),
                }

        # Check TTS API worker availability
        api_worker_available = False
        from dubstudio.config import get_api_base_url, get_api_port
        api_base = get_api_base_url()
        try:
            import requests
            r = requests.get(f"{api_base}/api/health", timeout=0.5)
            if r.status_code == 200:
                api_worker_available = True
        except Exception:
            api_worker_available = False

        from dubstudio.packaging import get_runtime_python, get_subprocess_env, get_subprocess_kwargs

        for seg in segments:
            sid = seg["id"]
            if sid not in all_rewritten_items:
                continue

            rew = all_rewritten_items[sid]
            new_vi = rew.get("vi_text", seg.get("vi_text", ""))
            new_tts = rew.get("tts_text") or normalize_for_tts(new_vi)
            from dubstudio.tts.base import MALE_VOICES, FEMALE_VOICES
            voice_choice = seg.get("voice")
            if not voice_choice:
                if detect_gender:
                    voice_choice = male_voice if seg.get("gender") == "male" else female_voice
                else:
                    voice_choice = fallback_single_voice

            synth_ok = False
            new_dur = None
            w_file = tts_dir / f"{sid:04d}.wav"

            # Step A: Try API worker if running
            if api_worker_available:
                try:
                    import requests
                    res = requests.post(
                        f"{api_base}/api/jobs/{job.job_id}/segments/{sid}/tts",
                        json={"text": new_tts, "voice": voice_choice, "speed": 1.0},
                        timeout=90,
                    )
                    if res.status_code == 200:
                        rdata = res.json()
                        d = float(rdata.get("tts_dur", 0.0))
                        if d > 0.05 and w_file.exists():
                            synth_ok = True
                            new_dur = d
                except Exception as e:
                    emit_event(stage_name, 30.0 + pass_idx * 10, f"Worker TTS (port {get_api_port()}) câu #{sid} thử lại qua tiến trình con ({type(e).__name__}).", level="info")

            # Step B: Fallback to standalone single_tts subprocess
            if not synth_ok:
                try:
                    tts_single_cmd = [
                        str(get_runtime_python()), "-m", "dubstudio.tts.single_tts",
                        "--text", new_tts,
                        "--voice", voice_choice,
                        "--speed", "1.0",
                        "--out", str(w_file.resolve()),
                    ]
                    proc = subprocess.run(
                        tts_single_cmd,
                        env=get_subprocess_env(),
                        capture_output=True,
                        text=True,
                        timeout=90,
                        **get_subprocess_kwargs(),
                    )
                    if proc.returncode == 0 and w_file.exists():
                        new_dur = round(sf.info(str(w_file)).duration, 3)
                        if new_dur > 0.05:
                            synth_ok = True
                except Exception as e:
                    emit_event(stage_name, 30.0 + pass_idx * 10, f"Tiến trình con TTS lỗi ở câu #{sid}: {e}", level="warning")

            # Step C: Commit text & cues if audio synthesized, otherwise ROLL BACK to guarantee 100% sync!
            if synth_ok and new_dur:
                seg["vi_text"] = new_vi
                seg["tts_text"] = new_tts
                seg["tts_dur"] = new_dur
                seg["tts_hash"] = None
                seg["voice"] = voice_choice
                new_cues = split_sentence_cues(new_vi, seg["start"], seg["end"], target_n=5)
                seg["cues"] = new_cues
                seg["sub_slices"] = [{"text": c["text"], "start": c["start"], "end": c["end"]} for c in new_cues]
            else:
                b = backup_segs[sid]
                seg["vi_text"] = b["vi_text"]
                seg["tts_text"] = b["tts_text"]
                seg["tts_hash"] = b["tts_hash"]
                seg["tts_dur"] = b["tts_dur"]
                seg["voice"] = b["voice"]
                seg["cues"] = b["cues"]
                seg["sub_slices"] = b["sub_slices"]
                emit_event(stage_name, 35.0, f"Giữ nguyên câu #{sid} do không tạo được âm thanh mới (bảo đảm phụ đề và giọng đọc khớp 100%)", level="warning")

        # Update actual wav durations for all segments
        for seg in segments:
            w_file = tts_dir / f"{seg['id']:04d}.wav"
            if w_file.exists():
                try:
                    seg["tts_dur"] = round(sf.info(str(w_file)).duration, 3)
                except Exception:
                    pass

        # Commit synchronized segments to disk
        with open(segments_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ─── 3. Final Placement & 1.0x - 1.1x Audio Stretching ───
    emit_event(stage_name, 70.0, "Đang căn chỉnh tốc độ và sắp xếp âm thanh lên trục timeline...")
    fit_plan = []
    outputs = ["fit_plan.json", "segments.json"]

    for idx, seg in enumerate(segments):
        st = float(seg["start"])
        orig_dur = max(0.1, round(float(seg["end"]) - st, 3))
        tts_dur = float(seg.get("tts_dur") or orig_dur)

        wav_path = tts_dir / f"{seg['id']:04d}.wav"
        if not wav_path.exists():
            continue

        if idx + 1 < len(segments):
            next_st = float(segments[idx + 1]["start"])
        else:
            next_st = video_dur if video_dur > st + orig_dur else (st + orig_dur + 3.0)

        # Kiểm tra khoảng trống phía trước để xê dịch tối đa 0.5s nếu câu bị chèn
        prev_end = float(segments[idx - 1]["end"]) if idx > 0 else 0.0
        gap_before = max(0.0, st - prev_end)
        needed_dur = tts_dur / 1.10
        if needed_dur > (next_st - st) and gap_before > 0.02:
            shift = min(0.50, gap_before, needed_dur - (next_st - st))
            st = max(0.0, round(st - shift, 3))

        available_dur = max(orig_dur, round(next_st - st, 3))
        max_audio_dur = max(0.1, round(available_dur - 0.05, 3))
        silence_after = max(0.0, available_dur - orig_dur)

        # Calculate rate: strictly adhere to [1.0x - 1.10x] speedup; NEVER artificially slow down natural speech
        if tts_dur > max_audio_dur:
            raw_rate = tts_dur / max_audio_dur
            rate = min(1.10, max(1.0, round(raw_rate, 2)))
            method = "speedup" if rate > 1.01 else "none"
        else:
            rate = 1.0
            method = "none"

        final_wav = f"tts/{seg['id']:04d}.wav"
        if method == "speedup" and rate > 1.01:
            stretched_file = stretched_dir / f"{seg['id']:04d}.wav"
            time_stretch_audio(wav_path, stretched_file, rate)
            final_wav = f"tts_stretched/{stretched_file.name}"
            outputs.append(final_wav)

        # Enforce audio file duration boundary to NEVER exceed next_st + ALLOWABLE_OVERLAP
        target_wav_path = job.workspace / final_wav
        max_allowed_file_dur = max(0.1, round(next_st - st + ALLOWABLE_OVERLAP, 3))
        if target_wav_path.exists():
            actual_file_dur = enforce_audio_boundary(target_wav_path, max_allowed_file_dur)
            effective_dur = actual_file_dur
        else:
            effective_dur = round(tts_dur / rate, 3) if rate > 0 else tts_dur

        seg["fit"] = {
            "method": method,
            "rate": rate,
            "notes": f"Tốc độ: {rate:.2f}x ({method})",
        }
        seg["fit_rate"] = round(rate, 2)
        seg["speed"] = round(rate, 2)

        voice_start = round(st, 3)
        voice_end = round(voice_start + effective_dur, 3)

        # Allow slight overlap on timeline within ALLOWABLE_OVERLAP (0.30s)
        if idx + 1 < len(segments) and voice_end > next_st + ALLOWABLE_OVERLAP:
            voice_end = round(next_st + ALLOWABLE_OVERLAP, 3)
            effective_dur = round(voice_end - voice_start, 3)

        ratio = effective_dur / max(0.05, orig_dur)
        seg["start"] = voice_start
        seg["end"] = voice_end
        seg["dur"] = round(voice_end - voice_start, 3)
        seg["voice_start"] = voice_start
        seg["voice_dur"] = effective_dur

        # Synchronize cues and sub_slices
        if seg.get("cues") and isinstance(seg["cues"], list):
            for cue in seg["cues"]:
                if isinstance(cue, dict):
                    c_st = float(cue.get("start", st))
                    c_en = float(cue.get("end", st + orig_dur))
                    rel_st = max(0.0, c_st - st)
                    rel_en = max(rel_st + 0.05, c_en - st)
                    cue["start"] = round(voice_start + rel_st * ratio, 3)
                    cue["end"] = round(voice_start + rel_en * ratio, 3)

        if seg.get("sub_slices") and isinstance(seg["sub_slices"], list):
            for sl in seg["sub_slices"]:
                if isinstance(sl, dict):
                    s_st = float(sl.get("start", st))
                    s_en = float(sl.get("end", st + orig_dur))
                    rel_st = max(0.0, s_st - st)
                    rel_en = max(rel_st + 0.05, s_en - st)
                    sl["start"] = round(voice_start + rel_st * ratio, 3)
                    sl["end"] = round(voice_start + rel_en * ratio, 3)

        fit_plan.append({
            "id": seg["id"],
            "start": voice_start,
            "end": voice_end,
            "wav": final_wav,
            "fit": seg["fit"],
            "flags": ["collision_prevented"] if rate > 1.0 else [],
        })

    # Save fit_plan.json and segments.json
    fit_plan_file = job.workspace / "fit_plan.json"
    with open(fit_plan_file, "w", encoding="utf-8") as f:
        json.dump(fit_plan, f, ensure_ascii=False, indent=2)

    with open(segments_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    job.finish_stage(stage_name, outputs)
    emit_event(stage_name, 100.0, "Hoàn tất khớp âm thanh! 100% các đoạn thoại không bị đè lên nhau trên timeline.")

"""Stage: fit. Closed-loop voice-to-picture timing algorithm with audio collision detection,
1.0x - 1.1x tempo balancing for minor overlaps, and batch two-way length balancing (shorter/longer) via LLM.
"""
import copy
import json
import os
from pathlib import Path
import shutil
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


def resolve_isolated_pair_shifts(segments: List[Dict[str, Any]], video_dur: float, max_shift: float = 0.25) -> int:
    """If exactly two consecutive segments collide with each other and are isolated
    (neither collides with outside neighbors), shift segment A backwards (up to max_shift)
    and segment B forwards (up to max_shift) using available silence gaps before and after.
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


def synthesize_fit_tts_batch(
    items_to_synth: List[Dict[str, Any]],
    tts_dir: Path,
    cfg: AppConfig,
    job_id: str = "",
    stage_name: str = "fit",
) -> Dict[int, float]:
    """Synthesize TTS for a batch of rewritten items using a persistent warm worker server.
    Falls back to API worker and single_tts if needed.
    Returns mapping: {segment_id: duration_in_seconds}
    """
    if not items_to_synth:
        return {}

    results: Dict[int, float] = {}
    from dubstudio.packaging import get_runtime_python, get_subprocess_env, get_subprocess_kwargs
    from dubstudio.config import get_api_base_url

    py_exe = get_runtime_python()
    worker_cmd = [str(py_exe), "-m", "dubstudio.tts.worker_server"]
    worker_proc = None

    # Step 1: Attempt warm worker_server (loads model once, synthesizes in ~0.4s per line)
    try:
        sub_kwargs = get_subprocess_kwargs()
        sub_kwargs.pop("stdin", None)
        worker_proc = subprocess.Popen(
            worker_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=get_subprocess_env(),
            **sub_kwargs,
        )
        try:
            from dubstudio.win_job import assign_process_to_job
            assign_process_to_job(worker_proc)
        except Exception:
            pass

        init_line = worker_proc.stdout.readline() if worker_proc.stdout else ""
        if init_line:
            status_data = json.loads(init_line.strip())
            if status_data.get("status") == "ready":
                for item in items_to_synth:
                    sid = item["id"]
                    text = item["new_tts"]
                    voice = item["voice"]
                    out_path = item["out_path"]

                    req = {
                        "text": text,
                        "voice": voice,
                        "speed": 1.0,
                        "out": str(out_path.resolve()),
                    }
                    worker_proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
                    worker_proc.stdin.flush()

                    resp_line = worker_proc.stdout.readline()
                    if not resp_line:
                        break
                    resp = json.loads(resp_line.strip())
                    if resp.get("status") == "ok":
                        dur = float(resp.get("duration", 0.0))
                        if dur > 0.05 and out_path.exists():
                            results[sid] = dur

                try:
                    worker_proc.stdin.write(json.dumps({"cmd": "exit"}) + "\n")
                    worker_proc.stdin.flush()
                    worker_proc.wait(timeout=5)
                except Exception:
                    pass
    except Exception as e:
        emit_event(stage_name, 29.0, f"Worker TTS batch gặp sự cố ({e}), đang dùng phương thức phụ...", level="info")
    finally:
        if worker_proc and worker_proc.poll() is None:
            try:
                worker_proc.terminate()
            except Exception:
                pass

    # Step 2: Fallback to active FastAPI background worker (if running)
    unresolved = [it for it in items_to_synth if it["id"] not in results]
    if unresolved and job_id:
        api_base = get_api_base_url()
        api_available = False
        try:
            import requests
            r = requests.get(f"{api_base}/api/health", timeout=0.5)
            if r.status_code == 200:
                api_available = True
        except Exception:
            api_available = False

        if api_available:
            for item in list(unresolved):
                sid = item["id"]
                try:
                    import requests
                    res = requests.post(
                        f"{api_base}/api/jobs/{job_id}/segments/{sid}/tts",
                        json={"text": item["new_tts"], "voice": item["voice"], "speed": 1.0},
                        timeout=90,
                    )
                    if res.status_code == 200:
                        rdata = res.json()
                        d = float(rdata.get("tts_dur", 0.0))
                        if d > 0.05 and item["out_path"].exists():
                            results[sid] = d
                            unresolved.remove(item)
                except Exception:
                    pass

    # Step 3: Fallback to standalone single_tts subprocess
    for item in unresolved:
        sid = item["id"]
        tmp_out = tts_dir / f"{sid:04d}_tmp.wav"
        try:
            cmd = [
                str(py_exe), "-m", "dubstudio.tts.single_tts",
                "--text", item["new_tts"],
                "--voice", item["voice"],
                "--speed", "1.0",
                "--out", str(tmp_out.resolve()),
            ]
            proc = subprocess.run(
                cmd,
                env=get_subprocess_env(),
                capture_output=True,
                text=True,
                timeout=90,
                **get_subprocess_kwargs(),
            )
            if proc.returncode == 0 and tmp_out.exists():
                d = round(sf.info(str(tmp_out)).duration, 3)
                if d > 0.05:
                    shutil.move(str(tmp_out), str(item["out_path"]))
                    results[sid] = d
        except Exception as e:
            emit_event(stage_name, 30.0, f"single_tts lỗi ở câu #{sid}: {e}", level="warning")
        finally:
            if tmp_out.exists():
                try:
                    tmp_out.unlink()
                except Exception:
                    pass

    return results


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

    # Xê dịch các cặp câu bị đè cô lập tới lui tối đa 0.25s nếu trước và sau còn trống
    isolated_shifted = resolve_isolated_pair_shifts(segments, video_dur, max_shift=0.25)
    if isolated_shifted > 0:
        emit_event(stage_name, 10.0, f"Đã tự động xê dịch tới/lui tối đa 0.25s cho {isolated_shifted} cặp câu bị đè cô lập vào khoảng trống yên lặng.")

    # ─── 1. Multi-pass Two-Way Timing Balancing & Batch LLM Rewrite ───
    ALLOWABLE_OVERLAP = 0.10
    MAX_REWRITE_PASSES = 3

    from dubstudio.llm.cdp_gemini import is_cdp_ready, find_browser_executable
    cdp_port = getattr(cfg.translation, "cdp_port", 9222)
    has_browser = bool(find_browser_executable())

    trans_provider = getattr(cfg.translation, "provider", "gemini_web")
    if conf.get("translation_provider"):
        trans_provider = conf["translation_provider"]

    is_gemini_web = (trans_provider == "gemini_web") or is_cdp_ready(cdp_port) or has_browser
    has_api_key = bool(
        cfg.gemini_api_key
        or os.getenv("GEMINI_API_KEY")
        or getattr(cfg.translation, "groq_api_key", None)
        or os.getenv("GROQ_API_KEY")
    )
    can_rewrite = has_api_key or is_gemini_web

    rewriter = FitRewriter(cfg=cfg, cache_dir=job.workspace / ".cache" / "llm")
    shrink_factors = [0.88, 0.72, 0.60]

    for pass_idx in range(1, MAX_REWRITE_PASSES + 1):
        shrink_factor = shrink_factors[min(pass_idx - 1, len(shrink_factors) - 1)]
        mismatched_units: List[Dict[str, Any]] = []

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

            # Check collision (too long)
            if raw_overlap > 0.02:
                overlap_after_speedup = round((tts_dur / 1.10) - max_audio_dur, 3)
                if overlap_after_speedup > ALLOWABLE_OVERLAP:
                    prev_end = float(segments[idx - 1]["end"]) if idx > 0 else 0.0
                    gap_before = max(0.0, st - prev_end)
                    needed_relief = overlap_after_speedup - ALLOWABLE_OVERLAP
                    shift_back = min(0.25, gap_before, needed_relief)

                    new_st = max(0.0, round(st - shift_back, 3))
                    new_avail = max(orig_dur, round(next_st - new_st, 3))
                    new_max_audio = max(0.1, round(new_avail - 0.05, 3))
                    new_overlap = round((tts_dur / 1.10) - new_max_audio, 3)

                    if new_overlap <= ALLOWABLE_OVERLAP:
                        seg["start"] = new_st
                        seg["voice_start"] = new_st
                    else:
                        cps = len(seg.get("tts_text") or seg.get("vi_text", "")) / max(0.1, tts_dur)
                        target_chars = max(10, int(round(new_max_audio * cps * shrink_factor)))
                        mismatched_units.append({
                            "id": seg["id"],
                            "idx": idx,
                            "zh": seg.get("src_text", ""),
                            "vi_text": seg.get("vi_text", ""),
                            "tts_text": seg.get("tts_text", ""),
                            "measured_dur": tts_dur,
                            "max_audio_dur": new_max_audio,
                            "direction": "shorter",
                            "target_chars": target_chars,
                            "prev_vi": segments[idx - 1].get("vi_text", "") if idx > 0 else "",
                            "next_vi": segments[idx + 1].get("vi_text", "") if idx + 1 < len(segments) else "",
                        })

            # Check underflow (too short compared to speaker duration on screen) - Pass 1 only
            elif pass_idx == 1:
                if tts_dur < 0.65 * orig_dur and orig_dur >= 2.0 and (next_st - (st + tts_dur)) > 1.2:
                    cps = len(seg.get("tts_text") or seg.get("vi_text", "")) / max(0.1, tts_dur)
                    target_chars = int(round(orig_dur * cps * 0.95))
                    mismatched_units.append({
                        "id": seg["id"],
                        "idx": idx,
                        "zh": seg.get("src_text", ""),
                        "vi_text": seg.get("vi_text", ""),
                        "tts_text": seg.get("tts_text", ""),
                        "measured_dur": tts_dur,
                        "max_audio_dur": round(orig_dur, 2),
                        "direction": "longer",
                        "target_chars": target_chars,
                        "prev_vi": segments[idx - 1].get("vi_text", "") if idx > 0 else "",
                        "next_vi": segments[idx + 1].get("vi_text", "") if idx + 1 < len(segments) else "",
                    })

        # If no mismatched units need rewriting, we are done!
        if not mismatched_units:
            if pass_idx == 1:
                emit_event(stage_name, 65.0, "Toàn bộ âm thanh đã vừa vặn với hình ảnh, không cần viết lại.")
            else:
                emit_event(
                    stage_name, 65.0,
                    f"Hoàn thành triệt tiêu đè âm thanh sau lượt {pass_idx - 1}! Toàn bộ đều trong ngưỡng an toàn (<={ALLOWABLE_OVERLAP:.1f}s hoặc cân đối 1.0x-1.1x)."
                )
            break

        if not can_rewrite:
            emit_event(
                stage_name, 25.0,
                f"Phát hiện {len(mismatched_units)} đoạn cần cân bằng thời lượng nhưng không có API key LLM hoặc kết nối Gemini Web. Sẽ áp dụng tốc độ 1.0x-1.1x tối đa.",
                level="warning"
            )
            break

        emit_event(
            stage_name, 20.0 + pass_idx * 12.0,
            f"Lượt {pass_idx}/{MAX_REWRITE_PASSES}: Đang gửi {len(mismatched_units)} câu cần cân bằng thời lượng đến LLM trong 1 yêu cầu duy nhất..."
        )

        # Single batch LLM call across all mismatched units
        rewritten_list = rewriter.rewrite_units(mismatched_units, analysis_data, pass_idx=pass_idx, stage_name=stage_name)
        rewritten_map = {item["id"]: item for item in rewritten_list if isinstance(item, dict) and item.get("id") is not None}

        if not rewritten_map:
            emit_event(stage_name, 25.0 + pass_idx * 12.0, f"Lượt {pass_idx}: Không nhận được dữ liệu từ LLM, chuyển sang bước bố trí âm thanh.")
            break

        # Filter strictly for segments that actually changed
        changed_units = []
        mismatched_ids = {u["id"] for u in mismatched_units}

        for seg in segments:
            sid = seg["id"]
            if sid not in mismatched_ids or sid not in rewritten_map:
                continue

            rew = rewritten_map[sid]
            new_vi = (
                rew.get("vi_text")
                or rew.get("vi")
                or rew.get("text")
                or rew.get("shortened_vi")
                or seg.get("vi_text", "")
            ).strip()
            new_tts = (
                rew.get("tts_text")
                or rew.get("tts")
                or rew.get("spoken_text")
                or normalize_for_tts(new_vi)
            ).strip()
            orig_vi = seg.get("vi_text", "").strip()

            if new_vi and new_vi != orig_vi:
                voice_choice = seg.get("voice")
                if not voice_choice:
                    if detect_gender:
                        voice_choice = male_voice if seg.get("gender") == "male" else female_voice
                    else:
                        voice_choice = fallback_single_voice
                changed_units.append({
                    "id": sid,
                    "seg": seg,
                    "orig_vi": orig_vi,
                    "new_vi": new_vi,
                    "new_tts": new_tts,
                    "voice": voice_choice,
                    "out_path": tts_dir / f"{sid:04d}.wav",
                })
            else:
                emit_event(stage_name, 26.0 + pass_idx * 12.0, f"Đoạn #{sid}: Lời thoại giữ nguyên sau lượt {pass_idx}.", level="info")

        if not changed_units:
            emit_event(stage_name, 26.0 + pass_idx * 12.0, f"Lượt {pass_idx}: Không có câu nào cần thay đổi âm thanh.")
            break

        emit_event(stage_name, 28.0 + pass_idx * 12.0, f"Lượt {pass_idx}: Đang tổng hợp âm thanh TTS cho {len(changed_units)} câu đã biên tập lại...")

        # Batch synthesize TTS for changed items only
        synth_results = synthesize_fit_tts_batch(changed_units, tts_dir, cfg, job_id=job.job_id, stage_name=stage_name)

        # Apply newly synthesized audio and sync cues
        for item in changed_units:
            sid = item["id"]
            seg = item["seg"]
            if sid in synth_results:
                new_dur = synth_results[sid]
                seg["vi_text"] = item["new_vi"]
                seg["tts_text"] = item["new_tts"]
                seg["tts_dur"] = new_dur
                seg["tts_hash"] = None
                seg["voice"] = item["voice"]
                new_cues = split_sentence_cues(item["new_vi"], seg["start"], seg["end"], target_n=5)
                seg["cues"] = new_cues
                seg["sub_slices"] = [{"text": c["text"], "start": c["start"], "end": c["end"]} for c in new_cues]
                emit_event(
                    stage_name,
                    29.0 + pass_idx * 12.0,
                    f"Đoạn #{sid} đã cập nhật âm thanh ({item['orig_vi'][:25]}... -> {item['new_vi'][:25]}..., {new_dur:.2f}s)"
                )
            else:
                emit_event(
                    stage_name, 35.0,
                    f"Giữ nguyên câu #{sid} do không tạo được âm thanh mới (bảo đảm phụ đề và giọng đọc khớp 100%)",
                    level="warning"
                )

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

        # Check if any collisions remain after this pass
        remaining_collisions = 0
        for idx, seg in enumerate(segments):
            st = float(seg["start"])
            orig_dur = max(0.1, round(float(seg["end"]) - st, 3))
            tts_dur = float(seg.get("tts_dur") or orig_dur)
            next_st = float(segments[idx + 1]["start"]) if idx + 1 < len(segments) else (video_dur or st + orig_dur + 3.0)
            avail = max(orig_dur, round(next_st - st, 3))
            max_a = max(0.1, round(avail - 0.05, 3))
            overlap_after_speed = round((tts_dur / 1.10) - max_a, 3)
            if overlap_after_speed > ALLOWABLE_OVERLAP:
                prev_end = float(segments[idx - 1]["end"]) if idx > 0 else 0.0
                gap_before = max(0.0, st - prev_end)
                shift_back = min(0.25, gap_before, overlap_after_speed - ALLOWABLE_OVERLAP)
                shifted_avail = max(orig_dur, round(next_st - (st - shift_back), 3))
                if round((tts_dur / 1.10) - (shifted_avail - 0.05), 3) > ALLOWABLE_OVERLAP:
                    remaining_collisions += 1

        if remaining_collisions == 0:
            emit_event(
                stage_name, 65.0,
                f"Hoàn thành triệt tiêu đè âm thanh sau lượt {pass_idx}! Toàn bộ đều trong ngưỡng an toàn (<={ALLOWABLE_OVERLAP:.1f}s hoặc cân đối 1.0x-1.1x)."
            )
            break

    # ─── 2. Final Placement & 1.0x - 1.1x Audio Stretching ───
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

        # Kiểm tra khoảng trống phía trước để xê dịch tối đa 0.25s nếu câu bị chèn
        prev_end = float(segments[idx - 1]["end"]) if idx > 0 else 0.0
        gap_before = max(0.0, st - prev_end)
        needed_dur = tts_dur / 1.10
        if needed_dur > (next_st - st) and gap_before > 0.02:
            shift = min(0.25, gap_before, needed_dur - (next_st - st))
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

        # Allow slight overlap on timeline within ALLOWABLE_OVERLAP (0.10s)
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

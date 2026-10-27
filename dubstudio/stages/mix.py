"""Stage: mix. Builds voice track and mixes with background music (BGM)."""
import json
from pathlib import Path
import subprocess
import numpy as np
import soundfile as sf
from dubstudio.config import AppConfig
from dubstudio.errors import DubError
from dubstudio.events import emit_event
from dubstudio.jobstate import JobContext, compute_file_hash


def run(job: JobContext, cfg: AppConfig, force: bool = False) -> None:
    stage_name = "mix"
    emit_event(stage_name, 0.0, "Bắt đầu ghép bè âm thanh (mix voice & BGM)")

    fit_plan_file = job.workspace / "fit_plan.json"
    mix_settings_file = job.workspace / "mix_settings.json"

    # Ensure fit_plan.json exists; run fit stage or build basic fallback if missing
    if not fit_plan_file.exists():
        emit_event(stage_name, 5.0, "Chưa có fit_plan.json, đang tự động đồng bộ kế hoạch khớp tiếng...")
        try:
            from dubstudio.stages import fit
            fit.run(job, cfg)
        except Exception as e:
            emit_event(stage_name, 5.0, f"Cảnh báo fit tự động: {e}", level="warning")

    if not fit_plan_file.exists():
        # Fallback: Build basic fit_plan directly from segments.json and tts directory
        plan = []
        segments_file = job.workspace / "segments.json"
        if segments_file.exists():
            try:
                with open(segments_file, "r", encoding="utf-8") as f:
                    s_data = json.load(f)
                for s in s_data.get("segments", []):
                    w_cand = job.workspace / f"tts/{s['id']:04d}.wav"
                    if w_cand.exists():
                        plan.append({
                            "id": s["id"],
                            "start": float(s.get("voice_start", s["start"])),
                            "end": float(s.get("end", s["start"] + 1.0)),
                            "wav": f"tts/{s['id']:04d}.wav",
                            "rate": float(s.get("fit_rate", s.get("speed", 1.0))),
                        })
            except Exception:
                pass
        with open(fit_plan_file, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)

    input_hash = compute_file_hash(fit_plan_file)
    if mix_settings_file.exists():
        input_hash += "_" + compute_file_hash(mix_settings_file)
    orig_ranges_file = job.workspace / "orig_audio_ranges.json"
    if orig_ranges_file.exists():
        input_hash += "_" + compute_file_hash(orig_ranges_file)

    if not force and job.is_stage_done(stage_name, input_hash):
        emit_event(stage_name, 100.0, "Giai đoạn mix đã hoàn thành (bỏ qua)")
        return

    job.start_stage(stage_name, input_hash)

    with open(fit_plan_file, "r", encoding="utf-8") as f:
        fit_plan = json.load(f)

    # Read target video duration with robust fallbacks
    segments_file = job.workspace / "segments.json"
    with open(segments_file, "r", encoding="utf-8") as f:
        seg_data = json.load(f)
    video_dur = float(seg_data.get("video", {}).get("duration", 0.0) or 0.0)

    # Fallback 1: probe.json
    probe_file = job.workspace / "probe.json"
    if video_dur <= 0.0 and probe_file.exists():
        try:
            p_data = json.loads(probe_file.read_text(encoding="utf-8"))
            video_dur = float(p_data.get("format", {}).get("duration", 0.0) or 0.0)
        except Exception:
            pass

    # Fallback 2: Audio stems on disk
    if video_dur <= 0.0:
        for a_cand in [job.workspace / "audio" / "bgm.wav", job.workspace / "audio" / "vocals.wav", job.workspace / "audio" / "orig.wav"]:
            if a_cand.exists():
                try:
                    video_dur = float(sf.info(str(a_cand.resolve())).duration)
                    if video_dur > 0.0:
                        break
                except Exception:
                    pass

    # Fallback 3: Max end timestamp from fit_plan and segments
    max_seg_end = 0.0
    for item in fit_plan:
        st = float(item.get("start", 0.0))
        wav_dur = float(item.get("dur", 0.0))
        wav_file = job.workspace / item.get("wav", "")
        if wav_file.exists():
            try:
                wav_dur = max(wav_dur, float(sf.info(str(wav_file.resolve())).duration))
            except Exception:
                pass
        max_seg_end = max(max_seg_end, st + wav_dur)
    for s in seg_data.get("segments", []):
        max_seg_end = max(max_seg_end, float(s.get("end", 0.0)))
    video_dur = max(video_dur, max_seg_end + 2.0)

    # Detect native TTS sample rate from fit_plan items to avoid any lossy resampling
    sr = 24000
    for item in fit_plan:
        w_cand = job.workspace / item.get("wav", "")
        if w_cand.exists():
            try:
                sr = sf.info(str(w_cand.resolve())).samplerate
                break
            except Exception:
                pass
    total_samples = int(video_dur * sr) + sr  # add 1s safety margin
    voice_track = np.zeros(total_samples, dtype=np.float32)

    import math
    from scipy.signal import resample_poly

    # Look up segment metadata to respect mute_tts and keep_original
    seg_lookup = {}
    keep_orig_ranges = []
    for s in seg_data.get("segments", []):
        sid = s.get("id")
        if sid is not None:
            seg_lookup[sid] = s
        if s.get("keep_original"):
            st = float(s.get("start", 0.0))
            en = float(s.get("end", st + 0.1))
            if en > st:
                keep_orig_ranges.append((st, en))

    if orig_ranges_file.exists():
        try:
            r_data = json.loads(orig_ranges_file.read_text(encoding="utf-8"))
            for r in r_data:
                if isinstance(r, dict):
                    st = float(r.get("start", 0.0))
                    en = float(r.get("end", 0.0))
                    if en > st:
                        keep_orig_ranges.append((st, en))
                elif isinstance(r, (list, tuple)) and len(r) == 2:
                    st, en = float(r[0]), float(r[1])
                    if en > st:
                        keep_orig_ranges.append((st, en))
        except Exception:
            pass

    if mix_settings_file.exists():
        try:
            m_data = json.loads(mix_settings_file.read_text(encoding="utf-8"))
            for r in m_data.get("keep_original_ranges", []):
                if isinstance(r, (list, tuple)) and len(r) == 2:
                    st, en = float(r[0]), float(r[1])
                    if en > st:
                        keep_orig_ranges.append((st, en))
        except Exception:
            pass

    # Merge overlapping keep_orig ranges
    merged_keep_ranges = []
    if keep_orig_ranges:
        sorted_ranges = sorted(keep_orig_ranges, key=lambda x: x[0])
        merged_keep_ranges = [sorted_ranges[0]]
        for cur in sorted_ranges[1:]:
            prev = merged_keep_ranges[-1]
            if cur[0] <= prev[1] + 0.05:
                merged_keep_ranges[-1] = (prev[0], max(prev[1], cur[1]))
            else:
                merged_keep_ranges.append(cur)

    # Place each segment at its absolute timestamp (AGENTS.md Section 8)
    for i, item in enumerate(fit_plan):
        sid = item.get("id")
        smeta = seg_lookup.get(sid, {})
        # Skip if muted or keep_original is requested
        if item.get("muted") or smeta.get("mute_tts") or smeta.get("muted_tts") or smeta.get("keep_original"):
            continue

        start_sec = item["start"]
        wav_path = job.workspace / item["wav"]
        if not wav_path.exists():
            continue

        audio_data, file_sr = sf.read(str(wav_path.resolve()))
        if audio_data.ndim > 1:
            audio_data = audio_data.mean(axis=1)

        # High-quality polyphase anti-aliasing resample if sample rates differ
        if file_sr != sr:
            g = math.gcd(int(sr), int(file_sr))
            up = int(sr) // g
            down = int(file_sr) // g
            audio_data = resample_poly(audio_data, up, down).astype(np.float32)

        # Natural speech transition and anti-overlap leveling
        if i + 1 < len(fit_plan):
            next_start_sec = float(fit_plan[i + 1]["start"])
            overlap_sec = (start_sec + len(audio_data) / sr) - next_start_sec
            if overlap_sec > 0:
                # Apply smooth cross-tail decay over the overlap region to prevent collision
                # while preserving all spoken words naturally (never chop off speech mid-sentence!)
                overlap_samples = min(int(overlap_sec * sr), len(audio_data))
                if overlap_samples > 0:
                    audio_data[-overlap_samples:] *= np.linspace(1.0, 0.05, overlap_samples, dtype=np.float32)

        start_idx = int(start_sec * sr)
        end_idx = min(start_idx + len(audio_data), total_samples)
        chunk_len = end_idx - start_idx
        if chunk_len > 0:
            voice_track[start_idx:end_idx] += audio_data[:chunk_len]

    # Process original audio passthrough and BGM ducking if any segments requested keep_original
    orig_passthrough_wav = None
    orig_bgm_wav = job.workspace / "audio" / "bgm.wav"
    bgm_effective_wav = orig_bgm_wav

    if merged_keep_ranges:
        emit_event(stage_name, 60.0, f"Đang hòa âm {len(merged_keep_ranges)} đoạn giữ âm thanh gốc (fadein/fadeout mượt)...")
        # Equal-power raised cosine S-curve crossfade (150ms) to ensure smooth transition
        fade_len = int(0.15 * sr)
        orig_mask = np.zeros(total_samples, dtype=np.float32)
        for st, en in merged_keep_ranges:
            i0 = int(st * sr)
            i1 = min(total_samples, int(en * sr))
            if i1 <= i0:
                continue
            orig_mask[i0:i1] = 1.0
            fl = min(fade_len, (i1 - i0) // 2)
            if fl > 0:
                x = np.linspace(0.0, 1.0, fl, dtype=np.float32)
                curve_in = (0.5 * (1.0 - np.cos(np.pi * x))).astype(np.float32)
                curve_out = (0.5 * (1.0 + np.cos(np.pi * x))).astype(np.float32)
                orig_mask[i0:i0 + fl] = curve_in
                orig_mask[i1 - fl:i1] = curve_out

        # Build passthrough track from original audio
        passthrough_audio = np.zeros((total_samples, 2), dtype=np.float32)
        orig_wav = job.workspace / "audio" / "orig.wav"
        if orig_wav.exists():
            orig_data, o_sr = sf.read(str(orig_wav.resolve()))
            if o_sr != sr:
                g = math.gcd(int(sr), int(o_sr))
                up = int(sr) // g
                down = int(o_sr) // g
                orig_data = resample_poly(orig_data, up, down).astype(np.float32)

            if orig_data.ndim == 1:
                orig_data = np.column_stack([orig_data, orig_data])
            o_len = len(orig_data)
            p_len = min(o_len, total_samples)
            passthrough_audio[:p_len] = orig_data[:p_len]
            passthrough_audio[:, 0] *= orig_mask
            passthrough_audio[:, 1] *= orig_mask

            orig_passthrough_wav = job.workspace / "orig_passthrough.wav"
            sf.write(str(orig_passthrough_wav.resolve()), passthrough_audio, sr)

        # Duck separated BGM so it does not double-play over original audio
        ducked_bgm = np.zeros((total_samples, 2), dtype=np.float32)
        if orig_bgm_wav.exists():
            bgm_data, b_sr = sf.read(str(orig_bgm_wav.resolve()))
            if b_sr != sr:
                g = math.gcd(int(sr), int(b_sr))
                up = int(sr) // g
                down = int(b_sr) // g
                bgm_data = resample_poly(bgm_data, up, down).astype(np.float32)
            if bgm_data.ndim == 1:
                bgm_data = np.column_stack([bgm_data, bgm_data])
            b_len = len(bgm_data)
            p_len = min(b_len, total_samples)
            ducked_bgm[:p_len] = bgm_data[:p_len]
            ducked_bgm[:, 0] *= (1.0 - orig_mask)
            ducked_bgm[:, 1] *= (1.0 - orig_mask)

            bgm_ducked_p = job.workspace / "bgm_ducked.wav"
            sf.write(str(bgm_ducked_p.resolve()), ducked_bgm, sr)
            bgm_effective_wav = bgm_ducked_p

        # Combine ducked BGM with original audio passthrough for preview
        combined_bgm = ducked_bgm + passthrough_audio
        sf.write(str((job.workspace / "bgm_effective.wav").resolve()), combined_bgm, sr)

    # Normalize voice track only if peaks exceed 0.98 to prevent clipping
    max_val = np.max(np.abs(voice_track))
    if max_val > 0.98:
        voice_track = (voice_track / max_val) * 0.98

    # Ensure 2-channel stereo without ITU pan attenuation
    if voice_track.ndim == 1:
        voice_stereo = np.column_stack([voice_track, voice_track])
    else:
        voice_stereo = voice_track

    raw_voice_wav = job.workspace / "voice_raw.wav"
    sf.write(str(raw_voice_wav.resolve()), voice_stereo, sr)

    # Combine with BGM if available
    bgm_wav = job.workspace / "audio" / "bgm.wav"
    final_mixed_wav = job.workspace / "voice_track.wav"
    mixed_wav = job.workspace / "mixed.wav"

    # Read 4-track audio mixing settings
    orig_bgm_volume = 1.00
    custom_bgm_path = None
    custom_bgm_volume = 0.50
    include_orig_voice = False
    orig_voice_volume = 0.00
    vi_voice_volume = 1.00

    if mix_settings_file.exists():
        try:
            mix_data = json.loads(mix_settings_file.read_text(encoding="utf-8"))
            raw_bgm = float(mix_data.get("orig_bgm_volume", mix_data.get("bgm_volume", 1.00)))
            if raw_bgm > 2.0:
                raw_bgm /= 100.0
            orig_bgm_volume = max(0.0, min(2.0, raw_bgm))

            raw_orig_voice = float(mix_data.get("orig_voice_volume", 0.00))
            if raw_orig_voice > 2.0:
                raw_orig_voice /= 100.0
            orig_voice_volume = max(0.0, min(2.0, raw_orig_voice))
            include_orig_voice = bool(mix_data.get("include_orig_voice", False)) or (orig_voice_volume > 0.01)

            raw_vi_voice = float(mix_data.get("vi_voice_volume", mix_data.get("voice_volume", 1.00)))
            if raw_vi_voice > 2.0:
                raw_vi_voice /= 100.0
            vi_voice_volume = max(0.0, min(2.0, raw_vi_voice))

            c_bgm = mix_data.get("custom_bgm_path")
            if c_bgm and Path(c_bgm).exists():
                custom_bgm_path = Path(c_bgm)
            raw_c_bgm_vol = float(mix_data.get("custom_bgm_volume", 0.50))
            if raw_c_bgm_vol > 2.0:
                raw_c_bgm_vol /= 100.0
            custom_bgm_volume = max(0.0, min(2.0, raw_c_bgm_vol))
        except Exception:
            pass

    out_sr = 48000
    orig_bgm_wav = job.workspace / "audio" / "bgm.wav"
    vocals_wav = job.workspace / "audio" / "vocals.wav"
    orig_wav = job.workspace / "audio" / "orig.wav"
    orig_target = vocals_wav if vocals_wav.exists() else (orig_wav if orig_wav.exists() else None)

    # Build dynamic ffmpeg inputs and audio filters
    # Input 0 is always raw_voice_wav (its duration sets video length)
    # Studio Vocal Enhancement & 0-200% Leveling (+20dB at 200%):
    # 1. highpass=f=80: cuts sub-bass rumble/mic thumps below 80Hz
    # 2. equalizer=f=3200:t=q:w=1.2:g=1.8: speech intelligibility & presence lift
    # 3. equalizer=f=350:t=q:w=1.4:g=-1.2: cleans boxy lower-mid mud
    # 0% -> 100%: 100% exact original volume of raw_voice_wav (0dB difference at 100%)
    # 101% -> 200%: Direct amplitude amplification up to +20.0 dB at 200% with transparent peak limiter
    eq_chain = "highpass=f=80,equalizer=f=350:t=q:w=1.4:g=-1.2,equalizer=f=3200:t=q:w=1.2:g=1.8"
    if vi_voice_volume <= 1.0:
        gain = max(0.0, vi_voice_volume)
        vi_filter = f"{eq_chain},volume={gain:.2f},aresample=48000,aformat=channel_layouts=stereo"
    else:
        gain_db = (vi_voice_volume - 1.0) * 20.0
        vi_filter = (
            f"{eq_chain},"
            f"volume={gain_db:.2f}dB,"
            f"alimiter=limit=0.98:attack=1:release=15:level=disabled,"
            f"aresample=48000,aformat=channel_layouts=stereo"
        )

    inputs = ["-i", str(raw_voice_wav.resolve())]
    filter_parts = [f"[0:a]{vi_filter}[vi]"]
    mix_inputs = ["[vi]"]
    input_idx = 1

    # Track 2: Video separated BGM (uses ducked BGM if passthrough ranges active)
    # Applied with musical sidechain ducking so BGM stays clear and present
    if orig_bgm_volume <= 1.0:
        bgm_gain = max(0.0, orig_bgm_volume)
    else:
        bgm_gain = 1.0 + 2.33 * (orig_bgm_volume - 1.0)

    if bgm_effective_wav and bgm_effective_wav.exists() and bgm_gain > 0.001:
        inputs.extend(["-i", str(bgm_effective_wav.resolve())])
        filter_parts.append(
            f"[{input_idx}:a]highpass=f=35,volume={bgm_gain:.2f},aformat=channel_layouts=stereo,aresample=48000[raw_bgm]"
        )
        filter_parts.append(
            "[raw_bgm][vi]sidechaincompress=threshold=0.15:ratio=2.0:attack=40:release=350[ducked_bgm]"
        )
        mix_inputs.append("[ducked_bgm]")
        input_idx += 1

    # Track 3: Custom external BGM
    if custom_bgm_volume <= 1.0:
        custom_gain = max(0.0, custom_bgm_volume)
    else:
        custom_gain = 1.0 + 2.33 * (custom_bgm_volume - 1.0)

    if custom_bgm_path and custom_bgm_path.exists() and custom_gain > 0.001:
        inputs.extend(["-stream_loop", "-1", "-i", str(custom_bgm_path.resolve())])
        filter_parts.append(
            f"[{input_idx}:a]highpass=f=35,volume={custom_gain:.2f},aformat=channel_layouts=stereo,aresample=48000[raw_custom_bgm]"
        )
        filter_parts.append(
            "[raw_custom_bgm][vi]sidechaincompress=threshold=0.15:ratio=2.0:attack=40:release=350[ducked_custom_bgm]"
        )
        mix_inputs.append("[ducked_custom_bgm]")
        input_idx += 1

    # Track 4: Original voice/vocals
    if orig_voice_volume <= 1.0:
        orig_voice_gain = max(0.0, orig_voice_volume)
    else:
        orig_voice_gain = 1.0 + 2.33 * (orig_voice_volume - 1.0)

    if include_orig_voice and orig_target and orig_target.exists() and orig_voice_gain > 0.001:
        inputs.extend(["-i", str(orig_target.resolve())])
        filter_parts.append(
            f"[{input_idx}:a]highpass=f=75,volume={orig_voice_gain:.2f},aformat=channel_layouts=stereo,aresample=48000[orig_voice]"
        )
        mix_inputs.append("[orig_voice]")
        input_idx += 1

    # Track 5: Original audio passthrough (keeps 100% full original audio independent of BGM slider!)
    if orig_passthrough_wav and orig_passthrough_wav.exists():
        inputs.extend(["-i", str(orig_passthrough_wav.resolve())])
        filter_parts.append(f"[{input_idx}:a]aformat=channel_layouts=stereo,aresample=48000,volume=1.00[passthrough]")
        mix_inputs.append("[passthrough]")
        input_idx += 1

    from dubstudio.paths import resolve_tool
    from dubstudio.packaging import get_subprocess_env, safe_subprocess_run
    ffmpeg_exe = resolve_tool("ffmpeg")

    if len(mix_inputs) > 1:
        amix_chain = "".join(mix_inputs)
        filter_complex = f"{';'.join(filter_parts)};{amix_chain}amix=inputs={len(mix_inputs)}:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.98:attack=3:release=30[out]"
        cmd = [
            ffmpeg_exe, "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-ac", "2",
            "-ar", str(out_sr),
            str(final_mixed_wav.resolve()),
        ]
    else:
        cmd = [
            ffmpeg_exe, "-y",
            *inputs,
            "-filter:a", vi_filter,
            "-ac", "2",
            "-ar", str(out_sr),
            str(final_mixed_wav.resolve()),
        ]

    try:
        safe_subprocess_run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True, env=get_subprocess_env())
    except subprocess.CalledProcessError as e:
        raise DubError(
            code="MIX_FAILED",
            user_message_vi="Lỗi khi hòa trộn âm thanh bằng ffmpeg.",
            hint_vi="Kiểm tra các tệp audio trung gian trong workspace.",
            details={"stderr": (e.stderr.decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else str(e.stderr))[-300:]},
        )

    # Replicate to mixed.wav for explicit multi-stem export
    import shutil
    try:
        shutil.copy2(final_mixed_wav, mixed_wav)
    except Exception:
        pass

    # Automatically generate preview_dubbed.mp4 for instant desktop preview with audio
    input_mp4 = job.workspace / "input.mp4"
    preview_mp4 = job.workspace / "preview_dubbed.mp4"
    if input_mp4.exists() and final_mixed_wav.exists():
        try:
            from dubstudio.paths import resolve_tool
            from dubstudio.packaging import get_subprocess_env, get_subprocess_kwargs
            ffmpeg_exe = resolve_tool("ffmpeg")
            prev_cmd = [
                ffmpeg_exe, "-y",
                "-i", str(input_mp4.resolve()),
                "-i", str(final_mixed_wav.resolve()),
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                str(preview_mp4.resolve()),
            ]
            safe_subprocess_run(
                prev_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=get_subprocess_env(),
            )
        except Exception:
            pass

    emit_event(stage_name, 100.0, "Hòa trộn âm thanh lồng tiếng hoàn tất")
    job.finish_stage(stage_name, ["voice_track.wav"])

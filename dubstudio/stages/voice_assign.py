"""Stage: voice_assign. Assigns character voices based on F0 gender detection and analysis.json."""
import json
from pathlib import Path
from dubstudio.audio.f0 import detect_gender_from_f0, estimate_median_f0
from dubstudio.config import AppConfig
from dubstudio.events import emit_event
from dubstudio.jobstate import JobContext, compute_file_hash


def run(job: JobContext, cfg: AppConfig) -> None:
    stage_name = "voice_assign"
    emit_event(stage_name, 0.0, "Bắt đầu phân tích giọng nói và gán nhân vật (voice assignment)")

    segments_file = job.workspace / "segments.json"
    units_file = job.workspace / "units.json"
    conf_file = job.workspace / "job_config.json"
    conf = {}
    if conf_file.exists():
        try:
            conf = json.loads(conf_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    from dubstudio.tts.base import clean_voice_name

    # Strictly use male and female voices configured in Settings or Job Config
    male_voice = clean_voice_name(conf.get("default_male_voice") or conf.get("voice_male") or cfg.tts.default_male_voice, "Minh Đức")
    female_voice = clean_voice_name(conf.get("default_female_voice") or conf.get("voice_female") or cfg.tts.default_female_voice, "Quỳnh Anh")
    detect_gender = bool(conf.get("detect_gender", False))
    single_choice = conf.get("single_voice_gender", "male")
    single_voice_override = clean_voice_name(conf.get("single_voice"), male_voice) if conf.get("single_voice") else None

    import hashlib
    base_hash = compute_file_hash(segments_file)
    cfg_sig = f"{detect_gender}|{single_choice}|{male_voice}|{female_voice}|{single_voice_override}"
    input_hash = hashlib.md5(f"{base_hash}|{cfg_sig}".encode("utf-8")).hexdigest()

    with open(segments_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    segments = data.get("segments", [])

    # Fast-path: When detect_gender is False, assign fixed voice immediately without F0 audio analysis
    if not detect_gender:
        if single_voice_override:
            target_voice = single_voice_override
            from dubstudio.tts.base import get_voice_gender
            target_gender = get_voice_gender(target_voice)
            if target_gender == "unknown":
                target_gender = "female" if single_choice == "female" else "male"
        else:
            target_voice = female_voice if single_choice == "female" else male_voice
            target_gender = "female" if single_choice == "female" else "male"

        already_assigned = len(segments) > 0 and all(s.get("voice") == target_voice for s in segments)
        if job.is_stage_done(stage_name, input_hash) and already_assigned:
            emit_event(stage_name, 100.0, f"Giọng đọc cố định ({target_voice}) đã được gán trước đó (bỏ qua)")
            job.finish_stage(stage_name, ["segments.json"])
            return

        job.start_stage(stage_name, input_hash)
        for seg in segments:
            if not seg.get("user_edited") and not seg.get("user_edited_voice"):
                seg["gender"] = target_gender
                seg["voice"] = target_voice

        with open(segments_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        if units_file.exists():
            with open(units_file, "r", encoding="utf-8") as f:
                units = json.load(f)
            for u in units:
                u["gender"] = target_gender
                u["voice"] = target_voice
            with open(units_file, "w", encoding="utf-8") as f:
                json.dump(units, f, ensure_ascii=False, indent=2)

        emit_event(stage_name, 100.0, f"Đã gán giọng đọc cố định: {target_voice} (bỏ qua nhận diện nam/nữ)")
        job.finish_stage(stage_name, ["segments.json"])
        return

    # Multi-voice mode: detect_gender is True -> proceed with F0 pitch analysis
    already_assigned = len(segments) > 0 and all(bool(s.get("voice")) for s in segments)
    if job.is_stage_done(stage_name, input_hash) and already_assigned:
        emit_event(stage_name, 100.0, "Giai đoạn voice_assign đã hoàn thành (bỏ qua)")
        job.finish_stage(stage_name, ["segments.json"])
        return

    job.start_stage(stage_name, input_hash)

    # Audio input for F0 analysis (prefer vocals.wav, fallback to orig.wav)
    audio_path = job.workspace / "audio" / "vocals.wav"
    if not audio_path.exists():
        audio_path = job.workspace / "audio" / "orig.wav"

    detected_f0_list = []

    for seg in segments:
        st = seg.get("start", 0.0)
        en = seg.get("end", 0.0)
        # Prefer contextual gender already determined by Gemini during translation
        gender = seg.get("gender")
        if not gender or gender == "unknown":
            f0 = estimate_median_f0(str(audio_path.resolve()), st, en)
            gender = detect_gender_from_f0(f0)
            seg["f0"] = round(f0, 1)

        if gender and gender != "unknown":
            seg["gender"] = gender
            if seg.get("f0"):
                detected_f0_list.append(seg["f0"])

    # Determine dominant gender of the whole video
    dominant_gender = "female" if (detected_f0_list and (float(sum(detected_f0_list)/len(detected_f0_list))) >= 165.0) else "male"
    if single_choice in ("male", "female"):
        dominant_gender = single_choice

    if not detect_gender:
        # Uniform single-voice mode: assign only if segment was not manually edited by user
        if single_voice_override:
            target_voice = single_voice_override
        else:
            target_voice = female_voice if dominant_gender == "female" else male_voice
        for seg in segments:
            if not seg.get("user_edited") and not seg.get("user_edited_voice"):
                seg["gender"] = dominant_gender
                seg["voice"] = target_voice
    else:
        # Multi-voice mode: classify male vs female segments (skip if segment was manually edited)
        for seg in segments:
            if seg.get("user_edited") or seg.get("user_edited_voice"):
                continue
            g = seg.get("gender")
            if g == "male":
                seg["voice"] = male_voice
            elif g == "female":
                seg["voice"] = female_voice
            else:
                seg["gender"] = dominant_gender
                seg["voice"] = female_voice if dominant_gender == "female" else male_voice

    with open(segments_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Also update units.json if it exists
    if units_file.exists():
        with open(units_file, "r", encoding="utf-8") as f:
            units = json.load(f)

        if not detect_gender:
            target_voice = female_voice if dominant_gender == "female" else male_voice
            for u in units:
                u["gender"] = dominant_gender
                u["voice"] = target_voice
        else:
            seg_map = {s["id"]: s for s in segments}
            for u in units:
                first_part_id = u["parts"][0] if u.get("parts") else None
                if first_part_id and first_part_id in seg_map:
                    u["gender"] = seg_map[first_part_id].get("gender", dominant_gender)
                    u["voice"] = seg_map[first_part_id].get("voice", male_voice if dominant_gender == "male" else female_voice)
                else:
                    u_st = u.get("start", 0.0)
                    u_en = u.get("end", 0.0)
                    u_f0 = estimate_median_f0(str(audio_path.resolve()), u_st, u_en)
                    u_gen = detect_gender_from_f0(u_f0)
                    if u_gen == "unknown":
                        u_gen = dominant_gender
                    u["gender"] = u_gen
                    u["voice"] = male_voice if u_gen == "male" else female_voice

        with open(units_file, "w", encoding="utf-8") as f:
            json.dump(units, f, ensure_ascii=False, indent=2)

    emit_event(stage_name, 100.0, f"Gán giọng đọc hoàn tất cho {len(segments)} đoạn thoại")
    job.finish_stage(stage_name, ["segments.json"])
